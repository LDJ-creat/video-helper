from __future__ import annotations

import json
import os
from pathlib import Path

import httpx
import pytest

from core.app.logs.pipeline_timings import append_pipeline_timing, time_pipeline_step
from core.app.pipeline.analyze_provider import AnalyzeError, llm_provider_from_env, llm_provider_from_runtime
from core.app.pipeline.llm_json_repair import build_repair_request
from core.app.pipeline.llm_plan import generate_plan, validate_plan
from core.app.pipeline.llm_usage_context import clear_llm_usage_context, set_llm_usage_context
from core.contracts.error_codes import ErrorCode


def _openai_sse_body(content: str, *, usage: dict | None = None) -> bytes:
	"""Build an OpenAI-style SSE response body from a content string."""
	chunk = json.dumps({"id": "chatcmpl-test", "choices": [{"delta": {"content": content}}]})
	lines = [f"data: {chunk}"]
	if usage is not None:
		usage_chunk = json.dumps({"id": "chatcmpl-test", "choices": [], "usage": usage})
		lines.append(f"data: {usage_chunk}")
	lines.append("data: [DONE]")
	return "\n".join(lines).encode("utf-8")


def _mock_transcript() -> dict:
	return {
		"version": 1,
		"segments": [{"startMs": 0, "endMs": 10000, "text": "Segment 1"}],
		"durationMs": 10000,
		"unit": "ms",
	}


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
		return httpx.Response(200, content=_openai_sse_body('{"ok": true}'), headers={"Content-Type": "text/event-stream"})

	transport = httpx.MockTransport(handler)

	_set_env(
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


def test_llm_provider_records_usage_from_sse(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	monkeypatch.setenv("DATA_DIR", str(tmp_path))
	set_llm_usage_context(project_id="proj-1", job_id="job-1")
	try:

		def handler(request: httpx.Request) -> httpx.Response:
			payload = httpx.Response(200, content=request.content).json()
			assert payload.get("stream_options") == {"include_usage": True}
			return httpx.Response(
				200,
				content=_openai_sse_body('{"ok": true}', usage={"prompt_tokens": 12, "completion_tokens": 8, "total_tokens": 20}),
				headers={"Content-Type": "text/event-stream"},
			)

		transport = httpx.MockTransport(handler)
		_set_env(
			LLM_API_BASE="https://example.invalid",
			LLM_API_KEY="sk-test-SECRET",
			LLM_MODEL="minimax-2.1",
			LLM_TIMEOUT_S="5",
		)
		provider = llm_provider_from_env(transport=transport)
		out = provider.generate_json("plan_content_blocks", {"messages": [{"role": "user", "content": "{}"}]})
		assert out == {"ok": True}
	finally:
		clear_llm_usage_context()

	path = tmp_path / "proj-1" / "artifacts" / "job-1" / "llm_usage.jsonl"
	assert path.exists()
	rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
	assert len(rows) == 1
	assert rows[0]["task"] == "plan_content_blocks"
	assert rows[0]["promptTokens"] == 12
	assert rows[0]["completionTokens"] == 8
	assert rows[0]["totalTokens"] == 20
	assert rows[0]["source"] == "api"


def test_llm_provider_maps_rate_limit_without_leaking_key() -> None:
	def handler(_: httpx.Request) -> httpx.Response:
		return httpx.Response(429, json={"error": {"message": "rate limited"}})

	transport = httpx.MockTransport(handler)
	_set_env(
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
	_set_env(LLM_API_BASE="https://example.invalid")
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

	def generate_json(self, task_name: str, input_dict: dict, *, max_tokens: int | None = None) -> dict:  # noqa: ARG002
		return self._result


class _RepairingPlanProvider:
	def __init__(self):
		self.calls: list[str] = []

	def generate_json(self, task_name: str, input_dict: dict, *, max_tokens: int | None = None) -> dict:  # noqa: ARG002
		self.calls.append(task_name)
		if task_name == "plan_content_blocks":
			return {"schemaVersion": "2026-02-06", "contentBlocks": []}
		if task_name == "plan_content_blocks_repair":
			return {
				"schemaVersion": "2026-02-06",
				"contentBlocks": [
					{
						"blockId": "b0",
						"idx": 0,
						"title": "Intro",
						"startMs": 0,
						"endMs": 10_000,
						"highlights": [
							{
								"highlightId": "h0",
								"idx": 0,
								"text": "Hello",
								"startMs": 1000,
								"endMs": 5000,
								"keyframes": [{"timeMs": 2000}],
							}
						],
					}
				],
			}
		if task_name == "plan_mindmap":
			return {
				"schemaVersion": "2026-02-06",
				"mindmap": {
					"nodes": [
						{"id": "n0", "type": "root", "label": "Video", "level": 0, "data": {}},
						{"id": "n1", "type": "topic", "label": "Intro", "level": 1, "data": {"targetBlockId": "b0"}},
					],
					"edges": [{"id": "e0", "source": "n0", "target": "n1"}],
				},
			}
		raise AssertionError(f"unexpected task: {task_name}")


class _RepairingChunkProvider:
	def __init__(self):
		self.calls: list[str] = []

	def generate_json(self, task_name: str, input_dict: dict, *, max_tokens: int | None = None) -> dict:  # noqa: ARG002
		self.calls.append(task_name)
		if task_name == "chunk_summary":
			return {"chunkId": "bad", "startMs": 0, "endMs": 10, "summary": "", "points": [], "terms": [], "keyMoments": []}
		if task_name == "chunk_summary_repair":
			return {
				"chunkId": "c_0_60000",
				"startMs": 0,
				"endMs": 60000,
				"summary": "Repaired summary",
				"points": [{"text": "Repaired point", "importance": 2}],
				"terms": [],
				"keyMoments": [{"timeMs": 1000, "label": "slide"}],
			}
		raise AssertionError(f"unexpected task: {task_name}")


class _RepairingRequestProvider:
	def __init__(self):
		self.calls: list[str] = []

	def generate_json(self, task_name: str, input_dict: dict, *, max_tokens: int | None = None) -> dict:  # noqa: ARG002
		self.calls.append(task_name)
		if task_name == "plan_content_blocks":
			return {"schemaVersion": "2026-02-06", "contentBlocks": []}
		if task_name == "plan_content_blocks_repair":
			return {
				"schemaVersion": "2026-02-06",
				"contentBlocks": [
					{
						"blockId": "b0",
						"idx": 0,
						"title": "Intro",
						"startMs": 0,
						"endMs": 10_000,
						"highlights": [],
					},
				],
			}
		if task_name == "plan_mindmap":
			return {
				"schemaVersion": "2026-02-06",
				"mindmap": {"nodes": [{"id": "n0", "type": "root", "label": "Root", "level": 0, "data": {}}], "edges": []},
			}
		raise AssertionError(f"unexpected task: {task_name}")


def test_plan_validate_normalizes_near_miss_payload() -> None:
	plan = {
		"content_blocks": [
			{
				"id": 0,
				"idx": "0",
				"title": "Intro",
				"timeRange": {"startMs": "0", "endMs": 10_000},
				"highlights": [
					{
						"id": 1,
						"idx": 0,
						"quote": "Key point",
						"timeMs": 10_000,
					}
				],
			},
		],
		"mindmap": {"nodes": [{"id": "n1", "data": {"targetBlockId": 0}}], "edges": []},
	}

	out = validate_plan(plan)
	assert out.get("schemaVersion")
	blocks = out.get("contentBlocks")
	assert isinstance(blocks, list) and len(blocks) == 1
	b0 = blocks[0]
	assert b0["blockId"] == "b0"
	assert b0["idx"] == 0
	assert b0["startMs"] == 0 and b0["endMs"] == 10_000
	assert isinstance(b0.get("highlights"), list) and len(b0["highlights"]) == 1
	h0 = b0["highlights"][0]
	assert h0["highlightId"]
	assert h0["idx"] == 0
	assert isinstance(h0.get("keyframe"), dict)
	# 10_000 must be clamped into [0, 10_000) => 9_999
	assert h0["keyframe"]["timeMs"] == 9_999

	nodes = out.get("mindmap", {}).get("nodes")
	assert isinstance(nodes, list)
	assert nodes[0].get("data", {}).get("targetBlockId") == "b0"


def test_plan_validate_parses_stringified_mindmap_entries() -> None:
	plan = {
		"schemaVersion": "2026-02-06",
		"contentBlocks": [
			{
				"blockId": "b0",
				"idx": 0,
				"title": "Intro",
				"startMs": 0,
				"endMs": 10_000,
				"highlights": [],
			}
		],
		"mindmap": {
			"nodes": [
				"{\"id\":\"n0\",\"type\":\"root\",\"label\":\"Root\",\"level\":0,\"data\":{}}",
				"{\"id\":\"n1\",\"type\":\"topic\",\"label\":\"Intro\",\"level\":1,\"data\":{\"targetBlockId\":\"b0\"}}",
			],
			"edges": ["{\"id\":\"e0\",\"source\":\"n0\",\"target\":\"n1\"}"],
		},
	}

	out = validate_plan(plan)
	nodes = out.get("mindmap", {}).get("nodes")
	edges = out.get("mindmap", {}).get("edges")

	assert isinstance(nodes, list)
	assert nodes[0]["id"] == "n0"
	assert nodes[1]["data"]["targetBlockId"] == "b0"
	assert isinstance(edges, list)
	assert edges[0]["source"] == "n0"


def test_plan_validate_parses_objectish_mindmap_entries() -> None:
	plan = {
		"schemaVersion": "2026-02-06",
		"contentBlocks": [
			{
				"blockId": "b0",
				"idx": 0,
				"title": "Intro",
				"startMs": 0,
				"endMs": 10_000,
				"highlights": [],
			}
		],
		"mindmap": {
			"nodes": [
				'id: "root", type: "root", label: "根节点", level: 0, data: {}',
				'id: "topic-1", type: "topic", label: "AI执行工具与风险", level: 1, data: { targetBlockId: "b0" }',
			],
			"edges": ['id: "edge-1", source: "root", target: "topic-1"'],
		},
	}

	out = validate_plan(plan)
	nodes = out.get("mindmap", {}).get("nodes")
	edges = out.get("mindmap", {}).get("edges")

	assert isinstance(nodes, list)
	assert nodes[0]["id"] == "root"
	assert nodes[1]["data"]["targetBlockId"] == "b0"
	assert isinstance(edges, list)
	assert edges[0]["id"] == "edge-1"


def test_generate_plan_placeholder_escape_hatch() -> None:
	os.environ.pop("PLAN_PROVIDER", None)
	try:
		_set_env(PLAN_PROVIDER="placeholder")
		transcript = _mock_transcript()
		out = generate_plan(transcript=transcript)
		assert isinstance(out.get("contentBlocks"), list) and len(out["contentBlocks"]) >= 1
		assert isinstance(out.get("mindmap"), dict)
	finally:
		os.environ.pop("PLAN_PROVIDER", None)


def test_generate_plan_invalid_llm_output_maps_reason() -> None:
	provider = _StubProvider({"schemaVersion": "2026-02-06", "contentBlocks": [], "mindmap": {"nodes": [], "edges": []}})
	transcript = _mock_transcript()
	with pytest.raises(AnalyzeError) as ei:
		generate_plan(transcript=transcript, provider=provider)
	assert ei.value.code == ErrorCode.JOB_STAGE_FAILED
	assert ei.value.details.get("reason") == "invalid_llm_output"
	task = ei.value.details.get("task")
	assert isinstance(task, str) and task.startswith("plan_content_blocks")


def test_llm_provider_invalid_json_always_dumps_raw_output(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
	monkeypatch.setenv("DATA_DIR", str(tmp_path))
	def handler(_: httpx.Request) -> httpx.Response:
		return httpx.Response(200, content=_openai_sse_body("not-json"), headers={"Content-Type": "text/event-stream"})

	transport = httpx.MockTransport(handler)
	_set_env(
		LLM_API_BASE="https://example.invalid",
		LLM_API_KEY="sk-test-SECRET",
		LLM_MODEL="minimax-2.1",
		LLM_TIMEOUT_S="5",
	)
	provider = llm_provider_from_env(transport=transport)

	with pytest.raises(AnalyzeError) as ei:
		provider.generate_json("plan", {"messages": [{"role": "user", "content": "{}"}]})

	err = ei.value
	assert err.details.get("reason") == "invalid_llm_output"
	dump_ref = err.details.get("dumpRef")
	assert isinstance(dump_ref, str) and dump_ref
	dump_path = tmp_path / dump_ref
	assert dump_path.exists()
	assert dump_path.read_text("utf-8") == "not-json"


def test_build_repair_request_includes_raw_validation_error() -> None:
	req = build_repair_request(
		task_name="plan_mindmap",
		schema_summary="schema summary",
		source_text='{"bad":true}',
		validation_issue={"reason": "invalid_llm_output", "error": "8 validation errors for PlanOutput"},
		validation_error_text="8 validation errors for PlanOutput\nmindmap.nodes.0\n  Input should be a valid dictionary or instance of PlanMindmapNode",
		attempt=1,
		max_attempts=3,
		output_language="zh-Hans",
	)

	payload = req.get("userPayload")
	assert isinstance(payload, dict)
	assert payload.get("validationError", "").startswith("8 validation errors for PlanOutput")
	assert "mindmap.nodes.0" in payload.get("validationError", "")
	assert payload.get("outputLanguage") == "zh-Hans"


def test_persist_plan_artifacts_writes_project_files(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
	monkeypatch.setenv("DATA_DIR", str(tmp_path))

	from core.app.worker.worker_loop import _persist_plan_artifacts

	_persist_plan_artifacts(
		project_id="proj-1",
		job_id="job-1",
		payload={
			"schemaVersion": "2026-02-06",
			"contentBlocks": [{"blockId": "b0", "idx": 0, "title": "Intro", "startMs": 0, "endMs": 10, "highlights": []}],
			"mindmap": {"nodes": [{"id": "n0", "type": "root", "label": "Root", "level": 0, "data": {}}], "edges": []},
		},
	)

	base_dir = tmp_path / "proj-1" / "artifacts" / "plan" / "job-1"
	assert (base_dir / "manifest.json").exists()
	assert (base_dir / "content_blocks.json").exists()
	assert (base_dir / "mindmap.json").exists()

	manifest = (base_dir / "manifest.json").read_text("utf-8")
	content_blocks = (base_dir / "content_blocks.json").read_text("utf-8")
	mindmap = (base_dir / "mindmap.json").read_text("utf-8")

	assert '"projectId":"proj-1"' in manifest
	assert '"contentBlocks"' in content_blocks
	assert '"mindmap"' in mindmap


def test_persist_plan_failure_trace_writes_trace_copy(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
	monkeypatch.setenv("DATA_DIR", str(tmp_path))

	from core.app.worker.worker_loop import _persist_plan_failure_trace

	trace_rel = "logs/llm_json_repair/plan/failure.json"
	trace_path = tmp_path / trace_rel
	trace_path.parent.mkdir(parents=True, exist_ok=True)
	trace_path.write_text('{"task":"plan_mindmap","sourceOutput":"raw"}', encoding="utf-8")

	_persist_plan_failure_trace(
		project_id="proj-1",
		job_id="job-1",
		details={"task": "plan_mindmap", "traceRef": trace_rel, "reason": "invalid_llm_output"},
	)

	failure_path = tmp_path / "proj-1" / "artifacts" / "plan" / "job-1" / "mindmap_repair_failed.json"
	assert failure_path.exists()
	text = failure_path.read_text("utf-8")
	assert '"traceRef":"logs/llm_json_repair/plan/failure.json"' in text
	assert '"repairTrace"' in text


def test_plan_request_logging_callback_captures_initial_and_repair_requests() -> None:
	from core.app.pipeline.llm_plan import generate_plan

	provider = _RepairingRequestProvider()
	requests: list[dict] = []

	plan = generate_plan(
		transcript=_mock_transcript(),
		provider=provider,
		on_request_ready=requests.append,
	)

	assert plan["contentBlocks"][0]["blockId"] == "b0"
	assert [req.get("phase") for req in requests if req.get("task") == "plan_content_blocks"] == ["initial", None]
	assert any(req.get("repairTask") == "plan_content_blocks_repair" for req in requests)
	assert any(isinstance(req.get("request"), dict) for req in requests)


def test_persist_plan_request_event_writes_project_files(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
	monkeypatch.setenv("DATA_DIR", str(tmp_path))

	from core.app.worker.worker_loop import _persist_plan_chain_metadata, _persist_plan_request_event

	_persist_plan_chain_metadata(
		project_id="proj-1",
		job_id="job-1",
		chain_type="short_video",
		duration_ms=12_345,
		summaries_count=0,
	)
	_persist_plan_request_event(
		project_id="proj-1",
		job_id="job-1",
		chain_type="short_video",
		event={"task": "plan_content_blocks", "phase": "initial", "request": {"messages": []}},
		sequence=1,
	)

	base_dir = tmp_path / "proj-1" / "artifacts" / "plan" / "job-1"
	chain_path = base_dir / "analysis_chain.json"
	request_path = base_dir / "llm_requests" / "01-plan_content_blocks.json"
	assert chain_path.exists()
	assert request_path.exists()
	assert '"chainType":"short_video"' in chain_path.read_text("utf-8")
	assert '"phase":"initial"' in request_path.read_text("utf-8")


def test_generate_plan_auto_repairs_schema_failure_and_logs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
	monkeypatch.setenv("DATA_DIR", str(tmp_path))
	provider = _RepairingPlanProvider()
	transcript = _mock_transcript()
	out = generate_plan(transcript=transcript, provider=provider)

	assert provider.calls == ["plan_content_blocks", "plan_content_blocks_repair", "plan_mindmap"]
	assert len(out.get("contentBlocks") or []) == 1
	assert out["contentBlocks"][0]["blockId"] == "b0"
	trace_dir = tmp_path / "logs" / "llm_json_repair" / "plan"
	traces = list(trace_dir.glob("*.json"))
	assert traces
	trace_text = traces[0].read_text("utf-8")
	assert "sourceOutput" in trace_text
	assert "repairResponse" in trace_text or "repairedOutput" in trace_text


def test_pipeline_timing_writes_project_artifact(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
	monkeypatch.setenv("DATA_DIR", str(tmp_path))
	with time_pipeline_step(project_id="proj-1", task_id="job-1", step="plan"):
		append_pipeline_timing(project_id="proj-1", task_id="job-1", step="plan.inner", duration_ms=12)

	log_path = tmp_path / "proj-1" / "artifacts" / "job-1" / "timings.jsonl"
	assert log_path.exists()
	text = log_path.read_text("utf-8")
	assert '"projectId":"proj-1"' in text
	assert '"taskId":"job-1"' in text
	assert '"step":"plan"' in text
