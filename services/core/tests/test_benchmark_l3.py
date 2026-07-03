from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.app.benchmark.faithfulness_judge import (
	collect_highlights,
	extract_transcript_window,
	judge_highlight_faithfulness,
	sample_highlights_deterministic,
)
from core.app.benchmark.human_rubric import load_rubric_template, validate_rubric_scores
from core.app.benchmark.keyframe_verify_metrics import collect_keyframe_verify_metrics
from core.app.benchmark.profiles import profile_env_overrides
from core.app.benchmark.report import build_benchmark_report
from core.app.benchmark.semantic_score import score_semantic_golden


def _write_verify_jsonl(path: Path, rows: list[dict]) -> None:
	path.parent.mkdir(parents=True, exist_ok=True)
	path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


def test_keyframe_verify_metrics_disabled_when_missing(tmp_path: Path) -> None:
	metrics = collect_keyframe_verify_metrics(
		data_dir=tmp_path,
		project_id="p1",
		job_id="j1",
	)
	assert metrics["enabled"] is False
	assert metrics["reason"] == "verify_mode_off_or_no_artifact"
	assert metrics["confidenceP50"] is None


def test_keyframe_verify_metrics_aggregates(tmp_path: Path) -> None:
	path = tmp_path / "p1" / "artifacts" / "j1" / "keyframe_verify" / "results.jsonl"
	_write_verify_jsonl(
		path,
		[
			{"mode": "multimodal", "confidence": 0.4, "action": "kept", "phase": "initial"},
			{"mode": "multimodal", "confidence": 0.8, "action": "kept", "phase": "initial"},
			{"mode": "multimodal", "confidence": 0.2, "action": "dropped", "phase": "initial"},
			{"mode": "multimodal", "confidence": 0.6, "action": "retry_scheduled", "phase": "initial"},
			{"mode": "multimodal", "confidence": 0.7, "action": "retried_kept", "phase": "retry"},
			{"mode": "multimodal", "confidence": 0.1, "action": "retried_dropped", "phase": "retry"},
		],
	)
	metrics = collect_keyframe_verify_metrics(data_dir=tmp_path, project_id="p1", job_id="j1")
	assert metrics["enabled"] is True
	assert metrics["count"] == 6
	assert metrics["keepRate"] == round(2 / 6, 4)
	assert metrics["overallKeepRate"] == round(3 / 6, 4)
	assert metrics["dropRate"] == round(2 / 6, 4)
	assert metrics["retryScheduledRate"] == round(1 / 6, 4)
	assert metrics["retryRate"] == metrics["retryScheduledRate"]
	assert metrics["secondVerifyPassRate"] == 0.5
	assert metrics["dropAfterRetryRate"] == round(1 / 6, 4)
	assert metrics["confidenceP50"] == 0.5


def test_faithfulness_sampling_is_deterministic() -> None:
	highlights = [{"highlightId": f"h{i}", "text": f"t{i}", "startMs": i * 1000, "endMs": i * 1000 + 500} for i in range(20)]
	a = sample_highlights_deterministic(highlights, job_id="job-1", profile="short-local", sample_size=5, full=False)
	b = sample_highlights_deterministic(highlights, job_id="job-1", profile="short-local", sample_size=5, full=False)
	c = sample_highlights_deterministic(highlights, job_id="job-2", profile="short-local", sample_size=5, full=False)
	assert a == b
	assert a != c
	assert len(a) == 5


def test_extract_transcript_window_overlap() -> None:
	segments = [
		{"startMs": 0, "endMs": 5000, "text": "hello"},
		{"startMs": 5000, "endMs": 10000, "text": "world"},
		{"startMs": 20000, "endMs": 25000, "text": "later"},
	]
	window = extract_transcript_window(segments=segments, start_ms=4000, end_ms=6000)
	assert "hello" in window
	assert "world" in window
	assert "later" not in window


class _MockJudgeProvider:
	def __init__(self, responses: list[dict]) -> None:
		self._responses = list(responses)
		self.calls = 0

	def generate_json(self, task_name: str, input_dict: dict, *, max_tokens: int | None = None) -> dict:
		self.calls += 1
		return self._responses.pop(0)


def test_faithfulness_judge_aggregates() -> None:
	result = {
		"contentBlocks": [
			{
				"blockId": "b1",
				"highlights": [
					{"highlightId": "h1", "text": "A", "startMs": 0, "endMs": 1000},
					{"highlightId": "h2", "text": "B", "startMs": 2000, "endMs": 3000},
				],
			}
		]
	}
	provider = _MockJudgeProvider(
		[
			{"supported": True, "score": 0.9, "evidenceQuote": "a", "reason": "ok"},
			{"supported": False, "score": 0.2, "evidenceQuote": "", "reason": "no"},
		]
	)
	out = judge_highlight_faithfulness(
		result=result,
		segments=[],
		provider=provider,
		job_id="j1",
		profile="p",
		sample_size=2,
		full=True,
		supported_rate_min=0.5,
		mean_score_min=0.5,
	)
	assert out["sampleSize"] == 2
	assert out["supportedRate"] == 0.5
	assert out["meanScore"] == 0.55
	assert out["passed"] is True
	assert len(collect_highlights(result)) == 2


