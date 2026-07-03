from __future__ import annotations

import base64
import json
import logging
import os
import random
import shutil
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from sqlalchemy.orm import Session

from core.app.pipeline.analyze_provider import AnalyzeError, AnalyzeProvider, is_vision_rejection_error, llm_provider_for_jobs
from core.contracts.error_codes import ErrorCode
from core.db.models.asset import Asset
from core.db.session import get_data_dir

logger = logging.getLogger(__name__)

VerifyPhase = Literal["initial", "retry"]


class VerifyPrepareError(Exception):
	"""Verify input could not be prepared (OCR/image missing, fallback failed, etc.)."""

	def __init__(self, reason: str):
		self.reason = reason
		super().__init__(reason)


def _now_ms() -> int:
    return int(time.time() * 1000)


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_str(name: str) -> str | None:
    raw = os.environ.get(name)
    if raw is None:
        return None
    s = raw.strip()
    return s or None


def _json_dumps_compact(obj: object) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"), default=str)


def _clamp_int(v: int, lo: int, hi: int) -> int:
    return max(int(lo), min(int(v), int(hi)))


def get_verify_mode() -> str:
    return (_env_str("KEYFRAME_VERIFY_MODE") or "multimodal").strip().lower()


def compute_max_verify_per_job(*, duration_ms: int | None) -> int:
    """Scale initial verify cap with video duration while keeping a hard ceiling."""

    base = max(0, _env_int("KEYFRAME_VERIFY_MAX_PER_JOB", 5))
    abs_max = max(base, _env_int("KEYFRAME_VERIFY_MAX_PER_JOB_ABS", 25))
    bonus_per_5min = max(0, _env_int("KEYFRAME_VERIFY_DURATION_BONUS_PER_5MIN", 1))
    bonus_max = max(0, _env_int("KEYFRAME_VERIFY_DURATION_BONUS_MAX", 15))
    if duration_ms is None or duration_ms <= 0:
        return base
    bonus = min(bonus_max, (int(duration_ms) // (5 * 60_000)) * bonus_per_5min)
    return min(abs_max, base + bonus)


def get_verify_threshold() -> float:
    raw = (_env_str("KEYFRAME_VERIFY_CONFIDENCE_THRESHOLD") or "0.4").strip()
    try:
        return float(raw)
    except Exception:
        return 0.4


def get_verify_concurrency() -> int:
    return _clamp_int(_env_int("KEYFRAME_VERIFY_CONCURRENCY", 2), 1, 8)


@dataclass
class VerifyBudget:
    max_verify_per_highlight: int
    max_verify_per_job: int
    retry_max_per_highlight: int
    local_search_window_ms: int


@dataclass
class VerifyStats:
    verified_count: int = 0
    dropped_count: int = 0
    skipped_prepare_count: int = 0
    retry_scheduled_count: int = 0
    retried_kept_count: int = 0
    retried_dropped_count: int = 0
    verify_used_job: int = 0


def get_verify_budget(*, duration_ms: int | None = None) -> VerifyBudget:
    retry_per_hl = _env_str("KEYFRAME_RETRY_MAX_PER_HIGHLIGHT")
    if retry_per_hl is not None:
        retry_max = max(0, _env_int("KEYFRAME_RETRY_MAX_PER_HIGHLIGHT", 1))
    else:
        retry_max = max(0, _env_int("KEYFRAME_RETRY_MAX", 1))
    return VerifyBudget(
        max_verify_per_highlight=max(0, _env_int("KEYFRAME_VERIFY_MAX_PER_HIGHLIGHT", 1)),
        max_verify_per_job=compute_max_verify_per_job(duration_ms=duration_ms),
        retry_max_per_highlight=retry_max,
        local_search_window_ms=max(1_000, _env_int("KEYFRAME_LOCAL_SEARCH_WINDOW_MS", 10_000)),
    )


@dataclass
class VerifyPassState:
    """Shared state across initial + retry verify passes within one job."""

    requested_mode: str
    vision_unavailable: bool = False
    lock: threading.Lock = field(default_factory=threading.Lock)


@dataclass
class _VerifyCandidate:
    block: dict
    highlight: dict
    block_id: str | None
    highlight_id: str | None
    asset_id: str
    time_ms: int
    start_ms: int
    end_ms: int
    highlight_text: str
    input_confidence: float | None
    phase: VerifyPhase
    messages: list[dict] = field(default_factory=list)


@dataclass
class _VerifyLlmOutcome:
    candidate: _VerifyCandidate
    keep: bool | None
    llm_confidence: float | None
    llm_reason: str | None
    retry_direction: str | None = None
    retry_offset_ms: int | None = None
    effective_mode: str | None = None
    fallback_reason: str | None = None
    error: Exception | None = None


def _verify_results_path(*, project_id: str, job_id: str) -> Path:
    data_dir = get_data_dir().resolve()
    base = (data_dir / project_id / "artifacts" / job_id / "keyframe_verify").resolve()
    if not base.is_relative_to(data_dir):
        raise ValueError("keyframe_verify dir escapes DATA_DIR")
    base.mkdir(parents=True, exist_ok=True)
    return (base / "results.jsonl").resolve()


def append_keyframe_verify_result(
    *,
    project_id: str,
    job_id: str,
    record: dict,
) -> None:
    """Best-effort append of a single verify outcome for benchmark observability."""

    try:
        path = _verify_results_path(project_id=project_id, job_id=job_id)
        payload = {"tsMs": _now_ms(), "projectId": project_id, "jobId": job_id, **record}
        with path.open("a", encoding="utf-8") as f:
            f.write(_json_dumps_compact(payload) + "\n")
    except Exception:
        return


def _run_tesseract_ocr(*, image_abs: Path, timeout_s: int = 15) -> str | None:
    exe = shutil.which("tesseract")
    if not exe:
        return None

    try:
        proc = subprocess.run(
            [exe, str(image_abs), "stdout", "--dpi", "150"],
            capture_output=True,
            text=True,
            timeout=max(1, int(timeout_s)),
            check=False,
        )
        out = (proc.stdout or "").strip()
        return out or None
    except Exception:
        return None


def _encode_image_data_url(*, image_abs: Path) -> str | None:
    try:
        b = image_abs.read_bytes()
    except Exception:
        return None
    if not b:
        return None
    max_bytes = max(50_000, _env_int("KEYFRAME_VERIFY_IMAGE_MAX_BYTES", 400_000))
    if len(b) > max_bytes:
        return None
    return "data:image/jpeg;base64," + base64.b64encode(b).decode("ascii")


def _resolve_asset_image_abs(*, session: Session, asset_id: str) -> Path | None:
    row = session.get(Asset, asset_id)
    if row is None:
        return None
    rel = getattr(row, "file_path", None)
    if not isinstance(rel, str) or not rel:
        return None
    data_dir = get_data_dir().resolve()
    abs_path = (data_dir / rel).resolve()
    if not abs_path.is_relative_to(data_dir):
        return None
    if not abs_path.exists() or not abs_path.is_file():
        return None
    return abs_path


def _coerce_confidence(val: object) -> float | None:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        v = float(val)
        if v != v:
            return None
        return max(0.0, min(1.0, v))
    if isinstance(val, str):
        s = val.strip().lower()
        if not s:
            return None
        if s in {"low", "l"}:
            return 0.2
        if s in {"medium", "mid", "m"}:
            return 0.5
        if s in {"high", "h"}:
            return 0.8
        try:
            return max(0.0, min(1.0, float(s)))
        except Exception:
            return None
    return None


def _parse_retry_hint(res: dict) -> tuple[str | None, int | None]:
    retry = res.get("retry")
    if not isinstance(retry, dict):
        return (None, None)
    direction_raw = retry.get("direction")
    direction: str | None = None
    if isinstance(direction_raw, str):
        d = direction_raw.strip().lower()
        if d in {"before", "after"}:
            direction = d
    offset_raw = retry.get("offsetMs")
    offset_ms: int | None = None
    if isinstance(offset_raw, (int, float)):
        offset_ms = max(1, int(offset_raw))
    elif isinstance(offset_raw, str):
        try:
            offset_ms = max(1, int(float(offset_raw.strip())))
        except Exception:
            offset_ms = None
    return (direction, offset_ms)


def _compute_retry_time_ms_fallback(
    *,
    time_ms: int,
    start_ms: int,
    end_ms: int,
    local_search_window_ms: int,
) -> int:
    mid = int((int(start_ms) + int(end_ms)) // 2)
    direction = 1 if mid >= int(time_ms) else -1
    step = min(int(local_search_window_ms), abs(mid - int(time_ms)))
    if step <= 0:
        step = int(local_search_window_ms)
    new_tm = int(time_ms) + direction * int(step)
    return _clamp_int(new_tm, int(start_ms), int(end_ms) - 1)


def compute_retry_time_ms(
    *,
    time_ms: int,
    start_ms: int,
    end_ms: int,
    local_search_window_ms: int,
    retry_direction: str | None = None,
    retry_offset_ms: int | None = None,
) -> int:
    """Compute a retry timestamp from LLM hint or midpoint fallback."""

    if retry_direction in {"before", "after"} and retry_offset_ms is not None and retry_offset_ms > 0:
        sign = -1 if retry_direction == "before" else 1
        offset = _clamp_int(int(retry_offset_ms), 1, int(local_search_window_ms))
        new_tm = int(time_ms) + sign * offset
        return _clamp_int(new_tm, int(start_ms), int(end_ms) - 1)
    return _compute_retry_time_ms_fallback(
        time_ms=time_ms,
        start_ms=start_ms,
        end_ms=end_ms,
        local_search_window_ms=local_search_window_ms,
    )


def _call_llm_with_backoff(*, provider: AnalyzeProvider, messages: list[dict], max_tokens: int | None = None) -> dict:
    max_attempts = max(1, _env_int("KEYFRAME_VERIFY_MAX_ATTEMPTS", 2))
    attempt = 0
    while True:
        attempt += 1
        try:
            res = provider.generate_json("keyframe_verify", {"messages": messages}, max_tokens=max_tokens)
            if not isinstance(res, dict):
                raise AnalyzeError(
                    code=ErrorCode.JOB_STAGE_FAILED,
                    message="Invalid LLM output",
                    details={"reason": "invalid_llm_output", "task": "keyframe_verify", "outputType": type(res).__name__},
                )
            return res
        except AnalyzeError as e:
            reason = str((e.details or {}).get("reason") or "")
            if is_vision_rejection_error(e):
                raise
            if reason in {"rate_limited", "upstream_error", "timeout"} and attempt < max_attempts:
                sleep_s = min(6.0, 0.5 * (2 ** (attempt - 1)))
                sleep_s = sleep_s * (0.8 + random.random() * 0.4)
                time.sleep(sleep_s)
                continue
            raise


def _verify_json_schema_hint() -> str:
    return (
        "Return ONLY one JSON object (no markdown) with keys: "
        "keep(boolean), confidence(number 0..1), reason(string), "
        "retry(object, optional when keep=false): {direction(string: before|after), offsetMs(number)}. "
        "offsetMs is milliseconds relative to the current frame; direction decides whether to subtract (before) or add (after)."
    )


def build_verify_request_text_only(
    *,
    highlight_text: str,
    time_range: tuple[int, int],
    ocr_text: str | None,
    output_language: str | None,
) -> list[dict]:
    lang = (output_language or "").strip()
    lang_hint = ""
    if lang and lang.lower() != "auto":
        lang_hint = f"Write the `reason` string in {lang}."

    system = (
        "You are verifying whether a candidate keyframe screenshot is useful for a highlight in a learning video. "
        + _verify_json_schema_hint()
        + " "
        "Rules: keep=true only if the image likely contains meaningful visual info (slide/diagram/code/UI/formula) that supports the highlight. "
        "If OCR text is empty or irrelevant, prefer keep=false. "
        "When keep=false, optionally suggest retry.direction and retry.offsetMs to search for a better frame nearby. "
        + (" " + lang_hint if lang_hint else "")
    )

    payload = {
        "task": "keyframe_verify",
        "highlight": highlight_text,
        "timeRange": {"startMs": int(time_range[0]), "endMs": int(time_range[1])},
        "ocrText": ocr_text or "",
    }

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": _json_dumps_compact(payload)},
    ]


def build_verify_request_multimodal(
    *,
    highlight_text: str,
    time_range: tuple[int, int],
    image_data_url: str,
    output_language: str | None,
) -> list[dict]:
    lang = (output_language or "").strip()
    lang_hint = ""
    if lang and lang.lower() != "auto":
        lang_hint = f"Write the `reason` string in {lang}."

    system = (
        "You are verifying whether a candidate keyframe screenshot is useful for a highlight in a learning video. "
        + _verify_json_schema_hint()
        + " "
        "keep=true only if the image contains meaningful visual info supporting the highlight. "
        "When keep=false, optionally suggest retry.direction and retry.offsetMs to search for a better frame nearby. "
        + (" " + lang_hint if lang_hint else "")
    )

    user_content = [
        {
            "type": "text",
            "text": _json_dumps_compact(
                {
                    "task": "keyframe_verify",
                    "highlight": highlight_text,
                    "timeRange": {"startMs": int(time_range[0]), "endMs": int(time_range[1])},
                }
            ),
        },
        {"type": "image_url", "image_url": {"url": image_data_url}},
    ]

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user_content},
    ]


