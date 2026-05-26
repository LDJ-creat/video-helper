from __future__ import annotations

import json
import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from core.db.session import get_data_dir
from core.storage.safe_paths import PathTraversalBlockedError, validate_single_dir_name


def _now_ms() -> int:
	return int(time.time() * 1000)


def _json_dumps_compact(obj: object) -> str:
	return json.dumps(obj, ensure_ascii=False, separators=(",", ":"), default=str)


def _timing_path(*, project_id: str, task_id: str) -> Path:
	validate_single_dir_name(project_id)
	validate_single_dir_name(task_id)
	data_dir = get_data_dir().resolve()
	base_dir = (data_dir / project_id / "artifacts" / task_id).resolve()
	if not base_dir.is_relative_to(data_dir):
		raise PathTraversalBlockedError("timing dir escapes DATA_DIR")
	base_dir.mkdir(parents=True, exist_ok=True)
	return (base_dir / "timings.jsonl").resolve()


def append_pipeline_timing(
	*,
	project_id: str,
	task_id: str,
	step: str,
	duration_ms: int,
	status: str = "ok",
	details: dict | None = None,
) -> str | None:
	"""Append a timing event to the project artifact tree.

	This is best-effort and never raises to callers.
	"""

	try:
		path = _timing_path(project_id=project_id, task_id=task_id)
		record: dict = {
			"tsMs": _now_ms(),
			"projectId": project_id,
			"taskId": task_id,
			"step": step,
			"status": status,
			"durationMs": int(max(0, duration_ms)),
		}
		if details:
			record["details"] = details
		with path.open("a", encoding="utf-8") as f:
			f.write(_json_dumps_compact(record) + "\n")
		return path.relative_to(get_data_dir().resolve()).as_posix()
	except Exception:
		return None


@contextmanager
def time_pipeline_step(
	*,
	project_id: str,
	task_id: str,
	step: str,
	details: dict | None = None,
) -> Iterator[dict]:
	"""Measure a pipeline step and persist the elapsed time on exit."""

	start = time.perf_counter()
	state = {"status": "ok", "details": details or {}}
	try:
		yield state
	except Exception as exc:
		state["status"] = "error"
		state["details"] = dict(state.get("details") or {})
		state["details"]["errorType"] = type(exc).__name__
		state["details"]["error"] = str(exc)
		raise
	finally:
		duration_ms = int(max(0.0, (time.perf_counter() - start) * 1000.0))
		append_pipeline_timing(
			project_id=project_id,
			task_id=task_id,
			step=step,
			duration_ms=duration_ms,
			status=str(state.get("status") or "ok"),
			details=state.get("details") if isinstance(state.get("details"), dict) else None,
		)
