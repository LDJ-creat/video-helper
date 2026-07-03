from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from core.app.benchmark.baseline import compare_to_baseline
from core.app.benchmark.job_metrics import collect_job_metrics
from core.app.benchmark.report import build_benchmark_report, write_benchmark_report
from core.app.benchmark.semantic_score import score_chapter_boundaries


def test_compare_to_baseline_speed_factor_alert() -> None:
	diff = compare_to_baseline(
		profile="short-local",
		job_metrics={"status": "succeeded", "speedFactor": 4.0, "e2eMs": 1000},
		structure_score={"score": 0.9, "passed": True},
		thresholds={"speedFactorMax": 3.0, "structureScoreMin": 0.85, "jobSuccess": True},
		baseline={"profiles": {}},
	)
	assert diff["passed"] is False
	assert any(a.get("code") == "speed_factor_exceeded" for a in diff["alerts"])


def test_build_report_mode_report_ignores_job_status_for_passed() -> None:
	report = build_benchmark_report(
		mode="report",
		job_metrics={"jobId": "j1", "projectId": "p1", "status": "canceled"},
		structure_score={"passed": True, "score": 1.0, "checks": {}},
		baseline_diff={"passed": True, "alerts": []},
	)
	assert report["passed"] is True
	ps = report.get("passSummary")
	assert isinstance(ps, dict)
	assert ps.get("jobSucceeded") is False
	assert ps.get("structurePassed") is True
	assert ps.get("overallPassed") is True


def test_build_and_write_benchmark_report(tmp_path: Path) -> None:
	report = build_benchmark_report(
		mode="report",
		job_metrics={"jobId": "11111111-1111-1111-1111-111111111111", "projectId": "p1", "status": "succeeded"},
		structure_score={"passed": True, "score": 0.92, "checks": {}},
		baseline_diff={"passed": True, "alerts": []},
		environment={"gitSha": "abc1234"},
	)
	json_path, md_path, html_path = write_benchmark_report(
		report,
		out_dir=tmp_path,
		job_id="11111111-1111-1111-1111-111111111111",
		git_sha="abc1234",
	)
	assert json_path.exists()
	assert md_path is not None and md_path.exists()
	assert html_path is not None and html_path.exists()
	html_text = html_path.read_text(encoding="utf-8")
	assert "<!DOCTYPE html>" in html_text
	assert "Benchmark Report" in html_text or "11111111" in html_text
	payload = json.loads(json_path.read_text(encoding="utf-8"))
	assert payload["passed"] is True
	assert "job-11111111-1111-1111-1111-111111111111" in json_path.name


def test_chapter_boundary_f1() -> None:
	predicted = [
		{"startMs": 0, "endMs": 60_000},
		{"startMs": 60_000, "endMs": 120_000},
	]
	expected = [
		{"title": "A", "startMs": 0, "endMs": 55_000},
		{"title": "B", "startMs": 58_000, "endMs": 120_000},
	]
	out = score_chapter_boundaries(predicted_blocks=predicted, expected_chapters=expected)
	assert out["f1"] >= 0.7


def _setup_sqlite_for_metrics(tmp_path: Path, job_id: str, project_id: str) -> None:
	db = tmp_path / "core.sqlite3"
	con = sqlite3.connect(str(db))
	con.execute(
		"""
		CREATE TABLE jobs (
			job_id TEXT PRIMARY KEY,
			project_id TEXT,
			status TEXT,
			stage TEXT,
			created_at_ms INTEGER,
			started_at_ms INTEGER,
			finished_at_ms INTEGER,
			transcript_meta TEXT,
			error TEXT
		)
		"""
	)
	con.execute(
		"INSERT INTO jobs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
		(
			job_id,
			project_id,
			"succeeded",
			"assemble_result",
			1_000,
			2_000,
			62_000,
			json.dumps({"durationMs": 60_000}),
			None,
		),
	)
	con.commit()
	con.close()


def test_collect_job_metrics_includes_llm_tokens(tmp_path: Path) -> None:
	job_id = "11111111-1111-1111-1111-111111111111"
	project_id = "22222222-2222-2222-2222-222222222222"
	_setup_sqlite_for_metrics(tmp_path, job_id, project_id)
	usage_path = tmp_path / project_id / "artifacts" / job_id / "llm_usage.jsonl"
	usage_path.parent.mkdir(parents=True)
	usage_path.write_text(
		"\n".join(
			[
				json.dumps(
					{
						"task": "plan_content_blocks",
						"stage": "analyze",
						"promptTokens": 100,
						"completionTokens": 50,
						"totalTokens": 150,
						"source": "api",
					}
				),
				json.dumps(
					{
						"task": "chunk_summary",
						"stage": "chunk_summaries",
						"promptTokens": 200,
						"completionTokens": 80,
						"totalTokens": 280,
						"source": "api",
					}
				),
			]
		)
		+ "\n",
		encoding="utf-8",
	)

	out = collect_job_metrics(data_dir=tmp_path, job_id=job_id)
	tokens = out["llm"]["tokens"]
	assert tokens["available"] is True
	assert tokens["total"] == 430
	assert tokens["byStage"]["analyze"]["total"] == 150
	assert tokens["byStage"]["chunk_summaries"]["total"] == 280
