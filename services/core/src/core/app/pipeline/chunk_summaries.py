from __future__ import annotations

import json
import math
import os
import random
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from core.app.pipeline.analyze_provider import AnalyzeError, AnalyzeProvider, llm_provider_for_jobs
from core.contracts.error_codes import ErrorCode
from core.db.session import get_data_dir
from core.storage.safe_paths import PathTraversalBlockedError


CHUNKING_VERSION = 1
PROMPTS_VERSION = 1


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


def _clamp_int(v: int, lo: int, hi: int) -> int:
    return max(int(lo), min(int(v), int(hi)))


def _as_int(v: object) -> int | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v)
    if isinstance(v, str):
        s = v.strip()
        if s.isdigit() or (s.startswith("-") and s[1:].isdigit()):
            try:
                return int(s)
            except Exception:
                return None
    return None


def estimate_duration_ms(*, transcript: dict, transcript_meta: dict | None = None) -> int | None:
    if isinstance(transcript_meta, dict):
        dm = transcript_meta.get("durationMs")
        if isinstance(dm, int) and dm > 0:
            return int(dm)

    segments = transcript.get("segments") if isinstance(transcript, dict) else None
    if not isinstance(segments, list) or not segments:
        return None

    end_ms: int | None = None
    for s in segments:
        if not isinstance(s, dict):
            continue
        e = s.get("endMs")
        if isinstance(e, int) and e > 0:
            end_ms = e if end_ms is None else max(end_ms, int(e))
    return int(end_ms) if end_ms is not None else None


def should_use_long_video_path(*, duration_ms: int | None, segments: list[dict], total_chars: int) -> bool:
    min_ms = max(0, _env_int("LONG_VIDEO_MIN_MS", 20 * 60 * 1000))
    min_segments = max(0, _env_int("LONG_VIDEO_MIN_SEGMENTS", 1800))
    min_chars = max(0, _env_int("LONG_VIDEO_MIN_CHARS", 120_000))

    if duration_ms is not None and duration_ms >= min_ms:
        return True
    if len(segments) >= min_segments:
        return True
    if total_chars >= min_chars:
        return True
    return False


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    start_ms: int
    end_ms: int
    segments: list[dict]


class ChunkPoint(BaseModel):
    text: str
    importance: int = 2  # 1|2|3


class ChunkTerm(BaseModel):
    term: str
    definition: str | None = None


class ChunkKeyMoment(BaseModel):
    timeMs: int
    label: str


class ChunkSummary(BaseModel):
    chunkId: str
    startMs: int
    endMs: int
    summary: str
    points: list[ChunkPoint] = Field(default_factory=list)
    terms: list[ChunkTerm] = Field(default_factory=list)
    keyMoments: list[ChunkKeyMoment] = Field(default_factory=list)


def _model_validate(cls: type[BaseModel], obj: Any) -> BaseModel:
    if hasattr(cls, "model_validate"):
        return cls.model_validate(obj)  # type: ignore[attr-defined]
    return cls.parse_obj(obj)  # type: ignore[attr-defined]


def _model_dump(model: BaseModel) -> dict:
    if hasattr(model, "model_dump"):
        return model.model_dump()  # type: ignore[attr-defined]
    return model.dict()  # type: ignore[attr-defined]


def _json_dumps_compact(obj: object) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"), default=str)


def _write_json_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".{_now_ms()}.tmp")
    data = _json_dumps_compact(payload).encode("utf-8")
    tmp.write_bytes(data)
    # Validate the just-written JSON to avoid leaving corrupt partials.
    try:
        json.loads(tmp.read_text("utf-8"))
    except Exception:
        try:
            tmp.unlink(missing_ok=True)  # type: ignore[call-arg]
        except Exception:
            pass
        raise
    tmp.replace(path)


def _read_json_if_ok(path: Path) -> dict | None:
    try:
        if not path.exists() or not path.is_file():
            return None
        return json.loads(path.read_text("utf-8"))
    except Exception:
        return None


def _chunk_window_ms(*, duration_ms: int) -> int:
    # Auto mode only (simplify config surface).
    target_count = _clamp_int(_env_int("CHUNK_TARGET_COUNT", 24), 1, 500)
    min_window = _clamp_int(_env_int("CHUNK_MIN_WINDOW_MS", 4 * 60 * 1000), 30_000, 60 * 60 * 1000)
    max_window = _clamp_int(_env_int("CHUNK_MAX_WINDOW_MS", 8 * 60 * 1000), min_window, 60 * 60 * 1000)

    if duration_ms <= 0:
        return int(min_window)

    window = int(math.ceil(float(duration_ms) / float(target_count)))
    return _clamp_int(window, int(min_window), int(max_window))