def _resolve_provider(mode: str) -> AnalyzeProvider | None:
    if mode not in {"ocr", "multimodal"}:
        return None
    resolved = llm_provider_for_jobs()
    if resolved is None:
        raise AnalyzeError(
            code=ErrorCode.JOB_STAGE_FAILED,
            message="LLM credentials missing",
            details={"reason": "missing_credentials", "task": "keyframe_verify"},
        )
    return resolved


def _collect_candidates(
    *,
    session: Session,
    content_blocks: list[dict],
    phase: VerifyPhase,
    retried_highlight_ids: set[str] | None,
    threshold: float,
    budget: VerifyBudget,
    verify_used_job: int,
) -> list[_VerifyCandidate]:
    candidates: list[_VerifyCandidate] = []
    retried_ids = retried_highlight_ids or set()
    # Retry phase always verifies scheduled highlights (not subject to initial job cap).
    enforce_job_cap = phase != "retry"

    for b in content_blocks:
        if enforce_job_cap and verify_used_job + len(candidates) >= budget.max_verify_per_job:
            break
        if not isinstance(b, dict):
            continue
        hls = b.get("highlights")
        if not isinstance(hls, list):
            continue

        for h in hls:
            if enforce_job_cap and verify_used_job + len(candidates) >= budget.max_verify_per_job:
                break
            if not isinstance(h, dict):
                continue

            highlight_id = h.get("highlightId") if isinstance(h.get("highlightId"), str) else None

            if phase == "retry":
                if not highlight_id or highlight_id not in retried_ids:
                    continue
            else:
                conf = _coerce_confidence(h.get("keyframeConfidence"))
                if conf is None or conf >= threshold:
                    continue
                # max_verify_per_highlight: 1=enable initial verify for low-confidence highlights, 0=disable.
                if budget.max_verify_per_highlight <= 0:
                    continue

            kfs = h.get("keyframes")
            if not isinstance(kfs, list) or not kfs:
                continue

            kf0 = kfs[0] if isinstance(kfs[0], dict) else None
            if not isinstance(kf0, dict):
                continue

            tm = kf0.get("timeMs")
            if not isinstance(tm, int):
                continue

            asset_id = kf0.get("assetId")
            if not isinstance(asset_id, str) or not asset_id:
                continue

            highlight_text = h.get("text")
            if not isinstance(highlight_text, str):
                highlight_text = ""

            hs = h.get("startMs")
            he = h.get("endMs")
            if not isinstance(hs, int) or not isinstance(he, int) or he <= hs:
                continue

            image_abs = _resolve_asset_image_abs(session=session, asset_id=asset_id)
            if image_abs is None:
                continue

            input_confidence = _coerce_confidence(h.get("keyframeConfidence")) if phase == "initial" else None
            block_id = b.get("blockId") if isinstance(b.get("blockId"), str) else None

            candidates.append(
                _VerifyCandidate(
                    block=b,
                    highlight=h,
                    block_id=block_id,
                    highlight_id=highlight_id,
                    asset_id=asset_id,
                    time_ms=int(tm),
                    start_ms=int(hs),
                    end_ms=int(he),
                    highlight_text=highlight_text,
                    input_confidence=input_confidence,
                    phase=phase,
                )
            )

    return candidates


