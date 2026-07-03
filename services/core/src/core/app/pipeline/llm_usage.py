from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from core.app.pipeline.llm_usage_context import get_llm_usage_context
from core.db.session import get_data_dir

LlmUsageSource = Literal["api", "estimated", "unavailable"]

_TASK_STAGE_MAP: dict[str, str] = {
	"plan": "analyze",
	"plan_content_blocks": "analyze",
	"plan_content_blocks_repair": "analyze",
	"plan_mindmap": "analyze",
	"plan_mindmap_repair": "analyze",
	"chunk_summary": "chunk_summaries",
	"chunk_summary_repair": "chunk_summaries",
	"keyframe_verify": "keyframe_verify",
}


@dataclass(frozen=True)
class NormalizedLlmUsage:
	prompt_tokens: int | None
	completion_tokens: int | None
	total_tokens: int | None
	source: LlmUsageSource
	provider_kind: str


def _env_bool(name: str, default: bool = False) -> bool:
	raw = (os.environ.get(name) or "").strip().lower()
	if raw in {"1", "true", "yes", "y", "on"}:
		return True
	if raw in {"0", "false", "no", "n", "off"}:
		return False
	return default


def _as_nonneg_int(value: object) -> int | None:
	if isinstance(value, bool):
		return None
	if isinstance(value, int) and value >= 0:
		return value
	if isinstance(value, float) and value >= 0:
		return int(value)
	return None


def normalize_openai_usage(usage: object) -> NormalizedLlmUsage | None:
	if not isinstance(usage, dict):
		return None
	prompt = _as_nonneg_int(usage.get("prompt_tokens"))
	completion = _as_nonneg_int(usage.get("completion_tokens"))
	total = _as_nonneg_int(usage.get("total_tokens"))
	if total is None and prompt is not None and completion is not None:
		total = prompt + completion
	if prompt is None and completion is None and total is None:
		return None
	return NormalizedLlmUsage(
		prompt_tokens=prompt,
		completion_tokens=completion,
		total_tokens=total,
		source="api",
		provider_kind="openai_compat",
	)


def normalize_anthropic_usage(*, input_tokens: object, output_tokens: object) -> NormalizedLlmUsage | None:
	prompt = _as_nonneg_int(input_tokens)
	completion = _as_nonneg_int(output_tokens)
	if prompt is None and completion is None:
		return None
	total = (prompt or 0) + (completion or 0) if (prompt is not None or completion is not None) else None
	return NormalizedLlmUsage(
		prompt_tokens=prompt,
		completion_tokens=completion,
		total_tokens=total,
		source="api",
		provider_kind="anthropic",
	)


