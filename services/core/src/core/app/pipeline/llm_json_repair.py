from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Callable

from pydantic import ValidationError

from core.app.pipeline.analyze_provider import AnalyzeError, AnalyzeProvider
from core.contracts.error_codes import ErrorCode
from core.db.session import get_data_dir
from core.storage.safe_paths import PathTraversalBlockedError


DEFAULT_MAX_REPAIR_ATTEMPTS = 3


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


def _truncate_text(text: str, *, max_chars: int) -> str:
    if max_chars <= 0:
        return ""
    if len(text) <= max_chars:
        return text
    return text[:max_chars]


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def _json_dumps_compact(obj: object) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"), default=str)


def _coerce_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, (dict, list)):
        return _json_dumps_compact(value)
    if value is None:
        return ""
    return str(value)


def _is_analyze_error(obj: Exception) -> bool:
    return isinstance(obj, AnalyzeError)


def _read_dump_ref_text(dump_ref: object) -> str | None:
    if not isinstance(dump_ref, str) or not dump_ref.strip():
        return None
    data_dir = get_data_dir().resolve()
    path = (data_dir / dump_ref).resolve()
    if not path.is_relative_to(data_dir):
        return None
    if not path.exists() or not path.is_file():
        return None
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return None


def _write_json_log(*, scope: str, filename: str, payload: dict) -> str:
    data_dir = get_data_dir().resolve()
    base = (data_dir / "logs" / "llm_json_repair" / scope).resolve()
    if not base.is_relative_to(data_dir):
        raise PathTraversalBlockedError("repair log dir escapes DATA_DIR")
    base.mkdir(parents=True, exist_ok=True)
    path = (base / filename).resolve()
    if not path.is_relative_to(data_dir):
        raise PathTraversalBlockedError("repair log file escapes DATA_DIR")
    content = _json_dumps_compact(payload)
    path.write_text(content, encoding="utf-8", errors="ignore")
    return path.relative_to(data_dir).as_posix()


def _validation_issue_from_exception(exc: Exception, *, output_keys: list[str] | None = None) -> dict:
    issue: dict[str, Any] = {
        "reason": "invalid_llm_output",
        "error": str(exc),
        "exceptionType": type(exc).__name__,
        "validationKind": "schema" if isinstance(exc, ValidationError) else "semantic",
        "validationMessage": str(exc),
    }
    if isinstance(exc, ValidationError):
        issue["validation"] = True
        issue["errors"] = exc.errors()
    if output_keys:
        issue["outputKeys"] = output_keys
    return issue


def build_repair_request(
    *,
    task_name: str,
    schema_summary: str,
    source_text: str,
    validation_issue: dict,
    attempt: int,
    max_attempts: int,
    output_language: str | None = None,
) -> dict:
    lang = (output_language or "").strip()
    lang_hint = ""
    if lang and lang.lower() != "auto":
        lang_hint = f" Preserve the user-visible language as {lang}."

    system = (
        f"You repair malformed JSON for the {task_name} task. "
        "Return ONLY one JSON object, no markdown, no code fences, no commentary. "
        "Preserve the intended content and fix only structure/schema issues. "
        f"The repaired output MUST satisfy this schema: {schema_summary}."
        f"{lang_hint}"
    )
    user_payload = {
        "task": task_name,
        "attempt": int(attempt),
        "maxAttempts": int(max_attempts),
        "sourceOutput": source_text,
        "validationIssue": validation_issue,
        "schemaSummary": schema_summary,
        "instructions": [
            "Return exactly one JSON object.",
            "Do not add explanations, markdown, or code fences.",
            "Keep the original meaning whenever possible.",
            "Fix missing or malformed fields so the result matches the schema.",
        ],
    }
    if lang:
        user_payload["outputLanguage"] = lang
    return {
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": _json_dumps_compact(user_payload)},
        ],
        "system": system,
        "userPayload": user_payload,
    }