def _multimodal_messages_include_image(messages: list[dict]) -> bool:
	for m in messages:
		if not isinstance(m, dict):
			continue
		content = m.get("content")
		if not isinstance(content, list):
			continue
		for part in content:
			if not isinstance(part, dict):
				continue
			if str(part.get("type") or "").strip().lower() != "image_url":
				continue
			image_url = part.get("image_url")
			url = image_url.get("url") if isinstance(image_url, dict) else None
			if isinstance(url, str) and url.startswith("data:image/"):
				return True
	return False


def _prepare_candidate_messages(
    *,
    candidate: _VerifyCandidate,
    mode: str,
    session: Session,
    output_language: str | None,
) -> list[dict] | None:
    image_abs = _resolve_asset_image_abs(session=session, asset_id=candidate.asset_id)
    if image_abs is None:
        return None

    if mode == "ocr":
        ocr_text = _run_tesseract_ocr(image_abs=image_abs)
        if ocr_text is None:
            return None
        return build_verify_request_text_only(
            highlight_text=candidate.highlight_text,
            time_range=(candidate.start_ms, candidate.end_ms),
            ocr_text=ocr_text,
            output_language=output_language,
        )

    data_url = _encode_image_data_url(image_abs=image_abs)
    if data_url is None:
        return None
    messages = build_verify_request_multimodal(
        highlight_text=candidate.highlight_text,
        time_range=(candidate.start_ms, candidate.end_ms),
        image_data_url=data_url,
        output_language=output_language,
    )
    if not _multimodal_messages_include_image(messages):
        logger.warning(
            "[keyframe_verify] multimodal prepare missing image highlightId=%s assetId=%s",
            candidate.highlight_id,
            candidate.asset_id,
        )
        return None
    return messages


