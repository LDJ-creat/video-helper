from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass


@dataclass(frozen=True)
class LlmUsageContext:
	project_id: str
	job_id: str


_llm_usage_ctx: ContextVar[LlmUsageContext | None] = ContextVar("llm_usage_ctx", default=None)


def set_llm_usage_context(*, project_id: str, job_id: str) -> None:
	_llm_usage_ctx.set(LlmUsageContext(project_id=str(project_id), job_id=str(job_id)))


def clear_llm_usage_context() -> None:
	_llm_usage_ctx.set(None)


def get_llm_usage_context() -> LlmUsageContext | None:
	return _llm_usage_ctx.get()
