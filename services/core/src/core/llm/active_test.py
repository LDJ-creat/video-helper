from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(frozen=True)
class LLMActiveTestError(RuntimeError):
	reason: str


def _endpoint_url(base_url: str) -> str:
	base = (base_url or "").strip().rstrip("/")
	lower = base.lower()
	if lower.endswith("/v1"):
		return base + "/chat/completions"
	if lower.endswith("/chat/completions") or lower.endswith("/v1/chat/completions"):
		return base
	if lower.endswith("/responses") or lower.endswith("/v1/responses"):
		return base
	return base + "/v1/chat/completions"


def run_llm_connectivity_test(
	*,
	base_url: str,
	api_key: str,
	model: str,
	timeout_s: float = 10.0,
	transport: httpx.BaseTransport | None = None,
) -> int:
	"""Perform a minimal OpenAI-compatible request to validate connectivity.

	Returns latency in ms on success.
	Raises LLMActiveTestError with stable reasons on failure.
	"""

	url = _endpoint_url(base_url)
	start = time.perf_counter()

	payload: dict[str, Any] = {
		"model": model,
		"messages": [{"role": "user", "content": "ping"}],
		"max_tokens": 1,
		"temperature": 0,
	}

	client = httpx.Client(
		timeout=max(1.0, float(timeout_s)),
		transport=transport,
		headers={
			"Authorization": f"Bearer {api_key}",
			"Content-Type": "application/json",
			"Accept": "application/json",
		},
	)
	try:
		resp = client.post(url, json=payload)
	except httpx.RequestError as e:
		raise LLMActiveTestError(reason="provider_unavailable") from e
	finally:
		client.close()

	latency_ms = int((time.perf_counter() - start) * 1000)
	status = int(resp.status_code)
	if status == 401:
		raise LLMActiveTestError(reason="invalid_credentials")
	if status == 404:
		raise LLMActiveTestError(reason="model_not_found")
	if status >= 500:
		raise LLMActiveTestError(reason="provider_unavailable")
	if status >= 400:
		# Best-effort parse, but keep stable reason.
		raise LLMActiveTestError(reason="provider_unavailable")

	return max(0, latency_ms)