def _resolve_effective_verify_mode(*, requested_mode: str, pass_state: VerifyPassState) -> str:
    mode = (requested_mode or "multimodal").strip().lower()
    if mode in {"off", "ocr"}:
        return mode
    with pass_state.lock:
        if pass_state.vision_unavailable:
            return "ocr"
    return "multimodal"


def _mark_vision_unavailable(pass_state: VerifyPassState) -> None:
    with pass_state.lock:
        pass_state.vision_unavailable = True


def _parse_llm_verify_response(res: dict) -> tuple[bool | None, float | None, str | None, str | None, int | None]:
    keep: bool | None = None
    llm_confidence: float | None = None
    llm_reason: str | None = None
    retry_direction: str | None = None
    retry_offset_ms: int | None = None
    if isinstance(res, dict):
        if "keep" in res:
            keep = bool(res.get("keep"))
        llm_confidence = _coerce_confidence(res.get("confidence"))
        reason_raw = res.get("reason")
        if isinstance(reason_raw, str):
            llm_reason = reason_raw
        retry_direction, retry_offset_ms = _parse_retry_hint(res)
    return keep, llm_confidence, llm_reason, retry_direction, retry_offset_ms


def _run_llm_outcomes_parallel(
    *,
    requested_mode: str,
    pass_state: VerifyPassState,
    candidates: list[_VerifyCandidate],
    session: Session,
    output_language: str | None,
    concurrency: int,
) -> list[_VerifyLlmOutcome]:
    if not candidates:
        return []

    thread_local = threading.local()

    def _provider_for_thread() -> AnalyzeProvider:
        cached = getattr(thread_local, "provider", None)
        if cached is not None:
            return cached
        provider = _resolve_provider(requested_mode)
        if provider is None:
            raise AnalyzeError(
                code=ErrorCode.JOB_STAGE_FAILED,
                message="LLM credentials missing",
                details={"reason": "missing_credentials", "task": "keyframe_verify"},
            )
        thread_local.provider = provider
        return provider

    outcomes: list[_VerifyLlmOutcome] = []

    def _verify_one_candidate(candidate: _VerifyCandidate) -> _VerifyLlmOutcome:
        effective_mode = _resolve_effective_verify_mode(requested_mode=requested_mode, pass_state=pass_state)
        messages = _prepare_candidate_messages(
            candidate=candidate,
            mode=effective_mode,
            session=session,
            output_language=output_language,
        )
        if messages is None:
            return _VerifyLlmOutcome(
                candidate=candidate,
                keep=None,
                llm_confidence=None,
                llm_reason=None,
                effective_mode=effective_mode,
                error=VerifyPrepareError("verify_input_unavailable"),
            )

        # Another worker may have marked vision unavailable while we prepared multimodal input.
        if effective_mode == "multimodal":
            effective_mode_retry = _resolve_effective_verify_mode(requested_mode=requested_mode, pass_state=pass_state)
            if effective_mode_retry == "ocr":
                effective_mode = "ocr"
                messages = _prepare_candidate_messages(
                    candidate=candidate,
                    mode=effective_mode,
                    session=session,
                    output_language=output_language,
                )
                if messages is None:
                    return _VerifyLlmOutcome(
                        candidate=candidate,
                        keep=None,
                        llm_confidence=None,
                        llm_reason=None,
                        effective_mode=effective_mode,
                        error=VerifyPrepareError("verify_input_unavailable"),
                    )

        provider = _provider_for_thread()
        try:
            res = _call_llm_with_backoff(provider=provider, messages=messages, max_tokens=512)
            keep, llm_confidence, llm_reason, retry_direction, retry_offset_ms = _parse_llm_verify_response(res)
            return _VerifyLlmOutcome(
                candidate=candidate,
                keep=keep,
                llm_confidence=llm_confidence,
                llm_reason=llm_reason,
                retry_direction=retry_direction,
                retry_offset_ms=retry_offset_ms,
                effective_mode=effective_mode,
            )
        except AnalyzeError as exc:
            if requested_mode == "multimodal" and effective_mode == "multimodal" and is_vision_rejection_error(exc):
                _mark_vision_unavailable(pass_state)
                logger.info(
                    "[keyframe_verify] multimodal rejected by upstream; falling back to ocr highlightId=%s",
                    candidate.highlight_id,
                )
                ocr_messages = _prepare_candidate_messages(
                    candidate=candidate,
                    mode="ocr",
                    session=session,
                    output_language=output_language,
                )
                if ocr_messages is None:
                    return _VerifyLlmOutcome(
                        candidate=candidate,
                        keep=None,
                        llm_confidence=None,
                        llm_reason=None,
                        effective_mode="ocr",
                        fallback_reason="vision_rejected_ocr_unavailable",
                        error=VerifyPrepareError("vision_rejected_ocr_unavailable"),
                    )
                try:
                    res = _call_llm_with_backoff(provider=provider, messages=ocr_messages, max_tokens=512)
                except Exception:
                    return _VerifyLlmOutcome(
                        candidate=candidate,
                        keep=None,
                        llm_confidence=None,
                        llm_reason=None,
                        effective_mode="ocr",
                        fallback_reason="vision_rejected_ocr_failed",
                        error=VerifyPrepareError("vision_rejected_ocr_failed"),
                    )
                keep, llm_confidence, llm_reason, retry_direction, retry_offset_ms = _parse_llm_verify_response(res)
                return _VerifyLlmOutcome(
                    candidate=candidate,
                    keep=keep,
                    llm_confidence=llm_confidence,
                    llm_reason=llm_reason,
                    retry_direction=retry_direction,
                    retry_offset_ms=retry_offset_ms,
                    effective_mode="ocr",
                    fallback_reason="vision_rejected",
                )
            return _VerifyLlmOutcome(
                candidate=candidate,
                keep=None,
                llm_confidence=None,
                llm_reason=None,
                effective_mode=effective_mode,
                error=exc,
            )
        except Exception as e:
            return _VerifyLlmOutcome(
                candidate=candidate,
                keep=None,
                llm_confidence=None,
                llm_reason=None,
                effective_mode=effective_mode,
                error=e,
            )

    workers = min(max(1, concurrency), len(candidates))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(_verify_one_candidate, c) for c in candidates]
        for fut in as_completed(futures):
            outcomes.append(fut.result())
    return outcomes


