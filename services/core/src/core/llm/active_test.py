from __future__ import annotations

import os
import time
import logging
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)
@dataclass(frozen=True)
class LLMActiveTestError(RuntimeError):
	reason: str


def _hash_secret(text: str) -> str:
	import hashlib

	return hashlib.sha256((text or "").encode("utf-8", errors="ignore")).hexdigest()


def _is_anthropic_base_url(base_url: str) -> bool:
	try:
		p = urlparse(base_url)
		host = (p.netloc or "").lower()
		return host.endswith("anthropic.com")
	except Exception:
		return False


def _resolve_openai_compat_endpoint(base_url: str) -> str:
	url = (base_url or "").strip().rstrip("/")
	lower = url.lower()
	if lower.endswith("/v1"):
		return url + "/chat/completions"
	if lower.endswith("/chat/completions") or lower.endswith("/v1/chat/completions") or lower.endswith("/responses") or lower.endswith("/v1/responses"):
		return url
	return url + "/v1/chat/completions"


def _resolve_anthropic_endpoint(base_url: str) -> str:
	url = (base_url or "").strip().rstrip("/")
	lower = url.lower()
	if lower.endswith("/v1/messages"):
		return url
	if lower.endswith("/v1"):
		return url + "/messages"
	return url + "/v1/messages"



def run_llm_connectivity_test(
	*,
	base_url: str,
	api_key: str,
	model: str,
	timeout_s: float = 10.0,
	transport: httpx.BaseTransport | None = None,
) -> int:
	"""Perform a minimal request to validate connectivity.

	Returns latency in ms on success.
	Raises LLMActiveTestError with stable reasons on failure.
	"""
	logger.debug("LLM connectivity test: base_url=%s", base_url)
	logger.debug("LLM connectivity test: model=%s", model)
	logger.debug("LLM connectivity test: api_key_hash=%s", _hash_secret(api_key)[:12])
  
	start = time.perf_counter()

	use_anthropic = _is_anthropic_base_url(base_url)
	url = _resolve_anthropic_endpoint(base_url) if use_anthropic else _resolve_openai_compat_endpoint(base_url)

	if use_anthropic:
		version = (os.environ.get("ANTHROPIC_VERSION") or "2023-06-01").strip() or "2023-06-01"
		payload: dict[str, Any] = {
			"model": model,
			"max_tokens": 16,
			"messages": [{"role": "user", "content": "ping"}],
		}
		headers = {
			"x-api-key": api_key,
			"anthropic-version": version,
			"Content-Type": "application/json",
			"Accept": "application/json",
		}
	else:
		payload = {
			"model": model,
			"messages": [{"role": "user", "content": "ping"}],
		}
		headers = {
			"Authorization": f"Bearer {api_key}",
			"Content-Type": "application/json",
			"Accept": "application/json",
		}

	client = httpx.Client(timeout=max(10.0, float(timeout_s)), transport=transport, headers=headers)
	try:
		resp = client.post(url, json=payload)
		logger.warning("LLM connectivity test response status: %s", resp.status_code)
		# Never log full body; it may include sensitive info.
		logger.warning("LLM connectivity test response len: %s", len(resp.text or ""))
	except httpx.RequestError as e:
		logger.error("LLM connectivity test request error: %s", str(e))
		raise LLMActiveTestError(reason="provider_unavailable") from e
	finally:
		client.close()

	latency_ms = int((time.perf_counter() - start) * 1000)
	status = int(resp.status_code)
	if status == 401:
		raise LLMActiveTestError(reason="invalid_credentials")
	if status == 403:
		raise LLMActiveTestError(reason="invalid_credentials")
	if status == 404:
		raise LLMActiveTestError(reason="model_not_found")
	if status >= 500:
		raise LLMActiveTestError(reason="provider_unavailable")
	if status >= 400:
		# Best-effort parse, but keep stable reason.
		raise LLMActiveTestError(reason="provider_unavailable")

	return max(0, latency_ms)