def estimate_usage_from_lengths(*, prompt_chars: int, completion_chars: int) -> NormalizedLlmUsage:
	prompt = max(0, int(prompt_chars) // 4)
	completion = max(0, int(completion_chars) // 4)
	return NormalizedLlmUsage(
		prompt_tokens=prompt,
		completion_tokens=completion,
		total_tokens=prompt + completion,
		source="estimated",
		provider_kind="unknown",
	)


def unavailable_usage(*, provider_kind: str) -> NormalizedLlmUsage:
	return NormalizedLlmUsage(
		prompt_tokens=None,
		completion_tokens=None,
		total_tokens=None,
		source="unavailable",
		provider_kind=provider_kind,
	)


def task_to_stage(task_name: str) -> str:
	task = (task_name or "").strip()
	if not task:
		return "unknown"
	if task in _TASK_STAGE_MAP:
		return _TASK_STAGE_MAP[task]
	if task.endswith("_repair"):
		base = task[: -len("_repair")]
		if base in _TASK_STAGE_MAP:
			return _TASK_STAGE_MAP[base]
	return task


def llm_usage_artifact_path(*, data_dir: Path, project_id: str, job_id: str) -> Path:
	return data_dir.resolve() / project_id / "artifacts" / job_id / "llm_usage.jsonl"


def append_llm_usage_record(
	*,
	task: str,
	model: str,
	usage: NormalizedLlmUsage,
	attempt: int = 1,
	duration_ms: int | None = None,
	project_id: str | None = None,
	job_id: str | None = None,
) -> None:
	ctx = get_llm_usage_context()
	pid = project_id or (ctx.project_id if ctx else None)
	jid = job_id or (ctx.job_id if ctx else None)
	if not pid or not jid:
		return
	if usage.source == "unavailable":
		return

	try:
		data_dir = get_data_dir().resolve()
		path = llm_usage_artifact_path(data_dir=data_dir, project_id=pid, job_id=jid)
		if not path.is_relative_to(data_dir):
			return
		path.parent.mkdir(parents=True, exist_ok=True)
		record: dict[str, Any] = {
			"task": task,
			"stage": task_to_stage(task),
			"attempt": max(1, int(attempt)),
			"model": model,
			"providerKind": usage.provider_kind,
			"promptTokens": usage.prompt_tokens,
			"completionTokens": usage.completion_tokens,
			"totalTokens": usage.total_tokens,
			"source": usage.source,
			"tsMs": int(time.time() * 1000),
		}
		if duration_ms is not None:
			record["durationMs"] = max(0, int(duration_ms))
		with path.open("a", encoding="utf-8") as f:
			f.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
	except Exception:
		return


def _read_usage_rows(path: Path) -> list[dict[str, Any]]:
	if not path.exists():
		return []
	rows: list[dict[str, Any]] = []
	try:
		for line in path.read_text(encoding="utf-8").splitlines():
			line = line.strip()
			if not line:
				continue
			try:
				obj = json.loads(line)
			except json.JSONDecodeError:
				continue
			if isinstance(obj, dict):
				rows.append(obj)
	except OSError:
		return []
	return rows


def _merge_bucket(buckets: dict[str, dict[str, Any]], key: str, row: dict[str, Any]) -> None:
	entry = buckets.setdefault(
		key,
		{"calls": 0, "prompt": 0, "completion": 0, "total": 0, "estimatedCalls": 0, "apiCalls": 0},
	)
	entry["calls"] = int(entry.get("calls") or 0) + 1
	prompt = _as_nonneg_int(row.get("promptTokens"))
	completion = _as_nonneg_int(row.get("completionTokens"))
	total = _as_nonneg_int(row.get("totalTokens"))
	if prompt is not None:
		entry["prompt"] = int(entry.get("prompt") or 0) + prompt
	if completion is not None:
		entry["completion"] = int(entry.get("completion") or 0) + completion
	if total is not None:
		entry["total"] = int(entry.get("total") or 0) + total
	source = str(row.get("source") or "")
	if source == "estimated":
		entry["estimatedCalls"] = int(entry.get("estimatedCalls") or 0) + 1
	elif source == "api":
		entry["apiCalls"] = int(entry.get("apiCalls") or 0) + 1


def aggregate_llm_usage(path: Path) -> dict[str, Any]:
	rows = _read_usage_rows(path)
	if not rows:
		return {"available": False, "reason": "no_llm_usage_artifact"}

	prompt_sum = 0
	completion_sum = 0
	total_sum = 0
	calls_with_usage = 0
	calls_missing_usage = 0
	estimated_calls = 0
	api_calls = 0
	by_task: dict[str, dict[str, Any]] = {}
	by_stage: dict[str, dict[str, Any]] = {}

	for row in rows:
		prompt = _as_nonneg_int(row.get("promptTokens"))
		completion = _as_nonneg_int(row.get("completionTokens"))
		total = _as_nonneg_int(row.get("totalTokens"))
		source = str(row.get("source") or "")
		if source == "estimated":
			estimated_calls += 1
		elif source == "api":
			api_calls += 1

		if total is None and prompt is None and completion is None:
			calls_missing_usage += 1
		else:
			calls_with_usage += 1
			if prompt is not None:
				prompt_sum += prompt
			if completion is not None:
				completion_sum += completion
			if total is not None:
				total_sum += total
			elif prompt is not None and completion is not None:
				total_sum += prompt + completion

		task = str(row.get("task") or "unknown")
		stage = str(row.get("stage") or task_to_stage(task))
		_merge_bucket(by_task, task, row)
		_merge_bucket(by_stage, stage, row)

	if estimated_calls > 0 and api_calls > 0:
		agg_source = "mixed"
	elif estimated_calls > 0:
		agg_source = "estimated"
	elif api_calls > 0:
		agg_source = "api"
	else:
		agg_source = "unavailable"

	return {
		"available": True,
		"prompt": prompt_sum,
		"completion": completion_sum,
		"total": total_sum,
		"source": agg_source,
		"calls": len(rows),
		"callsWithUsage": calls_with_usage,
		"callsMissingUsage": calls_missing_usage,
		"byTask": by_task,
		"byStage": by_stage,
	}


def resolve_usage_for_record(
	*,
	usage: NormalizedLlmUsage | None,
	provider_kind: str,
	prompt_chars: int,
	completion_chars: int,
) -> NormalizedLlmUsage:
	if usage is not None and usage.source == "api":
		return usage
	if _env_bool("LLM_USAGE_ESTIMATE_FALLBACK", True):
		return estimate_usage_from_lengths(prompt_chars=prompt_chars, completion_chars=completion_chars)
	return unavailable_usage(provider_kind=provider_kind)