def _drop_highlight_keyframes(highlight: dict) -> None:
    highlight["keyframes"] = []
    highlight["keyframe"] = None


def _apply_skipped_prepare(
    *,
    candidate: _VerifyCandidate,
    project_id: str,
    job_id: str,
    mode: str,
    requested_mode: str | None = None,
    stats: VerifyStats,
    skip_reason: str,
    fallback_reason: str | None = None,
) -> None:
    """Drop keyframes when verify input cannot be prepared (OCR/image missing, etc.)."""

    h = candidate.highlight
    _drop_highlight_keyframes(h)
    if candidate.phase == "retry":
        stats.retried_dropped_count += 1
        action = "retried_dropped"
    else:
        stats.skipped_prepare_count += 1
        stats.dropped_count += 1
        action = "skipped_prepare"
    append_keyframe_verify_result(
        project_id=project_id,
        job_id=job_id,
        record={
            "highlightId": candidate.highlight_id,
            "blockId": candidate.block_id,
            "assetId": candidate.asset_id,
            "timeMs": candidate.time_ms,
            "mode": mode,
            "requestedMode": requested_mode or mode,
            "effectiveMode": mode,
            "phase": candidate.phase,
            "keep": False,
            "reason": skip_reason,
            "inputConfidence": candidate.input_confidence,
            "action": action,
            **({"fallbackReason": fallback_reason} if fallback_reason else {}),
            **({"retryTimeMs": candidate.time_ms} if candidate.phase == "retry" else {}),
        },
    )
    logger.warning(
        "[keyframe_verify] skipped prepare phase=%s highlightId=%s reason=%s",
        candidate.phase,
        candidate.highlight_id,
        skip_reason,
    )


