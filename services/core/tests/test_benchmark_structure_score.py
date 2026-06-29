from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from core.app.benchmark.job_metrics import collect_job_metrics
from core.app.benchmark.structure_score import score_result_structure


def _valid_result() -> dict:
	return {
		"resultId": "r1",
		"projectId": "p1",
		"schemaVersion": "2026-01-29",
		"pipelineVersion": "dev",
		"createdAtMs": 123,
		"contentBlocks": [
			{
				"blockId": "b1",
				"idx": 0,
				"title": "Intro",
				"startMs": 0,
				"endMs": 60000,
		"highlights": [
					{
						"highlightId": "h1",
						"idx": 0,
						"text": "Hello",
						"startMs": 1000,
						"endMs": 5000,
						"keyframe": {"timeMs": 2000},
					},
					{
						"highlightId": "h2",
						"idx": 1,
						"text": "World",
						"startMs": 10000,
						"endMs": 15000,
						"keyframe": {"timeMs": 12000},
					},
				],
			},
			{
				"blockId": "b2",
				"idx": 1,
				"title": "Body",
				"startMs": 60000,
				"endMs": 120000,
				"highlights": [
					{
						"highlightId": "h3",
						"idx": 0,
						"text": "More",
						"startMs": 61000,
						"endMs": 65000,
						"keyframe": {"timeMs": 62000},
					},
					{
						"highlightId": "h4",
						"idx": 1,
						"text": "Extra",
						"startMs": 70000,
						"endMs": 75000,
						"keyframe": {"timeMs": 72000},
					},
					{
						"highlightId": "h5",
						"idx": 2,
						"text": "Tail",
						"startMs": 80000,
						"endMs": 85000,
					},
				],
			},
		],
		"mindmap": {
			"nodes": [
				{"id": "n0", "type": "root", "label": "Video", "level": 0, "data": {}},
				{"id": "n1", "type": "topic", "label": "Intro", "level": 1, "data": {"targetBlockId": "b1"}},
				{"id": "n2", "type": "detail", "label": "Hello", "level": 2, "data": {"targetBlockId": "b1", "targetHighlightId": "h1"}},
			],
			"edges": [],
		},
		"assetRefs": [{"assetId": "a1", "kind": "video", "contentUrl": "/api/v1/assets/a1/content"}],
	}


def test_structure_score_high_for_valid_result() -> None:
	out = score_result_structure(_valid_result(), duration_ms=120_000)
	assert out["passed"] is True
	assert out["score"] >= 0.85
	assert out["checks"]["keyframe_coverage"]["value"] == pytest.approx(4 / 5)


def test_structure_score_fails_on_invalid_result() -> None:
	bad = _valid_result()
	bad["contentBlocks"] = []
	out = score_result_structure(bad)
	assert out["passed"] is False
	assert "validationError" in out


def test_structure_score_timestamp_out_of_range() -> None:
	bad = _valid_result()
	bad["contentBlocks"][0]["startMs"] = 999_999
	out = score_result_structure(bad, duration_ms=120_000)
	assert out["checks"]["timestamp_in_range"]["ok"] is False


def test_structure_score_low_mindmap_link_rate() -> None:
	bad = _valid_result()
	bad["mindmap"]["nodes"] = [
		{"id": "n0", "type": "root", "label": "Video", "level": 0, "data": {}},
		{"id": "n1", "type": "topic", "label": "Intro", "level": 1, "data": {}},
	]
	out = score_result_structure(bad, duration_ms=120_000)
	assert out["checks"]["mindmap_link_rate"]["ok"] is False


def test_structure_score_skips_keyframe_when_stage_not_ran() -> None:
	result = _valid_result()
	for block in result["contentBlocks"]:
		for h in block["highlights"]:
			h.pop("keyframe", None)
	out = score_result_structure(result, duration_ms=120_000, pipeline_stages={"plan": {"durationMs": 1}})
	kf = out["checks"]["keyframe_coverage"]
	assert kf.get("skipped") is True
	assert kf.get("ok") is None
	assert out["passed"] is True
	assert out["score"] >= 0.85


def test_structure_score_fails_keyframe_when_stage_ran() -> None:
	result = _valid_result()
	for block in result["contentBlocks"]:
		for h in block["highlights"]:
			h.pop("keyframe", None)
	stages = {"keyframes.extract": {"durationMs": 5000, "status": "ok"}}
	out = score_result_structure(result, duration_ms=120_000, pipeline_stages=stages)
	kf = out["checks"]["keyframe_coverage"]
	assert kf.get("skipped") is not True
	assert kf.get("ok") is False
	assert out["passed"] is False


def test_structure_score_skips_keyframe_when_extract_noop() -> None:
	result = _valid_result()
	for block in result["contentBlocks"]:
		for h in block["highlights"]:
			h.pop("keyframe", None)
	stages = {"keyframes.extract": {"durationMs": 29, "status": "ok"}}
	out = score_result_structure(result, duration_ms=120_000, pipeline_stages=stages)
	kf = out["checks"]["keyframe_coverage"]
	assert kf.get("skipped") is True
	assert kf.get("reason") == "keyframes_extract_no_output"
	assert out["passed"] is True


def _setup_sqlite(tmp_path: Path, job_id: str, project_id: str) -> Path:
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
	return db


def test_collect_job_metrics_from_sqlite_and_timings(tmp_path: Path) -> None:
	job_id = "11111111-1111-1111-1111-111111111111"
	project_id = "22222222-2222-2222-2222-222222222222"
	_setup_sqlite(tmp_path, job_id, project_id)
	artifact_dir = tmp_path / project_id / "artifacts" / job_id
	artifact_dir.mkdir(parents=True)
	timings = artifact_dir / "timings.jsonl"
	timings.write_text(
		'{"step":"plan","durationMs":1000,"status":"ok"}\n{"step":"transcribe.asr","durationMs":5000,"status":"ok"}\n',
		encoding="utf-8",
	)

	out = collect_job_metrics(data_dir=tmp_path, job_id=job_id)
	assert out["e2eMs"] == 61_000
	assert out["executionMs"] == 60_000
	assert out["queueWaitMs"] == 1_000
	assert out["speedFactor"] == pytest.approx(1.0)
	assert out["stages"]["plan"]["durationMs"] == 1000
	assert out["stages"]["transcribe.asr"]["durationMs"] == 5000
