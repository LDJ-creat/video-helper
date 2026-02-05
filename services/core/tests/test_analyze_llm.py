from __future__ import annotations

import os

import httpx
import pytest

from core.app.pipeline.analyze_provider import AnalyzeError, llm_provider_from_env, llm_provider_from_runtime
from core.app.pipeline.highlights import build_highlights_llm, generate_highlights
from core.app.pipeline.mindmap import build_mindmap_llm, generate_mindmap
from core.app.pipeline.transcribe import build_placeholder_transcript
from core.contracts.error_codes import ErrorCode


def _set_env(**kwargs: str) -> None:
	for k, v in kwargs.items():
		os.environ[k] = v


def test_llm_provider_builds_request_and_parses_json() -> None:
	captured: dict = {}

	def handler(request: httpx.Request) -> httpx.Response:
		captured["url"] = str(request.url)
		captured["auth"] = request.headers.get("Authorization")
		payload = httpx.Response(200, content=request.content).json()
		captured["payload"] = payload
		return httpx.Response(200, json={"choices": [{"message": {"content": '{"ok": true}'}}]})

	transport = httpx.MockTransport(handler)

	_set_env(
		ANALYZE_PROVIDER="llm",
		LLM_API_BASE="https://example.invalid",
		LLM_API_KEY="sk-test-SECRET",
		LLM_MODEL="minimax-2.1",
		LLM_TIMEOUT_S="5",
	)
	provider = llm_provider_from_env(transport=transport)
	out = provider.generate_json("t", {"messages": [{"role": "user", "content": "{}"}]})

	assert out == {"ok": True}
	assert captured["auth"] == "Bearer sk-test-SECRET"
	assert captured["payload"]["model"] == "minimaxai/minimax-m2.1"
	assert captured["url"].endswith("/v1/chat/completions")


def test_llm_provider_maps_rate_limit_without_leaking_key() -> None:
	def handler(_: httpx.Request) -> httpx.Response:
		return httpx.Response(429, json={"error": {"message": "rate limited"}})

	transport = httpx.MockTransport(handler)
	_set_env(
		ANALYZE_PROVIDER="llm",
		LLM_API_BASE="https://example.invalid",
		LLM_API_KEY="sk-test-SECRET",
		LLM_MODEL="minimax-2.1",
		LLM_TIMEOUT_S="5",
	)
	provider = llm_provider_from_env(transport=transport)

	with pytest.raises(AnalyzeError) as ei:
		provider.generate_json("highlights", {"messages": [{"role": "user", "content": "{}"}]})

	err = ei.value
	assert err.code == ErrorCode.JOB_STAGE_FAILED
	assert err.details.get("reason") == "rate_limited"
	assert "sk-test-SECRET" not in str(err)


def test_llm_provider_missing_credentials_maps_reason() -> None:
	os.environ.pop("LLM_API_KEY", None)
	_set_env(ANALYZE_PROVIDER="llm", LLM_API_BASE="https://example.invalid")
	with pytest.raises(AnalyzeError) as ei:
		llm_provider_from_env()
	assert ei.value.details.get("reason") == "missing_credentials"


def test_llm_provider_from_runtime_validates_settings_fields() -> None:
	with pytest.raises(AnalyzeError) as ei1:
		llm_provider_from_runtime(api_base="not-a-url", api_key="sk-test-SECRET", model="m", timeout_s=5)
	assert ei1.value.details.get("reason") == "invalid_settings"
	assert ei1.value.details.get("badField") == "baseUrl"

	with pytest.raises(AnalyzeError) as ei2:
		llm_provider_from_runtime(api_base="https://example.invalid", api_key="sk-test-SECRET", model="", timeout_s=5)
	assert ei2.value.details.get("reason") == "invalid_settings"
	assert ei2.value.details.get("missingField") == "model"

	with pytest.raises(AnalyzeError) as ei3:
		llm_provider_from_runtime(api_base="https://example.invalid", api_key=None, model="m", timeout_s=5)
	assert ei3.value.details.get("reason") == "missing_credentials"


class _StubProvider:
	def __init__(self, result: dict):
		self._result = result

	def generate_json(self, task_name: str, input_dict: dict) -> dict:  # noqa: ARG002
		return self._result


def test_highlights_llm_normalizes_ids_and_time_bounds() -> None:
	transcript = build_placeholder_transcript(duration_ms=20_000, segment_ms=5_000)
	chapters = [
		{"chapterId": "ch_1", "idx": 0, "title": "C1", "summary": "", "startMs": 0, "endMs": 10_000},
		{"chapterId": "ch_2", "idx": 1, "title": "C2", "summary": "", "startMs": 10_000, "endMs": 20_000},
	]

	provider = _StubProvider(
		{
			"chapters": [
				{"chapterId": "ch_1", "items": [{"text": "A", "timeMs": 9999}, {"text": "B", "timeMs": 10_000}]},
				{"chapterId": "ch_2", "items": [{"text": "C", "timeMs": 15_000}]},
			]
		}
	)

	hls = build_highlights_llm(transcript=transcript, chapters=chapters, provider=provider)
	assert [h["highlightId"] for h in hls if h["chapterId"] == "ch_1"] == ["h_ch_1_0", "h_ch_1_1"]
	# timeMs at 10_000 is outside [0, 10_000) -> must be corrected to None
	ch1_times = [h.get("timeMs") for h in hls if h["chapterId"] == "ch_1"]
	assert ch1_times == [9999, None]