def drop_retried_highlights_missing_asset(
    *,
    content_blocks: list[dict],
    scheduled_highlight_ids: list[str],
    project_id: str,
    job_id: str,
    mode: str,
) -> list[str]:
    """Drop scheduled retries that still lack assetId after re-extraction. Returns ids still eligible."""

    scheduled = set(scheduled_highlight_ids)
    remaining: list[str] = []
    for b in content_blocks:
        if not isinstance(b, dict):
            continue
        hls = b.get("highlights")
        if not isinstance(hls, list):
            continue
        for h in hls:
            if not isinstance(h, dict):
                continue
            highlight_id = h.get("highlightId") if isinstance(h.get("highlightId"), str) else None
            if not highlight_id or highlight_id not in scheduled:
                continue
            kfs = h.get("keyframes")
            if not isinstance(kfs, list) or not kfs:
                _drop_highlight_keyframes(h)
                append_keyframe_verify_result(
                    project_id=project_id,
                    job_id=job_id,
                    record={
                        "highlightId": highlight_id,
                        "blockId": b.get("blockId") if isinstance(b.get("blockId"), str) else None,
                        "mode": mode,
                        "phase": "retry",
                        "keep": False,
                        "reason": "missing_keyframes_after_extract",
                        "action": "retried_dropped",
                    },
                )
                logger.warning(
                    "[keyframe_verify] retried highlight missing keyframes highlightId=%s",
                    highlight_id,
                )
                continue
            kf0 = kfs[0] if isinstance(kfs[0], dict) else None
            asset_id = kf0.get("assetId") if isinstance(kf0, dict) else None
            if not isinstance(asset_id, str) or not asset_id:
                _drop_highlight_keyframes(h)
                tm = kf0.get("timeMs") if isinstance(kf0, dict) else None
                append_keyframe_verify_result(
                    project_id=project_id,
                    job_id=job_id,
                    record={
                        "highlightId": highlight_id,
                        "blockId": b.get("blockId") if isinstance(b.get("blockId"), str) else None,
                        "timeMs": tm if isinstance(tm, int) else None,
                        "mode": mode,
                        "phase": "retry",
                        "keep": False,
                        "reason": "missing_asset_after_extract",
                        "action": "retried_dropped",
                        "retryTimeMs": tm if isinstance(tm, int) else None,
                    },
                )
                logger.warning(
                    "[keyframe_verify] retried highlight missing assetId highlightId=%s timeMs=%s",
                    highlight_id,
                    tm,
                )
                continue
            remaining.append(highlight_id)
    return remaining