def chunk_transcript_segments(*, transcript: dict, duration_ms: int | None) -> tuple[int, list[Chunk]]:
    segments_raw = transcript.get("segments") if isinstance(transcript, dict) else None
    if not isinstance(segments_raw, list):
        return 0, []

    segments: list[dict] = [s for s in segments_raw if isinstance(s, dict)]
    if not segments:
        return 0, []

    # Sort by startMs to be robust to provider quirks.
    segments_sorted = sorted(
        segments,
        key=lambda s: int(s.get("startMs")) if isinstance(s.get("startMs"), int) else 0,
    )

    dur = duration_ms
    if dur is None:
        dur = estimate_duration_ms(transcript=transcript)
    if dur is None:
        # Fallback to last segment end.
        last_end = None
        for s in segments_sorted:
            e = s.get("endMs")
            if isinstance(e, int) and e > 0:
                last_end = e if last_end is None else max(last_end, int(e))
        dur = int(last_end) if last_end is not None else 0

    window_ms = _chunk_window_ms(duration_ms=int(dur))

    chunks: list[Chunk] = []
    cur: list[dict] = []
    cur_start: int | None = None
    cur_end: int | None = None

    for s in segments_sorted:
        ss = s.get("startMs")
        ee = s.get("endMs")
        if not isinstance(ss, int) or not isinstance(ee, int) or ee <= ss:
            continue

        if cur_start is None:
            cur_start = int(ss)
            cur_end = int(ee)
            cur = [s]
            continue

        assert cur_end is not None

        # If adding this segment exceeds the window, flush current chunk.
        if int(ee) - int(cur_start) > int(window_ms) and cur:
            start_ms = int(cur_start)
            end_ms = int(cur_end)
            if end_ms <= start_ms:
                end_ms = start_ms + 1
            chunk_id = f"c_{start_ms}_{end_ms}"
            chunks.append(Chunk(chunk_id=chunk_id, start_ms=start_ms, end_ms=end_ms, segments=cur))

            # Start new chunk.
            cur_start = int(ss)
            cur_end = int(ee)
            cur = [s]
        else:
            cur.append(s)
            cur_end = max(int(cur_end), int(ee))

    if cur_start is not None and cur:
        start_ms = int(cur_start)
        end_ms = int(cur_end or (start_ms + 1))
        if end_ms <= start_ms:
            end_ms = start_ms + 1
        chunk_id = f"c_{start_ms}_{end_ms}"
        chunks.append(Chunk(chunk_id=chunk_id, start_ms=start_ms, end_ms=end_ms, segments=cur))

    return int(window_ms), chunks


def _chunk_text(segments: list[dict], *, max_chars: int) -> str:
    max_chars = max(200, int(max_chars))
    out: list[str] = []
    total = 0
    for s in segments:
        if not isinstance(s, dict):
            continue
        ss = s.get("startMs")
        ee = s.get("endMs")
        text = s.get("text")
        if not isinstance(ss, int) or not isinstance(ee, int):
            continue
        if not isinstance(text, str):
            text = ""
        line = f"{int(ss)}-{int(ee)}: {text.strip()}"
        if not line.strip():
            continue
        if total + len(line) + 1 > max_chars:
            break
        out.append(line)
        total += len(line) + 1
    return "\n".join(out)


