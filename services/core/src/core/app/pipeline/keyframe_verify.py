from __future__ import annotations

import base64
import json
import os
import random
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from core.app.pipeline.analyze_provider import AnalyzeError, AnalyzeProvider, llm_provider_for_jobs
from core.contracts.error_codes import ErrorCode
from core.db.models.asset import Asset
from core.db.session import get_data_dir


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
    return (_env_str("KEYFRAME_VERIFY_MODE") or "off").strip().lower()


def get_verify_threshold() -> float:
    raw = (_env_str("KEYFRAME_VERIFY_CONFIDENCE_THRESHOLD") or "0.4").strip()
    try:
        return float(raw)
    except Exception:
        return 0.4


@dataclass
class VerifyBudget:
    max_verify_per_highlight: int
    max_verify_per_job: int
    retry_max: int
    local_search_window_ms: int


def get_verify_budget() -> VerifyBudget:
    return VerifyBudget(
        max_verify_per_highlight=max(0, _env_int("KEYFRAME_VERIFY_MAX_PER_HIGHLIGHT", 1)),
        max_verify_per_job=max(0, _env_int("KEYFRAME_VERIFY_MAX_PER_JOB", 5)),
        retry_max=max(0, _env_int("KEYFRAME_RETRY_MAX", 1)),
        local_search_window_ms=max(1_000, _env_int("KEYFRAME_LOCAL_SEARCH_WINDOW_MS", 10_000)),
    )


def _run_tesseract_ocr(*, image_abs: Path, timeout_s: int = 15) -> str | None:
    exe = shutil.which("tesseract")
    if not exe:
        return None

    try:
        # stdout output mode
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
    # Keep conservative cap (providers may reject huge payloads)
    max_bytes = max(50_000, _env_int("KEYFRAME_VERIFY_IMAGE_MAX_BYTES", 400_000))
    if len(b) > max_bytes:
        # Truncate is unsafe for JPEG; skip multimodal in this case.
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


def _call_llm_with_backoff(*, provider: AnalyzeProvider, messages: list[dict]) -> dict:
    max_attempts = max(1, _env_int("KEYFRAME_VERIFY_MAX_ATTEMPTS", 2))
    attempt = 0
    while True:
        attempt += 1
        try:
            res = provider.generate_json("keyframe_verify", {"messages": messages})
            if not isinstance(res, dict):
                raise AnalyzeError(
                    code=ErrorCode.JOB_STAGE_FAILED,
                    message="Invalid LLM output",
                    details={"reason": "invalid_llm_output", "task": "keyframe_verify", "outputType": type(res).__name__},
                )
            return res
        except AnalyzeError as e:
            reason = str((e.details or {}).get("reason") or "")
            if reason in {"rate_limited", "upstream_error", "timeout"} and attempt < max_attempts:
                sleep_s = min(6.0, 0.5 * (2 ** (attempt - 1)))
                sleep_s = sleep_s * (0.8 + random.random() * 0.4)
                time.sleep(sleep_s)
                continue
            raise


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
        "Return ONLY one JSON object (no markdown) with keys: keep(boolean), confidence(number 0..1), reason(string). "
        "Rules: keep=true only if the image likely contains meaningful visual info (slide/diagram/code/UI/formula) that supports the highlight. "
        "If OCR text is empty or irrelevant, prefer keep=false. "
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
        "Return ONLY one JSON object (no markdown) with keys: keep(boolean), confidence(number 0..1), reason(string). "
        "keep=true only if the image contains meaningful visual info supporting the highlight." 
        + (" " + lang_hint if lang_hint else "")
    )

    # OpenAI-compatible multimodal message shape.
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