def repair_json_with_llm(
    *,
    provider: AnalyzeProvider,
    task_name: str,
    schema_summary: str,
    source_text: str,
    validation_issue: dict,
    validate_and_normalize: Callable[[dict], dict],
    repair_task_name: str | None = None,
    output_language: str | None = None,
    max_attempts: int = DEFAULT_MAX_REPAIR_ATTEMPTS,
    log_scope: str | None = None,
) -> dict:
    repair_task = repair_task_name or f"{task_name}_repair"
    scope = log_scope or task_name

    current_source = _truncate_text(_coerce_text(source_text), max_chars=_env_int("LLM_JSON_REPAIR_MAX_CHARS", 100_000))
    current_issue = dict(validation_issue or {"reason": "invalid_llm_output"})
    last_error: dict[str, Any] | None = None

    max_attempts = max(1, min(int(max_attempts), 3))

    for attempt in range(1, max_attempts + 1):
        request = build_repair_request(
            task_name=task_name,
            schema_summary=schema_summary,
            source_text=current_source,
            validation_issue=current_issue,
            attempt=attempt,
            max_attempts=max_attempts,
            output_language=output_language,
        )

        trace: dict[str, Any] = {
            "task": task_name,
            "repairTask": repair_task,
            "attempt": attempt,
            "maxAttempts": max_attempts,
            "sourceOutput": current_source,
            "validationIssue": current_issue,
            "request": request,
            "status": "pending",
        }

        try:
            repaired = provider.generate_json(repair_task, {"messages": request["messages"]})
        except AnalyzeError as exc:
            details = dict(exc.details or {})
            raw_text = _read_dump_ref_text(details.get("dumpRef"))
            trace["repairError"] = exc.to_error()
            if raw_text is not None:
                trace["repairRawOutput"] = _truncate_text(raw_text, max_chars=_env_int("LLM_JSON_REPAIR_MAX_CHARS", 100_000))
            trace["status"] = "repair-error"
            trace_ref = _write_json_log(
                scope=scope,
                filename=f"{_now_ms()}-attempt{attempt}-{_hash_text(_json_dumps_compact(trace))[:12]}.json",
                payload=trace,
            )
            trace["traceRef"] = trace_ref
            last_error = exc.to_error()

            if details.get("reason") == "invalid_llm_output" and raw_text:
                current_source = _truncate_text(raw_text, max_chars=_env_int("LLM_JSON_REPAIR_MAX_CHARS", 100_000))
                current_issue = _validation_issue_from_exception(exc, output_keys=[str(k) for k in details.keys()])
                continue
            raise

        trace["repairResponse"] = repaired

        try:
            validated = validate_and_normalize(repaired)
        except Exception as exc:  # noqa: BLE001
            issue = _validation_issue_from_exception(exc, output_keys=sorted([str(k) for k in repaired.keys()]))
            trace["validationError"] = issue
            trace["status"] = "validation-error"
            trace_ref = _write_json_log(
                scope=scope,
                filename=f"{_now_ms()}-attempt{attempt}-{_hash_text(_json_dumps_compact(trace))[:12]}.json",
                payload=trace,
            )
            trace["traceRef"] = trace_ref
            last_error = issue
            current_source = _truncate_text(_coerce_text(repaired), max_chars=_env_int("LLM_JSON_REPAIR_MAX_CHARS", 100_000))
            current_issue = issue
            continue

        trace["repairedOutput"] = validated
        trace["status"] = "success"
        trace_ref = _write_json_log(
            scope=scope,
            filename=f"{_now_ms()}-attempt{attempt}-{_hash_text(_json_dumps_compact(trace))[:12]}.json",
            payload=trace,
        )
        trace["traceRef"] = trace_ref
        return validated

    details: dict[str, Any] = {
        "reason": "invalid_llm_output",
        "task": task_name,
        "repairAttempts": max_attempts,
        "error": last_error.get("error") if isinstance(last_error, dict) else "repair exhausted",
    }
    if isinstance(last_error, dict) and last_error.get("validation"):
        details["validation"] = True
        details["errors"] = last_error.get("errors")
    raise AnalyzeError(code=ErrorCode.JOB_STAGE_FAILED, message="Invalid LLM output", details=details)