def _build_chunk_summary_request(*, chunk: Chunk, output_language: str | None) -> dict:
    lang = (output_language or "").strip()
    lang_hint = ""
    if lang and lang.lower() != "auto":
        lang_hint = f"Write ALL user-visible strings in {lang}."

    max_chars = _env_int("CHUNK_MAX_CHARS", 10_000)
    max_points = _clamp_int(_env_int("CHUNK_MAX_POINTS", 6), 0, 20)
    max_terms = _clamp_int(_env_int("CHUNK_MAX_TERMS", 4), 0, 20)
    max_moments = _clamp_int(_env_int("CHUNK_MAX_KEY_MOMENTS", 3), 0, 10)
    summary_max_chars = _clamp_int(_env_int("CHUNK_SUMMARY_MAX_CHARS", 600), 50, 5000)

    system = (
        "You are summarizing ONE chunk of a long video transcript for downstream chapter planning. "
        "Return ONLY one JSON object (no markdown). "
        "Do NOT restate the transcript sentence-by-sentence. Produce compact learning notes. "
        "Output JSON MUST be an object with top-level keys: chunkId,startMs,endMs,summary,points,terms,keyMoments. "
        "Do NOT nest these under another key. Do NOT rename keys. "
        "Field meanings: "
        "- summary: a compact learning-oriented summary of this chunk (not verbatim). "
        "- points: key takeaways from this chunk (each one is a short statement). "
        "- terms: ONLY important domain terms/abbreviations introduced or heavily used in this chunk. "
        "- keyMoments: a few timestamp anchors where a screenshot/slide/diagram/code change is most useful. "
        "Schema: "
        "- points[] item: {text:string, importance:1|2|3}. importance=3 means critical; 2 normal; 1 minor. "
        "- terms[] item: {term:string, definition?:string}. definition should be SHORT and only when disambiguation helps. "
        "- keyMoments[] item: {timeMs:int, label:string}. label is a short reason/title. timeMs must be within [startMs,endMs). "
        f"Hard limits: summary length <= {summary_max_chars} chars; points <= {max_points}; terms <= {max_terms}; keyMoments <= {max_moments}. "
        + (" " + lang_hint if lang_hint else "")
    )

    user_payload = {
        "task": "chunk_summary",
        "chunkId": chunk.chunk_id,
        "startMs": int(chunk.start_ms),
        "endMs": int(chunk.end_ms),
        "outputLanguage": lang or "auto",
        "transcript": _chunk_text(chunk.segments, max_chars=max_chars),
    }

    return {
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": _json_dumps_compact(user_payload)},
        ],
        "system": system,
        "userPayload": user_payload,
    }


def _normalize_chunk_summary(payload: dict, *, chunk: Chunk) -> dict:
    # Ensure required fields + bounds.
    payload["chunkId"] = chunk.chunk_id
    payload["startMs"] = int(chunk.start_ms)
    payload["endMs"] = int(chunk.end_ms)

    # summary (required): coerce to string and cap size.
    summary_max_chars = _clamp_int(_env_int("CHUNK_SUMMARY_MAX_CHARS", 600), 50, 5000)
    summary = payload.get("summary")
    if not isinstance(summary, str):
        summary = str(summary or "")
    payload["summary"] = summary.strip()[: int(summary_max_chars)]

    # points: accept list[str|dict], normalize structure, clamp importance, cap count.
    max_points = _clamp_int(_env_int("CHUNK_MAX_POINTS", 6), 0, 20)
    points_raw = payload.get("points")
    if not isinstance(points_raw, list):
        points_raw = []
    points_out: list[dict] = []
    for p in points_raw:
        if len(points_out) >= max_points:
            break
        if isinstance(p, str):
            text = p.strip()
            if text:
                points_out.append({"text": text[:400], "importance": 2})
            continue
        if not isinstance(p, dict):
            continue
        text_v = p.get("text")
        text = text_v.strip() if isinstance(text_v, str) else str(text_v or "").strip()
        if not text:
            continue
        imp = _as_int(p.get("importance"))
        if imp is None:
            imp = 2
        imp = _clamp_int(int(imp), 1, 3)
        points_out.append({"text": text[:400], "importance": int(imp)})
    payload["points"] = points_out

    # terms: accept list[str|dict], keep few, coerce definition.
    max_terms = _clamp_int(_env_int("CHUNK_MAX_TERMS", 4), 0, 20)
    terms_raw = payload.get("terms")
    if not isinstance(terms_raw, list):
        terms_raw = []
    terms_out: list[dict] = []
    for t in terms_raw:
        if len(terms_out) >= max_terms:
            break
        if isinstance(t, str):
            term = t.strip()
            if term:
                terms_out.append({"term": term[:80]})
            continue
        if not isinstance(t, dict):
            continue
        term_v = t.get("term")
        term = term_v.strip() if isinstance(term_v, str) else str(term_v or "").strip()
        if not term:
            continue
        d_v = t.get("definition")
        if d_v is None:
            terms_out.append({"term": term[:80]})
            continue
        d = d_v.strip() if isinstance(d_v, str) else str(d_v).strip()
        d2 = d[:200] if d else ""
        if d2:
            terms_out.append({"term": term[:80], "definition": d2})
        else:
            terms_out.append({"term": term[:80]})
    payload["terms"] = terms_out

    # Clamp keyMoments times.
    max_moments = _clamp_int(_env_int("CHUNK_MAX_KEY_MOMENTS", 3), 0, 10)
    km = payload.get("keyMoments")
    if not isinstance(km, list):
        km = []

    km2: list[dict] = []
    for x in km:
        if len(km2) >= max_moments:
            break
        if not isinstance(x, dict):
            continue
        tm = _as_int(x.get("timeMs"))
        if tm is None:
            continue
        tm2 = max(int(chunk.start_ms), min(int(tm), int(chunk.end_ms) - 1))
        label_v = x.get("label")
        label = label_v.strip() if isinstance(label_v, str) else str(label_v or "").strip()
        if not label:
            continue
        km2.append({"timeMs": int(tm2), "label": label[:120]})
    payload["keyMoments"] = km2

    return payload


