from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from core.app.pipeline.chunk_summaries import estimate_duration_ms


def _read_json(path: Path) -> dict | list | None:
	if not path.exists() or not path.is_file():
		return None
	try:
		raw = path.read_text(encoding="utf-8")
		obj = json.loads(raw)
		return obj if isinstance(obj, (dict, list)) else None
	except Exception:
		return None


def _read_timings(path: Path) -> dict[str, dict[str, Any]]:
	stages: dict[str, dict[str, Any]] = {}
	if not path.exists():
		return stages
	try:
		for line in path.read_text(encoding="utf-8").splitlines():
			line = line.strip()
			if not line:
				continue
			try:
				record = json.loads(line)
			except json.JSONDecodeError:
				continue
			if not isinstance(record, dict):
				continue
			step = str(record.get("step") or "")
			if not step:
				continue
			prev = stages.get(step)
			duration_ms = int(record.get("durationMs") or 0)
			entry = {
				"durationMs": duration_ms,
				"status": str(record.get("status") or "ok"),
			}
			details = record.get("details")
			if isinstance(details, dict) and details:
				entry["details"] = details
			if prev is None:
				stages[step] = entry
			else:
				stages[step] = {
					"durationMs": int(prev.get("durationMs") or 0) + duration_ms,
					"status": entry["status"],
					**({"details": entry["details"]} if "details" in entry else {}),
				}
	except OSError:
		return stages
	return stages


def _count_llm_artifacts(plan_dir: Path) -> dict[str, int]:
	calls = 0
	repairs = 0
	retries = 0
	if not plan_dir.exists():
		return {"calls": 0, "repairs": 0, "retries": 0}
	for path in sorted(plan_dir.glob("*.json")):
		obj = _read_json(path)
		if not isinstance(obj, dict):
			continue
		calls += 1
		task = str(obj.get("task") or path.stem)
		if "repair" in task.lower():
			repairs += 1
		attempt = obj.get("attempt")
		if isinstance(attempt, int) and attempt > 1:
			retries += 1
	return {"calls": calls, "repairs": repairs, "retries": retries}


def _load_job_row(db_path: Path, job_id: str) -> dict[str, Any] | None:
	if not db_path.exists():
		return None
	con = sqlite3.connect(str(db_path))
	con.row_factory = sqlite3.Row
	try:
		cur = con.cursor()
		cur.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,))
		row = cur.fetchone()
		if row is None:
			return None
		return {k: row[k] for k in row.keys()}
	finally:
		con.close()


def _resolve_video_duration_ms(
	*,
	data_dir: Path,
	project_id: str,
	job_id: str,
	job_row: dict[str, Any],
) -> int | None:
	transcript_meta = job_row.get("transcript_meta")
	if isinstance(transcript_meta, str):
		try:
			transcript_meta = json.loads(transcript_meta)
		except json.JSONDecodeError:
			transcript_meta = None
	if isinstance(transcript_meta, dict):
		dm = transcript_meta.get("durationMs")
		if isinstance(dm, int) and dm > 0:
			return int(dm)

	transcript = job_row.get("transcript")
	if isinstance(transcript, str):
		try:
			transcript = json.loads(transcript)
		except json.JSONDecodeError:
			transcript = None
	if isinstance(transcript, dict):
		dm = estimate_duration_ms(transcript=transcript, transcript_meta=transcript_meta if isinstance(transcript_meta, dict) else None)
		if dm is not None and dm > 0:
			return int(dm)

	artifact_transcript = data_dir / project_id / "artifacts" / job_id / "transcript.json"
	obj = _read_json(artifact_transcript)
	if isinstance(obj, dict):
		dm = estimate_duration_ms(transcript=obj, transcript_meta=transcript_meta if isinstance(transcript_meta, dict) else None)
		if dm is not None and dm > 0:
			return int(dm)
	return None


def collect_job_metrics(
	*,
	data_dir: Path,
	job_id: str,
	project_id: str | None = None,
) -> dict[str, Any]:
	"""Collect L1 performance metrics for a job from SQLite and artifact files."""

	data_dir = data_dir.resolve()
	db_path = data_dir / "core.sqlite3"
	row = _load_job_row(db_path, job_id)
	if row is None:
		raise ValueError(f"job not found in sqlite: {job_id}")

	project_id = project_id or str(row.get("project_id") or "")
	if not project_id:
		raise ValueError(f"missing project_id for job {job_id}")

	created_at = row.get("created_at_ms")
	started_at = row.get("started_at_ms")
	finished_at = row.get("finished_at_ms")

	queue_wait_ms: int | None = None
	execution_ms: int | None = None
	e2e_ms: int | None = None
	if isinstance(created_at, int) and isinstance(started_at, int):
		queue_wait_ms = max(0, started_at - created_at)
	if isinstance(started_at, int) and isinstance(finished_at, int):
		execution_ms = max(0, finished_at - started_at)
	if isinstance(created_at, int) and isinstance(finished_at, int):
		e2e_ms = max(0, finished_at - created_at)

	video_duration_ms = _resolve_video_duration_ms(
		data_dir=data_dir,
		project_id=project_id,
		job_id=job_id,
		job_row=row,
	)

	speed_factor: float | None = None
	if execution_ms is not None and video_duration_ms is not None and video_duration_ms > 0:
		speed_factor = round(execution_ms / float(video_duration_ms), 4)

	timings_path = data_dir / project_id / "artifacts" / job_id / "timings.jsonl"
	stages = _read_timings(timings_path)

	plan_dir = data_dir / project_id / "artifacts" / "plan" / job_id / "llm_requests"
	llm = _count_llm_artifacts(plan_dir)

	chain_path = data_dir / project_id / "artifacts" / "plan" / job_id / "analysis_chain.json"
	chain = _read_json(chain_path)
	if isinstance(chain, dict) and isinstance(chain.get("durationMs"), int):
		llm.setdefault("chainDurationMs", int(chain["durationMs"]))

	error = row.get("error")
	if isinstance(error, str):
		try:
			error = json.loads(error)
		except json.JSONDecodeError:
			error = {"message": error}

	return {
		"jobId": job_id,
		"projectId": project_id,
		"status": str(row.get("status") or ""),
		"stage": str(row.get("stage") or ""),
		"error": error if isinstance(error, dict) else None,
		"videoDurationMs": video_duration_ms,
		"queueWaitMs": queue_wait_ms,
		"executionMs": execution_ms,
		"e2eMs": e2e_ms,
		"speedFactor": speed_factor,
		"stages": stages,
		"llm": llm,
		"timingsRef": timings_path.relative_to(data_dir).as_posix() if timings_path.exists() else None,
	}
