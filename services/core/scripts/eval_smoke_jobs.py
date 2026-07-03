"""One-off evaluation for existing smoke DATA_DIR jobs (no LLM judge)."""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

import httpx


def _repo_root() -> Path:
	return Path(__file__).resolve().parents[2]


def _load_result_from_db(data_dir: Path, project_id: str) -> dict[str, Any] | None:
	db = data_dir / "core.sqlite3"
	if not db.exists():
		return None
	con = sqlite3.connect(str(db))
	con.row_factory = sqlite3.Row
	try:
		row = con.execute(
			"""
			SELECT r.result_id, r.project_id, r.schema_version, r.pipeline_version,
			       r.created_at_ms, r.content_blocks, r.mindmap, r.asset_refs
			FROM projects p
			JOIN results r ON r.result_id = p.latest_result_id
			WHERE p.project_id = ?
			""",
			(project_id,),
		).fetchone()
		if row is None:
			return None
		return {
			"resultId": row["result_id"],
			"projectId": row["project_id"],
			"schemaVersion": row["schema_version"],
			"pipelineVersion": row["pipeline_version"],
			"createdAtMs": row["created_at_ms"],
			"contentBlocks": json.loads(row["content_blocks"]) if isinstance(row["content_blocks"], str) else row["content_blocks"],
			"mindmap": json.loads(row["mindmap"]) if isinstance(row["mindmap"], str) else row["mindmap"],
			"assetRefs": json.loads(row["asset_refs"]) if isinstance(row["asset_refs"], str) else row["asset_refs"],
		}
	finally:
		con.close()


def evaluate_job(
	*,
	data_dir: Path,
	repo_root: Path,
	api_base: str,
	job_id: str,
	project_id: str,
	out_dir: Path,
	label: str,
) -> tuple[dict[str, Any], Path]:
	from core.app.benchmark.baseline import compare_to_baseline, load_baseline
	from core.app.benchmark.environment import collect_environment_snapshot
	from core.app.benchmark.http_client import get_latest_result
	from core.app.benchmark.job_metrics import collect_job_metrics
	from core.app.benchmark.keyframe_verify_metrics import collect_keyframe_verify_metrics
	from core.app.benchmark.report import build_benchmark_report, write_benchmark_report
	from core.app.benchmark.structure_score import score_result_structure

	job_metrics = collect_job_metrics(data_dir=data_dir, job_id=job_id, project_id=project_id)
	result: dict[str, Any] | None = None
	try:
		with httpx.Client(timeout=60.0) as client:
			result = get_latest_result(client=client, api_base=api_base, project_id=project_id)
	except Exception:
		result = _load_result_from_db(data_dir, project_id)

	structure_score: dict[str, Any] | None = None
	if result is not None:
		duration_ms = job_metrics.get("videoDurationMs")
		structure_score = score_result_structure(
			result,
			duration_ms=int(duration_ms) if isinstance(duration_ms, int) else None,
			pipeline_stages=job_metrics.get("stages") if isinstance(job_metrics.get("stages"), dict) else None,
		)
		if job_metrics.get("status") != "succeeded":
			structure_score = {**structure_score, "note": f"job status={job_metrics.get('status')}; structure scored from latest result"}
	else:
		structure_score = {"passed": False, "score": 0.0, "checks": {}, "skipped": True}

	keyframe_verify = collect_keyframe_verify_metrics(data_dir=data_dir, project_id=project_id, job_id=job_id)
	baseline = load_baseline(repo_root / "benchmarks" / "results" / "baseline.json")
	baseline_diff = compare_to_baseline(
		profile=None,
		job_metrics=job_metrics,
		structure_score=structure_score or {"passed": False, "score": 0.0},
		thresholds=None,
		baseline=baseline,
	)
	environment = collect_environment_snapshot()
	report = build_benchmark_report(
		mode="report",
		job_metrics=job_metrics,
		structure_score=structure_score,
		baseline_diff=baseline_diff,
		environment=environment,
		profile=None,
		keyframe_verify=keyframe_verify,
		extra={"evaluationLabel": label, "sourceUrl": _project_source_url(data_dir, project_id)},
	)

	json_path, md_path, html_path = write_benchmark_report(
		report,
		out_dir=out_dir,
		profile=None,
		job_id=job_id,
		git_sha=str(environment.get("gitSha") or ""),
	)
	return report, json_path


def _project_source_url(data_dir: Path, project_id: str) -> str | None:
	db = data_dir / "core.sqlite3"
	if not db.exists():
		return None
	con = sqlite3.connect(str(db))
	try:
		row = con.execute("SELECT source_url FROM projects WHERE project_id = ?", (project_id,)).fetchone()
		return str(row[0]) if row and row[0] else None
	finally:
		con.close()


def main() -> int:
	core_root = Path(__file__).resolve().parents[1]
	src_dir = core_root / "src"
	if str(src_dir) not in sys.path:
		sys.path.insert(0, str(src_dir))

	data_dir = Path(r"d:\vh-smoke-data").resolve()
	repo_root = _repo_root()
	out_dir = data_dir / "evaluation-reports"
	api_base = "http://127.0.0.1:8000"

	jobs = [
		{
			"project_id": "037a3dae-fb3a-465f-b972-97e661dbb5b0",
			"job_id": "cf0a3ded-8126-4ccc-b73b-f438e98f921c",
			"label": "BV1oCwEeVEe4",
		},
		{
			"project_id": "7bde2cd0-7574-448e-ab98-2c8e23eacafc",
			"job_id": "c9b563cc-4156-4d67-aff7-1719df91bfbd",
			"label": "BV1J9o4BnE2n",
		},
	]

	summary: list[dict[str, Any]] = []
	for item in jobs:
		report, path = evaluate_job(
			data_dir=data_dir,
			repo_root=repo_root,
			api_base=api_base,
			job_id=item["job_id"],
			project_id=item["project_id"],
			out_dir=out_dir,
			label=item["label"],
		)
		summary.append(
			{
				"label": item["label"],
				"projectId": item["project_id"],
				"jobId": item["job_id"],
				"reportPath": path.as_posix(),
				"passed": report.get("passed"),
				"status": report.get("jobMetrics", {}).get("status"),
				"structureScore": report.get("structureScore", {}).get("score"),
				"speedFactor": report.get("jobMetrics", {}).get("speedFactor"),
				"e2eMs": report.get("jobMetrics", {}).get("e2eMs"),
				"executionMs": report.get("jobMetrics", {}).get("executionMs"),
				"videoDurationMs": report.get("jobMetrics", {}).get("videoDurationMs"),
			}
		)
		print(f"[eval] {item['label']}: report={path} passed={report.get('passed')}")

	summary_path = out_dir / "summary.json"
	out_dir.mkdir(parents=True, exist_ok=True)
	summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
	print(f"[eval] summary written: {summary_path}")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
