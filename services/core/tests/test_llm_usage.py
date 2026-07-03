from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.app.pipeline.llm_usage import (
	aggregate_llm_usage,
	append_llm_usage_record,
	normalize_anthropic_usage,
	normalize_openai_usage,
	resolve_usage_for_record,
	task_to_stage,
	unavailable_usage,
)
from core.app.pipeline.llm_usage_context import clear_llm_usage_context, set_llm_usage_context


def test_normalize_openai_usage() -> None:
	out = normalize_openai_usage({"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15})
	assert out is not None
	assert out.prompt_tokens == 10
	assert out.completion_tokens == 5
	assert out.total_tokens == 15
	assert out.source == "api"


def test_normalize_anthropic_usage() -> None:
	out = normalize_anthropic_usage(input_tokens=100, output_tokens=40)
	assert out is not None
	assert out.prompt_tokens == 100
	assert out.completion_tokens == 40
	assert out.total_tokens == 140


def test_task_to_stage_repair() -> None:
	assert task_to_stage("plan_content_blocks_repair") == "analyze"
	assert task_to_stage("chunk_summary") == "chunk_summaries"


def test_append_and_aggregate_llm_usage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	monkeypatch.setenv("DATA_DIR", str(tmp_path))
	set_llm_usage_context(project_id="proj-1", job_id="job-1")
	try:
		from core.app.pipeline.llm_usage import NormalizedLlmUsage

		append_llm_usage_record(
			task="plan_content_blocks",
			model="test-model",
			usage=NormalizedLlmUsage(100, 50, 150, "api", "openai_compat"),
		)
		append_llm_usage_record(
			task="chunk_summary",
			model="test-model",
			usage=NormalizedLlmUsage(200, 80, 280, "api", "openai_compat"),
		)
	finally:
		clear_llm_usage_context()

	path = tmp_path / "proj-1" / "artifacts" / "job-1" / "llm_usage.jsonl"
	assert path.exists()
	agg = aggregate_llm_usage(path)
	assert agg["available"] is True
	assert agg["total"] == 430
	assert agg["byTask"]["plan_content_blocks"]["total"] == 150
	assert agg["byStage"]["analyze"]["total"] == 150
	assert agg["byStage"]["chunk_summaries"]["total"] == 280


def test_resolve_usage_fallback_estimate() -> None:
	out = resolve_usage_for_record(
		usage=None,
		provider_kind="openai_compat",
		prompt_chars=400,
		completion_chars=200,
	)
	assert out.source == "estimated"
	assert out.total_tokens == 150


def test_resolve_usage_unavailable_when_fallback_off(monkeypatch: pytest.MonkeyPatch) -> None:
	monkeypatch.setenv("LLM_USAGE_ESTIMATE_FALLBACK", "0")
	out = resolve_usage_for_record(
		usage=unavailable_usage(provider_kind="openai_compat"),
		provider_kind="openai_compat",
		prompt_chars=400,
		completion_chars=200,
	)
	assert out.source == "unavailable"
	assert out.total_tokens is None


def test_aggregate_missing_file(tmp_path: Path) -> None:
	agg = aggregate_llm_usage(tmp_path / "missing.jsonl")
	assert agg["available"] is False
