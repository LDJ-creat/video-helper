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


def _connectivity_read_timeout_s(explicit_timeout_s: float) -> float:
	"""Upper bound for waiting on first response byte from chat/completions (often >10s for LLMs)."""

	raw = (os.environ.get("LLM_CONNECTIVITY_TEST_TIMEOUT_S") or "").strip()
	if raw:
		try:
			v = float(raw)
			return max(15.0, min(300.0, v))
		except ValueError:
			pass
	return max(15.0, min(300.0, float(explicit_timeout_s)))


def _safe_host_for_log(base_url: str) -> str:
	try:
		return (urlparse(base_url).netloc or "").lower() or "(no-host)"
	except Exception:
		return "(bad-url)"


def run_llm_connectivity_test(
	*,
	base_url: str,
	api_key: str,
	model: str,
	timeout_s: float = 45.0,
	transport: httpx.BaseTransport | None = None,
) -> int:
	"""Perform a minimal request to validate connectivity.

	Returns latency in ms on success.
	Raises LLMActiveTestError with stable reasons on failure.
	"""
	read_s = _connectivity_read_timeout_s(timeout_s)
	connect_s = min(30.0, max(10.0, read_s * 0.5))
	timeout = httpx.Timeout(connect=connect_s, read=read_s, write=min(30.0, read_s), pool=10.0)

	use_anthropic = _is_anthropic_base_url(base_url)
	url = _resolve_anthropic_endpoint(base_url) if use_anthropic else _resolve_openai_compat_endpoint(base_url)
	key_fp = _hash_secret(api_key)[:12]

	logger.info(
		"LLM connectivity test start host=%s anthropic=%s model=%s post_url=%s timeout_connect_s=%.1f timeout_read_s=%.1f api_key_sha256_12=%s",
		_safe_host_for_log(base_url),
		use_anthropic,
		(model or "")[:120],
		url,
		connect_s,
		read_s,
		key_fp,
	)

	start = time.perf_counter()

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

	client = httpx.Client(timeout=timeout, transport=transport, headers=headers)
	try:
		resp = client.post(url, json=payload)
		elapsed_ms = int((time.perf_counter() - start) * 1000)
		logger.info(
			"LLM connectivity test response host=%s status=%s elapsed_ms=%s body_len=%s",
			_safe_host_for_log(base_url),
			resp.status_code,
			elapsed_ms,
			len(resp.text or ""),
		)
	except httpx.ReadTimeout as e:
		elapsed_ms = int((time.perf_counter() - start) * 1000)
		logger.error(
			"LLM connectivity test READ TIMEOUT host=%s post_url=%s model=%s elapsed_ms=%s timeout_read_s=%.1f "
			"err_type=%s err=%s (upstream slow or stalled; try LLM_CONNECTIVITY_TEST_TIMEOUT_S, e.g. 90)",
			_safe_host_for_log(base_url),
			url,
			(model or "")[:120],
			elapsed_ms,
			read_s,
			type(e).__name__,
			str(e),
		)
		raise LLMActiveTestError(reason="provider_unavailable") from e
	except httpx.ConnectTimeout as e:
		elapsed_ms = int((time.perf_counter() - start) * 1000)
		logger.error(
			"LLM connectivity test CONNECT TIMEOUT host=%s post_url=%s elapsed_ms=%s timeout_connect_s=%.1f err_type=%s err=%s",
			_safe_host_for_log(base_url),
			url,
			elapsed_ms,
			connect_s,
			type(e).__name__,
			str(e),
		)
		raise LLMActiveTestError(reason="provider_unavailable") from e
	except httpx.TimeoutException as e:
		elapsed_ms = int((time.perf_counter() - start) * 1000)
		logger.error(
			"LLM connectivity test OTHER TIMEOUT host=%s post_url=%s model=%s elapsed_ms=%s err_type=%s err=%s",
			_safe_host_for_log(base_url),
			url,
			(model or "")[:120],
			elapsed_ms,
			type(e).__name__,
			str(e),
		)
		raise LLMActiveTestError(reason="provider_unavailable") from e
	except httpx.RequestError as e:
		elapsed_ms = int((time.perf_counter() - start) * 1000)
		logger.error(
			"LLM connectivity test REQUEST ERROR host=%s post_url=%s model=%s elapsed_ms=%s err_type=%s err=%s",
			_safe_host_for_log(base_url),
			url,
			(model or "")[:120],
			elapsed_ms,
			type(e).__name__,
			str(e),
		)
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