def test_generate_highlights_falls_back_when_llm_unavailable() -> None:
	transcript = build_placeholder_transcript(duration_ms=10_000, segment_ms=5_000)
	chapters = [{"chapterId": "ch_1", "idx": 0, "title": "C1", "summary": "", "startMs": 0, "endMs": 10_000}]

	# No LLM_API_KEY set; allow fallback.
	_set_env(ANALYZE_PROVIDER="llm", LLM_API_BASE="https://example.invalid", ANALYZE_ALLOW_RULES_FALLBACK="1")
	os.environ.pop("LLM_API_KEY", None)

	hls = generate_highlights(transcript=transcript, chapters=chapters)
	assert isinstance(hls, list) and len(hls) >= 1
	assert hls[0]["chapterId"] == "ch_1"


def test_generate_highlights_invalid_settings_file_maps_reason(tmp_path) -> None:
	os.environ["DATA_DIR"] = str(tmp_path)
	(tmp_path / "settings.json").write_text("{not-json", encoding="utf-8")

	transcript = build_placeholder_transcript(duration_ms=10_000, segment_ms=5_000)
	chapters = [{"chapterId": "ch_1", "idx": 0, "title": "C1", "summary": "", "startMs": 0, "endMs": 10_000}]

	_set_env(ANALYZE_PROVIDER="llm", ANALYZE_ALLOW_RULES_FALLBACK="0")
	with pytest.raises(AnalyzeError) as ei:
		generate_highlights(transcript=transcript, chapters=chapters)
	assert ei.value.details.get("reason") == "invalid_settings_file"

	# When fallback enabled, keep pipeline moving.
	_set_env(ANALYZE_PROVIDER="llm", ANALYZE_ALLOW_RULES_FALLBACK="1")
	hls = generate_highlights(transcript=transcript, chapters=chapters)
	assert isinstance(hls, list) and len(hls) >= 1


def test_highlights_llm_invalid_output_maps_reason() -> None:
	transcript = build_placeholder_transcript(duration_ms=10_000, segment_ms=5_000)
	chapters = [{"chapterId": "ch_1", "idx": 0, "title": "C1", "summary": "", "startMs": 0, "endMs": 10_000}]

	provider = _StubProvider({"nope": True})
	with pytest.raises(AnalyzeError) as ei:
		build_highlights_llm(transcript=transcript, chapters=chapters, provider=provider)
	assert ei.value.code == ErrorCode.JOB_STAGE_FAILED
	assert ei.value.details.get("reason") == "invalid_llm_output"


def test_mindmap_llm_builds_renderable_graph() -> None:
	chapters = [
		{"chapterId": "ch_1", "idx": 0, "title": "Intro", "summary": "", "startMs": 0, "endMs": 10_000},
		{"chapterId": "ch_2", "idx": 1, "title": "Main", "summary": "", "startMs": 10_000, "endMs": 20_000},
	]
	highlights = [
		{"highlightId": "h_ch_1_0", "chapterId": "ch_1", "idx": 0, "text": "Point A", "timeMs": 1000},
		{"highlightId": "h_ch_2_0", "chapterId": "ch_2", "idx": 0, "text": "Point B", "timeMs": 12000},
	]

	provider = _StubProvider(
		{
			"chapters": [
				{"chapterId": "ch_1", "topics": [{"label": "What is it"}]},
				{"chapterId": "ch_2", "topics": [{"label": "How it works"}, {"label": "Examples"}]},
			]
		}
	)

	mm = build_mindmap_llm(chapters=chapters, highlights=highlights, provider=provider)
	assert isinstance(mm, dict)
	assert "nodes" in mm and "edges" in mm
	ids = {n.get("id") for n in mm["nodes"] if isinstance(n, dict)}
	assert "node_root" in ids
	assert "node_ch_ch_1" in ids
	assert "node_ch_ch_2" in ids


def test_mindmap_llm_invalid_output_maps_reason() -> None:
	chapters = [{"chapterId": "ch_1", "idx": 0, "title": "Intro", "summary": "", "startMs": 0, "endMs": 10_000}]
	highlights = [{"highlightId": "h_ch_1_0", "chapterId": "ch_1", "idx": 0, "text": "Point A", "timeMs": 1000}]

	provider = _StubProvider({"chapters": [{"chapterId": "wrong", "topics": [{"label": "x"}]}]})
	with pytest.raises(AnalyzeError) as ei:
		build_mindmap_llm(chapters=chapters, highlights=highlights, provider=provider)
	assert ei.value.code == ErrorCode.JOB_STAGE_FAILED
	assert ei.value.details.get("reason") == "invalid_llm_output"


def test_generate_mindmap_falls_back_when_llm_unavailable() -> None:
	chapters = [{"chapterId": "ch_1", "idx": 0, "title": "Intro", "summary": "", "startMs": 0, "endMs": 10_000}]
	highlights = [{"highlightId": "h_ch_1_0", "chapterId": "ch_1", "idx": 0, "text": "Point A", "timeMs": 1000}]

	_set_env(ANALYZE_PROVIDER="llm", LLM_API_BASE="https://example.invalid", ANALYZE_ALLOW_RULES_FALLBACK="1")
	os.environ.pop("LLM_API_KEY", None)

	mm = generate_mindmap(chapters=chapters, highlights=highlights)
	assert isinstance(mm, dict)
	assert isinstance(mm.get("nodes"), list)
	assert isinstance(mm.get("edges"), list)
