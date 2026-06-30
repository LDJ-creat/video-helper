from __future__ import annotations

import os
import time
import logging
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx

from core.llm.http_headers import http_header_value_error
from core.llm.openai_compat_url import resolve_openai_compat_chat_endpoint

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
	return resolve_openai_compat_chat_endpoint(base_url)


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

	5xx responses are retried up to 2 times (3 total attempts) with 1–2 s
	backoff to handle transient provider unavailability.
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

	if http_header_value_error(api_key or ""):
		raise LLMActiveTestError("invalid_api_key")

	if use_anthropic:
		version = (os.environ.get("ANTHROPIC_VERSION") or "2023-06-01").strip() or "2023-06-01"
		payload: dict[str, Any] = {
			"model": model,
			"max_tokens": 2,
			"stream": True,
			"messages": [{"role": "user", "content": "Reply with only the letter 'O'."}],
		}
		headers = {
			"x-api-key": api_key,
			"anthropic-version": version,
			"Content-Type": "application/json",
			"Accept": "text/event-stream",
		}
	else:
		payload = {
			"model": model,
			"max_tokens": 2,
			"stream": True,
			"messages": [{"role": "user", "content": "Reply with only the letter 'O'."}],
		}
		headers = {
			"Authorization": f"Bearer {api_key}",
			"Content-Type": "application/json",
			"Accept": "text/event-stream",
		}

	_t_payload = time.perf_counter()
	logger.info(
		"LLM connectivity test payload-built host=%s payload_ms=%.1f",
		_safe_host_for_log(base_url),
		(_t_payload - start) * 1000,
	)

	# trust_env=False: skip Windows WPAD / system proxy detection which can add ~2s latency
	try:
		client = httpx.Client(timeout=timeout, transport=transport, headers=headers, trust_env=False)
	except UnicodeEncodeError as exc:
		raise LLMActiveTestError("invalid_api_key") from exc
	_t_client = time.perf_counter()
	logger.info(
		"LLM connectivity test client-created host=%s client_init_ms=%.1f total_so_far=%.1f",
		_safe_host_for_log(base_url),
		(_t_client - _t_payload) * 1000,
		(_t_client - start) * 1000,
	)

	_MAX_RETRIES = 2  # 3 total attempts for 5xx
	last_status: int = 0

	try:
		for attempt in range(_MAX_RETRIES + 1):
			if attempt > 0:
				backoff_s = 1.0 * attempt  # 1s, 2s
				logger.warning(
					"LLM connectivity test retry host=%s attempt=%s/%s backoff_s=%.1f last_status=%s",
					_safe_host_for_log(base_url),
					attempt,
					_MAX_RETRIES,
					backoff_s,
					last_status,
				)
				time.sleep(backoff_s)

			try:
				# Use streaming: only wait for the first chunk to confirm connectivity.
				# This avoids waiting for the full response body (reasoning models can
				# take 10+ seconds to complete generation, but connectivity is confirmed
				# as soon as the first byte arrives).
				status: int = 0
				with client.stream("POST", url, json=payload) as stream:
					status = stream.status_code
					# Read just the first chunk to confirm the connection works.
					# For error responses (4xx/5xx) the body may be empty, which is fine.
					for _ in stream.iter_bytes():
						break
				elapsed_ms = int((time.perf_counter() - _t_client) * 1000)
				logger.info(
					"LLM connectivity test response host=%s status=%s elapsed_ms=%s (streaming, first-chunk) attempt=%s",
					_safe_host_for_log(base_url),
					status,
					elapsed_ms,
					attempt,
				)
				last_status = status
			except httpx.ReadTimeout as e:
				elapsed_ms = int((time.perf_counter() - _t_client) * 1000)
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
				elapsed_ms = int((time.perf_counter() - _t_client) * 1000)
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
				elapsed_ms = int((time.perf_counter() - _t_client) * 1000)
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
				elapsed_ms = int((time.perf_counter() - _t_client) * 1000)
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

			# Non-retryable: 4xx errors exit immediately.
			if status == 401:
				raise LLMActiveTestError(reason="invalid_credentials")
			if status == 403:
				raise LLMActiveTestError(reason="invalid_credentials")
			if status == 404:
				raise LLMActiveTestError(reason="model_not_found")
			if 400 <= status < 500:
				raise LLMActiveTestError(reason="provider_unavailable")

			# 5xx: retry if attempts remain.
			if status >= 500 and attempt < _MAX_RETRIES:
				continue

			# 5xx exhausted, or success.
			if status >= 500:
				raise LLMActiveTestError(reason="provider_unavailable")

			return max(0, int((time.perf_counter() - _t_client) * 1000))

		# Exhausted all retries (loop completed without returning/raising).
		raise LLMActiveTestError(reason="provider_unavailable")
	finally:
		client.close()