_THREAD_LOCAL = threading.local()


def _get_thread_provider(*, transport: object | None = None) -> AnalyzeProvider:
    p = getattr(_THREAD_LOCAL, "provider", None)
    if p is not None:
        return p
    resolved = llm_provider_for_jobs(transport=transport)  # type: ignore[arg-type]
    if resolved is None:
        raise AnalyzeError(
            code=ErrorCode.JOB_STAGE_FAILED,
            message="LLM credentials missing",
            details={"reason": "missing_credentials", "task": "chunk_summary"},
        )
    _THREAD_LOCAL.provider = resolved
    return resolved


def _call_llm_with_backoff(*, provider: AnalyzeProvider, task: str, messages: list[dict]) -> dict:
    max_attempts = _clamp_int(_env_int("CHUNK_LLM_MAX_ATTEMPTS", 3), 1, 10)
    attempt = 0
    while True:
        attempt += 1
        try:
            return provider.generate_json(task, {"messages": messages})
        except AnalyzeError as e:
            # Retry on rate limit/upstream for chunk summaries only.
            reason = str((e.details or {}).get("reason") or "")
            if reason in {"rate_limited", "upstream_error", "timeout"} and attempt < max_attempts:
                # jittered exponential backoff
                sleep_s = min(8.0, 0.5 * (2 ** (attempt - 1)))
                sleep_s = sleep_s * (0.8 + random.random() * 0.4)
                time.sleep(sleep_s)
                continue
            raise