def verify_and_maybe_adjust_plan_keyframes(
    *,
    session: Session,
    content_blocks: list[dict],
    output_language: str | None,
    mode: str,
    budget: VerifyBudget,
) -> tuple[list[int], int, int]:
    """Verify keyframes and adjust plan in-place.

    Returns: (new_times_to_extract, verified_count, dropped_count)
    """

    if mode not in {"ocr", "multimodal"}:
        return ([], 0, 0)

    resolved = llm_provider_for_jobs()
    if resolved is None:
        raise AnalyzeError(
            code=ErrorCode.JOB_STAGE_FAILED,
            message="LLM credentials missing",
            details={"reason": "missing_credentials", "task": "keyframe_verify"},
        )
    provider: AnalyzeProvider = resolved

    threshold = float(get_verify_threshold())

    verify_used_job = 0
    verified_count = 0
    dropped_count = 0
    new_times: list[int] = []

    for b in content_blocks:
        if verify_used_job >= budget.max_verify_per_job:
            break
        if not isinstance(b, dict):
            continue
        hls = b.get("highlights")
        if not isinstance(hls, list):
            continue

        for h in hls:
            if verify_used_job >= budget.max_verify_per_job:
                break
            if not isinstance(h, dict):
                continue

            kfs = h.get("keyframes")
            if not isinstance(kfs, list) or not kfs:
                continue

            # Trigger only on low-confidence (or explicit) highlights.
            conf = _coerce_confidence(h.get("keyframeConfidence"))
            if conf is None or conf >= threshold:
                continue

            # Only verify at most once per highlight (budget).
            if budget.max_verify_per_highlight <= 0:
                continue

            kf0 = kfs[0] if isinstance(kfs[0], dict) else None
            if not isinstance(kf0, dict):
                continue

            tm = kf0.get("timeMs")
            if not isinstance(tm, int):
                continue

            asset_id = kf0.get("assetId")
            if not isinstance(asset_id, str) or not asset_id:
                # Not extractable yet.
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

            keep: bool | None = None
            try:
                if mode == "ocr":
                    ocr_text = _run_tesseract_ocr(image_abs=image_abs)
                    # If OCR dependency is missing, skip silently (do not fail the job).
                    if ocr_text is None:
                        continue
                    messages = build_verify_request_text_only(
                        highlight_text=highlight_text,
                        time_range=(int(hs), int(he)),
                        ocr_text=ocr_text,
                        output_language=output_language,
                    )
                    res = _call_llm_with_backoff(provider=provider, messages=messages)
                else:
                    data_url = _encode_image_data_url(image_abs=image_abs)
                    if data_url is None:
                        continue
                    messages = build_verify_request_multimodal(
                        highlight_text=highlight_text,
                        time_range=(int(hs), int(he)),
                        image_data_url=data_url,
                        output_language=output_language,
                    )
                    res = _call_llm_with_backoff(provider=provider, messages=messages)

                keep = bool(res.get("keep")) if isinstance(res, dict) and "keep" in res else None
            finally:
                verify_used_job += 1
                verified_count += 1

            if keep is True:
                continue

            # Not kept: attempt one retry by selecting a nearby time within the local search window.
            allow_retry = budget.retry_max > 0
            if allow_retry:
                mid = int((int(hs) + int(he)) // 2)
                direction = 1 if mid >= int(tm) else -1
                step = min(int(budget.local_search_window_ms), abs(mid - int(tm)))
                if step <= 0:
                    step = int(budget.local_search_window_ms)
                new_tm = int(tm) + direction * int(step)
                new_tm = _clamp_int(new_tm, int(hs), int(he) - 1)
                if new_tm != int(tm):
                    # Replace keyframes with the new candidate (assetId will be backfilled after extraction).
                    h["keyframes"] = [{"timeMs": int(new_tm)}]
                    h["keyframe"] = {"timeMs": int(new_tm)}
                    new_times.append(int(new_tm))
                    budget.retry_max -= 1
                    continue

            # No retry possible: drop keyframes.
            h["keyframes"] = []
            h["keyframe"] = None
            dropped_count += 1

    return (new_times, verified_count, dropped_count)
