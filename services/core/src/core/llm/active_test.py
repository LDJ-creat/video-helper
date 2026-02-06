from __future__ import annotations

import time
import logging
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)
@dataclass(frozen=True)
class LLMActiveTestError(RuntimeError):
	reason: str




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

	start = time.perf_counter()

	payload: dict[str, Any] = {
		"model": model,
		"messages": [{"role": "user", "content": "ping for connectivity test"}],
		"max_tokens": 20,
		"temperature": 0.1,
	}

	client = httpx.Client(
		timeout=max(10.0, float(timeout_s)),
		transport=transport,
		headers={
			"Authorization": f"Bearer {api_key}",
			"Content-Type": "application/json",
			"Accept": "application/json",
		},
	)
	try:
		resp = client.post(base_url, json=payload)
		logger.warning("LLM connectivity test response status: %s", resp.status_code)
		logger.warning("LLM connectivity test response data: %s", resp.text)
	except httpx.RequestError as e:
		logger.error("LLM connectivity test request error: %s", str(e))
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