def test_semantic_score_combines_faithfulness() -> None:
	result = {"contentBlocks": [{"blockId": "b1", "startMs": 0, "endMs": 1000, "highlights": []}]}
	faithfulness = {"enabled": True, "passed": False, "sampleSize": 1}
	score = score_semantic_golden(result=result, expected_chapters=[], faithfulness=faithfulness)
	assert score["passed"] is False
	assert score["highlightFaithfulness"]["passed"] is False


def test_report_passes_when_keyframe_verify_disabled() -> None:
	report = build_benchmark_report(
		mode="benchmark",
		job_metrics={"status": "succeeded", "jobId": "j1"},
		structure_score={"passed": True, "score": 0.9, "checks": {}},
		baseline_diff={"passed": True, "alerts": []},
		keyframe_verify={
			"enabled": False,
			"reason": "verify_mode_off_or_no_artifact",
			"confidenceP50": None,
			"keepRate": None,
		},
	)
	assert report["passed"] is True
	assert report["keyframeVerify"]["enabled"] is False


def test_human_rubric_validation() -> None:
	root = Path(__file__).resolve().parents[3]
	template = load_rubric_template(root)
	payload = {
		"dimensions": {
			"chapterQuality": {"score": 4, "note": ""},
			"faithfulness": {"score": 5, "note": ""},
			"mindmapUsability": {"score": 4, "note": ""},
		}
	}
	validated = validate_rubric_scores(payload, template=template)
	assert validated["meanScore"] == pytest.approx(4.3333, rel=1e-3)
	assert validated["passed"] is True


def test_profile_env_overrides_keyframe_verify() -> None:
	overrides = profile_env_overrides({"keyframeVerify": {"mode": "multimodal", "maxPerJob": 3}})
	assert overrides["KEYFRAME_VERIFY_MODE"] == "multimodal"
	assert overrides["KEYFRAME_VERIFY_MAX_PER_JOB"] == "3"


def test_render_benchmark_report_html_sections() -> None:
	from core.app.benchmark.report_html import render_benchmark_report_html

	report = {
		"schemaVersion": "2026-06-22",
		"generatedAtMs": 1_700_000_000_000,
		"mode": "report",
		"passed": False,
		"jobMetrics": {
			"jobId": "j1",
			"projectId": "p1",
			"status": "succeeded",
			"videoDurationMs": 120_000,
			"e2eMs": 60_000,
			"executionMs": 55_000,
			"speedFactor": 0.45,
			"stages": {"plan": {"durationMs": 5000, "status": "ok"}},
			"llm": {"calls": 2, "repairs": 0},
		},
		"structureScore": {
			"passed": False,
			"score": 0.8,
			"checks": {
				"keyframe_coverage": {"value": 0.0, "min": 0.5, "ok": False},
			},
		},
		"baselineDiff": {"passed": True, "alerts": []},
		"keyframeVerify": {"enabled": False, "reason": "verify_mode_off_or_no_artifact"},
		"semanticScore": {
			"passed": True,
			"chapterBoundary": {"f1": 0.85, "precision": 0.9, "recall": 0.8, "matched": 3, "expected": 4},
			"highlightFaithfulness": {
				"passed": True,
				"enabled": True,
				"sampleSize": 2,
				"supportedRate": 1.0,
				"meanScore": 0.9,
				"samples": [{"supported": True, "score": 0.9, "highlightId": "h1", "reason": "ok"}],
			},
		},
		"humanRubric": {
			"passed": True,
			"meanScore": 4.0,
			"scorer": "tester",
			"scoredAtMs": 1_700_000_000_000,
			"dimensions": {
				"chapterQuality": {"score": 4, "note": ""},
				"faithfulness": {"score": 4, "note": "good"},
				"mindmapUsability": {"score": 4, "note": ""},
			},
		},
		"environment": {"gitSha": "abc"},
	}
	html = render_benchmark_report_html(report)
	assert "Keyframe Verify" in html
	assert "忠实度" in html
	assert "人工 Rubric" in html
	assert "关键帧覆盖率" in html


def test_render_stage_bars_groups_transcribe_children() -> None:
	from core.app.benchmark.report_html import render_benchmark_report_html

	report = {
		"schemaVersion": "2026-06-22",
		"generatedAtMs": 1,
		"mode": "report",
		"passed": True,
		"jobMetrics": {
			"jobId": "j1",
			"projectId": "p1",
			"status": "succeeded",
			"stages": {
				"speech_to_text": {"durationMs": 633876, "status": "ok"},
				"transcribe.asr": {"durationMs": 609105, "status": "ok"},
				"transcribe.download": {"durationMs": 22283, "status": "ok"},
				"plan": {"durationMs": 74226, "status": "ok"},
			},
			"llm": {"calls": 1, "repairs": 0},
		},
		"structureScore": {"passed": True, "score": 1.0, "checks": {}},
		"baselineDiff": {"passed": True, "alerts": []},
		"keyframeVerify": {"enabled": False},
		"environment": {},
	}
	html = render_benchmark_report_html(report)
	assert "speech_to_text" in html
	assert "transcribe.asr" in html
	assert "stage-details" in html
	assert "已包含在 speech_to_text 耗时内" in html