def _run_verify_pass(
    *,
    session: Session,
    project_id: str,
    job_id: str,
    content_blocks: list[dict],
    output_language: str | None,
    mode: str,
    budget: VerifyBudget,
    pass_state: VerifyPassState,
    phase: VerifyPhase,
    retried_highlight_ids: set[str] | None = None,
    verify_used_job: int = 0,
    highlight_retry_used: dict[str, int] | None = None,
) -> tuple[list[int], list[str], VerifyStats, int]:
    """Run one verify pass (initial or retry). Returns (retry_times, scheduled_highlight_ids, stats, verify_used_job)."""

    t_start = time.perf_counter()
    stats = VerifyStats(verify_used_job=verify_used_job)
    retry_times: list[int] = []
    scheduled_highlight_ids: list[str] = []
    retry_used = highlight_retry_used if highlight_retry_used is not None else {}

    provider = _resolve_provider(mode)
    if provider is None:
        return ([], [], stats, verify_used_job)

    threshold = float(get_verify_threshold())
    concurrency = get_verify_concurrency()

    candidates = _collect_candidates(
        session=session,
        content_blocks=content_blocks,
        phase=phase,
        retried_highlight_ids=retried_highlight_ids,
        threshold=threshold,
        budget=budget,
        verify_used_job=verify_used_job,
    )

    outcomes = _run_llm_outcomes_parallel(
        requested_mode=mode,
        pass_state=pass_state,
        candidates=candidates,
        session=session,
        output_language=output_language,
        concurrency=concurrency,
    )

    for outcome in outcomes:
        c = outcome.candidate
        h = c.highlight
        effective_mode = outcome.effective_mode or mode

        if isinstance(outcome.error, VerifyPrepareError):
            _apply_skipped_prepare(
                candidate=c,
                project_id=project_id,
                job_id=job_id,
                mode=effective_mode,
                requested_mode=mode,
                stats=stats,
                skip_reason=outcome.error.reason,
                fallback_reason=outcome.fallback_reason,
            )
            continue

        stats.verify_used_job += 1
        stats.verified_count += 1

        if outcome.error is not None:
            if isinstance(outcome.error, AnalyzeError):
                raise outcome.error
            raise AnalyzeError(
                code=ErrorCode.JOB_STAGE_FAILED,
                message="Keyframe verify failed",
                details={"reason": "verify_error", "task": "keyframe_verify"},
            ) from outcome.error

        base_record = {
            "highlightId": c.highlight_id,
            "blockId": c.block_id,
            "assetId": c.asset_id,
            "timeMs": c.time_ms,
            "mode": effective_mode,
            "requestedMode": mode,
            "effectiveMode": effective_mode,
            "phase": phase,
            "keep": outcome.keep,
            "confidence": outcome.llm_confidence,
            "reason": outcome.llm_reason,
            "inputConfidence": c.input_confidence,
        }
        if outcome.fallback_reason:
            base_record["fallbackReason"] = outcome.fallback_reason

        if phase == "retry":
            base_record["retryTimeMs"] = c.time_ms
            if outcome.keep is True:
                stats.retried_kept_count += 1
                append_keyframe_verify_result(
                    project_id=project_id,
                    job_id=job_id,
                    record={**base_record, "action": "retried_kept"},
                )
                continue

            _drop_highlight_keyframes(h)
            stats.retried_dropped_count += 1
            append_keyframe_verify_result(
                project_id=project_id,
                job_id=job_id,
                record={**base_record, "action": "retried_dropped"},
            )
            continue

        # initial phase
        if outcome.keep is True:
            append_keyframe_verify_result(
                project_id=project_id,
                job_id=job_id,
                record={**base_record, "action": "kept"},
            )
            continue

        hl_key = c.highlight_id or f"{c.block_id}:{c.time_ms}"
        used = retry_used.get(hl_key, 0)
        allow_retry = used < budget.retry_max_per_highlight

        if allow_retry:
            new_tm = compute_retry_time_ms(
                time_ms=c.time_ms,
                start_ms=c.start_ms,
                end_ms=c.end_ms,
                local_search_window_ms=budget.local_search_window_ms,
                retry_direction=outcome.retry_direction,
                retry_offset_ms=outcome.retry_offset_ms,
            )
            if new_tm != c.time_ms:
                h["keyframes"] = [{"timeMs": int(new_tm)}]
                h["keyframe"] = {"timeMs": int(new_tm)}
                retry_times.append(int(new_tm))
                retry_used[hl_key] = used + 1
                stats.retry_scheduled_count += 1
                if c.highlight_id:
                    scheduled_highlight_ids.append(c.highlight_id)
                record = {
                    **base_record,
                    "action": "retry_scheduled",
                    "retryTimeMs": int(new_tm),
                }
                if outcome.retry_direction:
                    record["retryDirection"] = outcome.retry_direction
                if outcome.retry_offset_ms is not None:
                    record["retryOffsetMs"] = outcome.retry_offset_ms
                append_keyframe_verify_result(
                    project_id=project_id,
                    job_id=job_id,
                    record=record,
                )
                continue

        _drop_highlight_keyframes(h)
        stats.dropped_count += 1
        append_keyframe_verify_result(
            project_id=project_id,
            job_id=job_id,
            record={**base_record, "action": "dropped"},
        )

    total_dur = time.perf_counter() - t_start
    logger.info(
        "[keyframe_verify] phase=%s requested_mode=%s vision_unavailable=%s verified=%d dropped=%d skipped_prepare=%d retry_scheduled=%d retried_kept=%d retried_dropped=%d dur=%.1fs",
        phase,
        mode,
        pass_state.vision_unavailable,
        stats.verified_count,
        stats.dropped_count,
        stats.skipped_prepare_count,
        stats.retry_scheduled_count,
        stats.retried_kept_count,
        stats.retried_dropped_count,
        total_dur,
    )
    return (retry_times, scheduled_highlight_ids, stats, stats.verify_used_job)