def ensure_chunk_summaries(
    *,
    project_id: str,
    job_id: str,
    transcript: dict,
    transcript_meta: dict | None,
    output_language: str | None,
    duration_ms: int | None = None,
    llm_transport: object | None = None,
) -> list[dict]:
    """Compute (or reuse) chunk summaries for long-video planning.

    Persistence layout:
      DATA_DIR/<projectId>/artifacts/<jobId>/chunk_summaries/
        manifest.json
        chunk_<chunkId>.json

    The function is deterministic w.r.t transcript + window settings.
    """

    data_dir = get_data_dir().resolve()
    base_dir = (data_dir / project_id / "artifacts" / job_id / "chunk_summaries").resolve()
    if not base_dir.is_relative_to(data_dir):
        raise PathTraversalBlockedError("chunk summaries dir escapes DATA_DIR")
    base_dir.mkdir(parents=True, exist_ok=True)

    transcript_sha = None
    if isinstance(transcript_meta, dict) and isinstance(transcript_meta.get("sha256"), str):
        transcript_sha = transcript_meta.get("sha256")

    if duration_ms is None:
        duration_ms = estimate_duration_ms(transcript=transcript, transcript_meta=transcript_meta)

    window_ms, chunks = chunk_transcript_segments(transcript=transcript, duration_ms=duration_ms)
    if not chunks:
        return []

    manifest_path = (base_dir / "manifest.json").resolve()
    if not manifest_path.is_relative_to(data_dir):
        raise PathTraversalBlockedError("chunk summaries manifest escapes DATA_DIR")

    effective_lang = (output_language or "").strip() or "auto"

    existing_manifest = _read_json_if_ok(manifest_path)
    if isinstance(existing_manifest, dict):
        if (
            existing_manifest.get("chunkingVersion") == CHUNKING_VERSION
            and existing_manifest.get("promptsVersion") == PROMPTS_VERSION
            and existing_manifest.get("windowMs") == int(window_ms)
            and existing_manifest.get("outputLanguage") == effective_lang
            and (transcript_sha is None or existing_manifest.get("transcriptSha256") == transcript_sha)
        ):
            # Reuse if all expected chunk files exist and validate.
            existing_chunks = existing_manifest.get("chunks")
            if isinstance(existing_chunks, list) and existing_chunks:
                out: list[dict] = []
                ok = True
                for c in existing_chunks:
                    if not isinstance(c, dict):
                        ok = False
                        break
                    cid = c.get("chunkId")
                    if not isinstance(cid, str) or not cid:
                        ok = False
                        break
                    p = (base_dir / f"chunk_{cid}.json").resolve()
                    if not p.is_relative_to(data_dir):
                        ok = False
                        break
                    payload = _read_json_if_ok(p)
                    if not isinstance(payload, dict):
                        ok = False
                        break
                    try:
                        parsed = _model_validate(ChunkSummary, payload)
                    except Exception:
                        ok = False
                        break
                    out.append(_model_dump(parsed))
                if ok:
                    return out

    # Ensure manifest is written first (defines the required chunk set).
    manifest = {
        "chunkingVersion": CHUNKING_VERSION,
        "promptsVersion": PROMPTS_VERSION,
        "windowMs": int(window_ms),
        "outputLanguage": effective_lang,
        "transcriptSha256": transcript_sha,
        "chunks": [
            {"chunkId": c.chunk_id, "startMs": int(c.start_ms), "endMs": int(c.end_ms)} for c in chunks
        ],
    }
    _write_json_atomic(manifest_path, manifest)

    # Placeholder mode for tests/dev.
    if (os.environ.get("CHUNK_SUMMARY_PROVIDER") or "").strip().lower() == "placeholder":
        out: list[dict] = []
        for c in chunks:
            payload = {
                "chunkId": c.chunk_id,
                "startMs": int(c.start_ms),
                "endMs": int(c.end_ms),
                "summary": f"Chunk {c.chunk_id} summary (placeholder)",
                "points": [{"text": "placeholder point", "importance": 2}],
                "terms": [],
                "keyMoments": [],
            }
            p = (base_dir / f"chunk_{c.chunk_id}.json").resolve()
            _write_json_atomic(p, payload)
            out.append(payload)
        return out

    max_concurrency = _clamp_int(_env_int("CHUNK_LLM_MAX_CONCURRENCY", 5), 1, 32)

    # Worker fn: read cache, else call LLM and persist.
    def compute_one(c: Chunk) -> dict:
        p = (base_dir / f"chunk_{c.chunk_id}.json").resolve()
        if not p.is_relative_to(data_dir):
            raise PathTraversalBlockedError("chunk output escapes DATA_DIR")

        existing = _read_json_if_ok(p)
        if isinstance(existing, dict):
            try:
                parsed = _model_validate(ChunkSummary, existing)
                return _model_dump(parsed)
            except Exception:
                pass

        req = _build_chunk_summary_request(chunk=c, output_language=output_language)
        messages = req.get("messages")
        if not isinstance(messages, list):
            raise AnalyzeError(
                code=ErrorCode.JOB_STAGE_FAILED,
                message="Invalid chunk summary request",
                details={"reason": "chunk_summary_request_invalid"},
            )

        provider = _get_thread_provider(transport=llm_transport)
        raw = _call_llm_with_backoff(provider=provider, task="chunk_summary", messages=messages)
        if not isinstance(raw, dict):
            raise AnalyzeError(
                code=ErrorCode.JOB_STAGE_FAILED,
                message="Invalid LLM output",
                details={"reason": "invalid_llm_output", "task": "chunk_summary", "outputType": type(raw).__name__},
            )

        raw = _normalize_chunk_summary(raw, chunk=c)
        try:
            parsed = _model_validate(ChunkSummary, raw)
        except ValidationError as e:
            raise AnalyzeError(
                code=ErrorCode.JOB_STAGE_FAILED,
                message="Invalid LLM output (schema)",
                details={"reason": "invalid_llm_output", "task": "chunk_summary", "error": str(e), "validation": True},
            )
        out = _model_dump(parsed)
        _write_json_atomic(p, out)
        return out

    # Bounded concurrency in threads.
    from concurrent.futures import ThreadPoolExecutor, as_completed

    out_by_id: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=max_concurrency) as ex:
        futs = {ex.submit(compute_one, c): c for c in chunks}
        for fut in as_completed(futs):
            c = futs[fut]
            out_by_id[c.chunk_id] = fut.result()

    # Preserve chronological order.
    ordered = [out_by_id[c.chunk_id] for c in chunks if c.chunk_id in out_by_id]
    return ordered