def verify_keyframes_initial(
    *,
    session: Session,
    project_id: str,
    job_id: str,
    content_blocks: list[dict],
    output_language: str | None,
    mode: str,
    budget: VerifyBudget | None = None,
    pass_state: VerifyPassState | None = None,
) -> tuple[list[int], list[str], VerifyStats]:
    """First-pass verify. Returns (retry_times_ms, scheduled_highlight_ids, stats)."""

    b = budget or get_verify_budget()
    state = pass_state or VerifyPassState(requested_mode=mode)
    highlight_retry_used: dict[str, int] = {}
    retry_times, scheduled_ids, stats, _ = _run_verify_pass(
        session=session,
        project_id=project_id,
        job_id=job_id,
        content_blocks=content_blocks,
        output_language=output_language,
        mode=mode,
        budget=b,
        pass_state=state,
        phase="initial",
        verify_used_job=0,
        highlight_retry_used=highlight_retry_used,
    )
    return (retry_times, scheduled_ids, stats)


def verify_keyframes_after_retry(
    *,
    session: Session,
    project_id: str,
    job_id: str,
    content_blocks: list[dict],
    output_language: str | None,
    mode: str,
    retried_highlight_ids: list[str],
    budget: VerifyBudget | None = None,
    verify_used_job: int = 0,
    pass_state: VerifyPassState | None = None,
) -> VerifyStats:
    """Second-pass verify for retried highlights only."""

    if not retried_highlight_ids:
        return VerifyStats(verify_used_job=verify_used_job)

    b = budget or get_verify_budget()
    state = pass_state or VerifyPassState(requested_mode=mode)
    _, _, stats, _ = _run_verify_pass(
        session=session,
        project_id=project_id,
        job_id=job_id,
        content_blocks=content_blocks,
        output_language=output_language,
        mode=mode,
        budget=b,
        pass_state=state,
        phase="retry",
        retried_highlight_ids=set(retried_highlight_ids),
        verify_used_job=verify_used_job,
    )
    return stats


def verify_and_maybe_adjust_plan_keyframes(
    *,
    session: Session,
    project_id: str,
    job_id: str,
    content_blocks: list[dict],
    output_language: str | None,
    mode: str,
    budget: VerifyBudget,
) -> tuple[list[int], int, int]:
    """Deprecated wrapper for initial verify only. Prefer verify_keyframes_initial + verify_keyframes_after_retry."""

    retry_times, _, stats = verify_keyframes_initial(
        session=session,
        project_id=project_id,
        job_id=job_id,
        content_blocks=content_blocks,
        output_language=output_language,
        mode=mode,
        budget=budget,
    )
    return (retry_times, stats.verified_count, stats.dropped_count)
