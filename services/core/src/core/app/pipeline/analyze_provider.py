from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
import time
import logging
from urllib.parse import urlparse
from typing import Any, Protocol

import httpx
from sqlalchemy.exc import OperationalError

from core.contracts.error_codes import ErrorCode
from core.db.repositories.llm_settings import get_llm_active, get_llm_provider_secret_ciphertext
from core.db.session import get_sessionmaker
from core.llm.catalog import find_provider, resolve_runtime_model_name
from core.llm.secrets_crypto import decrypt_api_key

logger = logging.getLogger(__name__)

class AnalyzeProvider(Protocol):
	def generate_json(self, task_name: str, input_dict: dict) -> dict: ...


@dataclass(frozen=True)
class LLMRuntimeConfig:
	provider_id: str | None
	api_base: str
	api_key: str
	model: str
	timeout_s: float


class AnalyzeError(Exception):
	"""Internal analyze error mapped to job.error.

	Must be safe to stringify (no API keys, no prompts).
	"""

	def __init__(self, *, code: ErrorCode, message: str, details: dict | None = None):
		super().__init__(message)
		self.code = code
		self.message = message
		self.details = details or {}

	def to_error(self) -> dict:
		return {"code": self.code, "message": self.message, "details": dict(self.details)}

	def __str__(self) -> str:
		# Ensure worker_loop logging remains safe.
		return self.message


def _env_str(name: str) -> str | None:
	raw = os.environ.get(name)
	if raw is None:
		return None
	raw = raw.strip()
	return raw or None


def _env_int(name: str, default: int) -> int:
	raw = _env_str(name)
	if raw is None:
		return default
	try:
		return int(raw)
	except ValueError:
		return default


def _env_bool(name: str, default: bool = False) -> bool:
	raw = (os.environ.get(name) or "").strip().lower()
	if raw in {"1", "true", "yes", "y", "on"}:
		return True
	if raw in {"0", "false", "no", "n", "off"}:
		return False
	return default


def _strip_code_fences(text: str) -> str:
	t = text.strip()
	if t.startswith("```"):
		# Drop first fence line
		lines = t.splitlines()
		if lines:
			lines = lines[1:]
			# Drop last fence if present
			if lines and lines[-1].strip().startswith("```"):
				lines = lines[:-1]
			return "\n".join(lines).strip()
	return t


def _extract_json_object(text: str) -> str | None:
	"""Best-effort extraction of the first JSON object from a string."""

	start = text.find("{")
	end = text.rfind("}")
	if start == -1 or end == -1 or end <= start:
		return None
	return text[start : end + 1]


def _hash_text(text: str) -> str:
	return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def _normalize_model_id(model: str) -> str:
	"""Normalize common shorthand model names to NVIDIA NIM OpenAI-compatible ids."""

	m = (model or "").strip()
	lower = m.lower().replace("_", "-")
	if lower in {"minimax-2.1", "minimax2.1", "minimax 2.1", "minimax-m2.1", "minimax-m2_1"}:
		return "minimaxai/minimax-m2.1"
	return m


class LLMAnalyzeProvider:
	"""OpenAI-compatible chat-completions style client.

	The exact base URL is provided via env and may point to NVIDIA-hosted endpoints.
	"""

	def __init__(
		self,
		*,
		api_base: str,
		api_key: str,
		model: str,
		timeout_s: float,
		transport: httpx.BaseTransport | None = None,
	):
		self._api_base = api_base.rstrip("/")
		self._api_key = api_key
		self._model = model
		self._timeout_s = max(1.0, float(timeout_s))
		self._transport = transport

		self._client = httpx.Client(
			timeout=self._timeout_s,
			transport=self._transport,
			headers={
				"Authorization": f"Bearer {self._api_key}",
				"Content-Type": "application/json",
				"Accept": "application/json",
			},
		)

	def _endpoint_url(self) -> str:
		# If user points directly to a path, respect it.
		lower = self._api_base.lower()
		if lower.endswith("/v1"):
			return self._api_base + "/chat/completions"
		if lower.endswith("/chat/completions") or lower.endswith("/v1/chat/completions") or lower.endswith("/responses") or lower.endswith("/v1/responses"):
			return self._api_base
		return self._api_base + "/v1/chat/completions"

	def generate_json(self, task_name: str, input_dict: dict) -> dict:
		messages = input_dict.get("messages")
		if not isinstance(messages, list) or not messages:
			raise AnalyzeError(code=ErrorCode.JOB_STAGE_FAILED, message="Invalid LLM input", details={"reason": "invalid_input", "task": task_name})

		payload: dict[str, Any] = {
			"model": self._model,
			"messages": messages,
			"temperature": 0.2,
			"response_format": {"type": "json_object"},
		}

		debug_enabled = _env_bool("LLM_DEBUG", False)
		debug_meta: dict[str, Any] = {}
		if debug_enabled:
			# Store only hashes/lengths, never raw prompts.
			joined = "\n".join(
				f"{m.get('role','')}: {m.get('content','')}" for m in messages if isinstance(m, dict)
			)
			debug_meta = {
				"task": task_name,
				"model": self._model,
				"endpoint": self._endpoint_url(),
				"promptHash": _hash_text(joined),
				"promptLen": len(joined),
			}

		# Default retries: reduces flakiness on providers with slow first-byte latency.
		max_attempts = max(1, _env_int("LLM_MAX_ATTEMPTS", 3))
		attempt = 0
		resp: httpx.Response | None = None
		while attempt < max_attempts:
			attempt += 1
			try:
				resp = self._client.post(self._endpoint_url(), json=payload)
			except httpx.TimeoutException:
				if attempt < max_attempts:
					# Exponential backoff (0.5s, 1s, 2s, 4s...) capped.
					time.sleep(min(8.0, 0.5 * (2 ** (attempt - 1))))
					continue
				details = {
					"reason": "timeout",
					"task": task_name,
					"attempt": attempt,
					"maxAttempts": max_attempts,
					"timeoutS": self._timeout_s,
				}
				if debug_enabled:
					details["debug"] = debug_meta
				raise AnalyzeError(code=ErrorCode.JOB_STAGE_FAILED, message="LLM request timed out", details=details)
			except httpx.RequestError as e:
				# Network/transport errors.
				if attempt < max_attempts:
					time.sleep(min(8.0, 0.5 * (2 ** (attempt - 1))))
					continue
				details = {
					"reason": "upstream_error",
					"task": task_name,
					"errorType": type(e).__name__,
					"attempt": attempt,
					"maxAttempts": max_attempts,
				}
				if debug_enabled:
					details["debug"] = debug_meta
				raise AnalyzeError(code=ErrorCode.JOB_STAGE_FAILED, message="LLM request failed", details=details)

			# Retry on transient upstream failures.
			status = int(resp.status_code)
			if status >= 500 and attempt < max_attempts:
				time.sleep(min(8.0, 0.5 * (2 ** (attempt - 1))))
				continue
			break

		assert resp is not None
		status = int(resp.status_code)
		if status == 401:
			details = {"reason": "missing_credentials", "task": task_name}
			if debug_enabled:
				details["debug"] = debug_meta
			raise AnalyzeError(code=ErrorCode.JOB_STAGE_FAILED, message="LLM unauthorized", details=details)
		if status == 429:
			details = {"reason": "rate_limited", "task": task_name}
			if debug_enabled:
				details["debug"] = debug_meta
			raise AnalyzeError(code=ErrorCode.JOB_STAGE_FAILED, message="LLM rate limited", details=details)
		if status in {402, 403}:
			details = {"reason": "quota_exhausted", "task": task_name}
			if debug_enabled:
				details["debug"] = debug_meta
			raise AnalyzeError(code=ErrorCode.RESOURCE_EXHAUSTED, message="LLM quota exhausted", details=details)
		if status >= 400:
			details = {"reason": "upstream_error", "task": task_name, "httpStatus": status}
			if debug_enabled:
				details["debug"] = debug_meta
			raise AnalyzeError(code=ErrorCode.JOB_STAGE_FAILED, message="LLM returned error", details=details)

		# Parse response.
		try:
			body = resp.json()
		except Exception:
			details = {"reason": "invalid_llm_output", "task": task_name, "httpStatus": status, "bodyLen": len(resp.text or "")}
			if debug_enabled:
				details["debug"] = debug_meta
			raise AnalyzeError(code=ErrorCode.JOB_STAGE_FAILED, message="LLM returned non-JSON response", details=details)

		parsed = _parse_openai_style_json(body)
		if not isinstance(parsed, dict):
			raise AnalyzeError(
				code=ErrorCode.JOB_STAGE_FAILED,
				message="LLM output is not a JSON object",
				details={"reason": "invalid_llm_output", "task": task_name},
			)
		return parsed


def _is_anthropic_base_url(api_base: str | None) -> bool:
	if not api_base:
		return False
	try:
		p = urlparse(api_base)
		host = (p.netloc or "").lower()
		return host.endswith("anthropic.com")
	except Exception:
		return False


class AnthropicAnalyzeProvider:
	"""Anthropic Messages API client (POST /v1/messages).

	Input: OpenAI-style messages: [{role, content}].
	Output: JSON object parsed from the assistant text.
	"""

	def __init__(
		self,
		*,
		api_base: str,
		api_key: str,
		model: str,
		timeout_s: float,
		transport: httpx.BaseTransport | None = None,
	):
		self._api_base = api_base.rstrip("/")
		self._api_key = api_key
		self._model = model
		self._timeout_s = max(1.0, float(timeout_s))
		self._transport = transport

		version = (_env_str("ANTHROPIC_VERSION") or "2023-06-01").strip()
		self._anthropic_version = version or "2023-06-01"

		self._client = httpx.Client(
			timeout=self._timeout_s,
			transport=self._transport,
			headers={
				"x-api-key": self._api_key,
				"anthropic-version": self._anthropic_version,
				"Content-Type": "application/json",
				"Accept": "application/json",
			},
		)

	def _endpoint_url(self) -> str:
		lower = self._api_base.lower()
		if lower.endswith("/v1/messages"):
			return self._api_base
		if lower.endswith("/v1"):
			return self._api_base + "/messages"
		return self._api_base + "/v1/messages"

	def generate_json(self, task_name: str, input_dict: dict) -> dict:
		messages = input_dict.get("messages")
		if not isinstance(messages, list) or not messages:
			raise AnalyzeError(code=ErrorCode.JOB_STAGE_FAILED, message="Invalid LLM input", details={"reason": "invalid_input", "task": task_name})

		# Convert OpenAI-style messages into Anthropic Messages API format.
		system_parts: list[str] = []
		anthropic_messages: list[dict[str, Any]] = []
		for m in messages:
			if not isinstance(m, dict):
				continue
			role = str(m.get("role") or "").strip().lower()
			content = m.get("content")
			if not isinstance(content, str):
				content = "" if content is None else str(content)
			if role == "system":
				system_parts.append(content)
				continue
			if role not in {"user", "assistant"}:
				# Best-effort: coerce unknown roles into user text.
				role = "user"
				content = f"[{m.get('role')}]: {content}"
			anthropic_messages.append({"role": role, "content": [{"type": "text", "text": content}]})

		payload: dict[str, Any] = {
			"model": self._model,
			"messages": anthropic_messages or [{"role": "user", "content": [{"type": "text", "text": "{}"}]}],
			"temperature": 0.2,
			"max_tokens": max(64, _env_int("LLM_MAX_TOKENS", 4096)),
		}
		if system_parts:
			payload["system"] = "\n\n".join([p for p in system_parts if p.strip()])

		debug_enabled = _env_bool("LLM_DEBUG", False)
		debug_meta: dict[str, Any] = {}
		if debug_enabled:
			joined = "\n".join(
				f"{m.get('role','')}: {m.get('content','')}" for m in messages if isinstance(m, dict)
			)
			debug_meta = {
				"task": task_name,
				"model": self._model,
				"endpoint": self._endpoint_url(),
				"promptHash": _hash_text(joined),
				"promptLen": len(joined),
				"anthropicVersion": self._anthropic_version,
			}

		max_attempts = max(1, _env_int("LLM_MAX_ATTEMPTS", 3))
		attempt = 0
		resp: httpx.Response | None = None
		while attempt < max_attempts:
			attempt += 1
			try:
				resp = self._client.post(self._endpoint_url(), json=payload)
			except httpx.TimeoutException:
				if attempt < max_attempts:
					time.sleep(min(8.0, 0.5 * (2 ** (attempt - 1))))
					continue
				details = {
					"reason": "timeout",
					"task": task_name,
					"attempt": attempt,
					"maxAttempts": max_attempts,
					"timeoutS": self._timeout_s,
				}
				if debug_enabled:
					details["debug"] = debug_meta
				raise AnalyzeError(code=ErrorCode.JOB_STAGE_FAILED, message="LLM request timed out", details=details)
			except httpx.RequestError as e:
				if attempt < max_attempts:
					time.sleep(min(8.0, 0.5 * (2 ** (attempt - 1))))
					continue
				details = {
					"reason": "upstream_error",
					"task": task_name,
					"errorType": type(e).__name__,
					"attempt": attempt,
					"maxAttempts": max_attempts,
				}
				if debug_enabled:
					details["debug"] = debug_meta
				raise AnalyzeError(code=ErrorCode.JOB_STAGE_FAILED, message="LLM request failed", details=details)

			status = int(resp.status_code)
			if status >= 500 and attempt < max_attempts:
				time.sleep(min(8.0, 0.5 * (2 ** (attempt - 1))))
				continue
			break

		assert resp is not None
		status = int(resp.status_code)
		if status in {401, 403}:
			details = {"reason": "missing_credentials", "task": task_name}
			if debug_enabled:
				details["debug"] = debug_meta
			raise AnalyzeError(code=ErrorCode.JOB_STAGE_FAILED, message="LLM unauthorized", details=details)
		if status == 429:
			details = {"reason": "rate_limited", "task": task_name}
			if debug_enabled:
				details["debug"] = debug_meta
			raise AnalyzeError(code=ErrorCode.JOB_STAGE_FAILED, message="LLM rate limited", details=details)
		if status >= 400:
			details = {"reason": "upstream_error", "task": task_name, "httpStatus": status}
			if debug_enabled:
				details["debug"] = debug_meta
			raise AnalyzeError(code=ErrorCode.JOB_STAGE_FAILED, message="LLM returned error", details=details)

		try:
			body = resp.json()
		except Exception:
			details = {"reason": "invalid_llm_output", "task": task_name, "httpStatus": status, "bodyLen": len(resp.text or "")}
			if debug_enabled:
				details["debug"] = debug_meta
			raise AnalyzeError(code=ErrorCode.JOB_STAGE_FAILED, message="LLM returned non-JSON response", details=details)

		parsed = _parse_anthropic_style_json(body)
		if not isinstance(parsed, dict):
			raise AnalyzeError(
				code=ErrorCode.JOB_STAGE_FAILED,
				message="LLM output is not a JSON object",
				details={"reason": "invalid_llm_output", "task": task_name},
			)
		return parsed


def _parse_anthropic_style_json(body: Any) -> Any:
	"""Extract a JSON object from Anthropic Messages API response."""
	if isinstance(body, dict):
		content = body.get("content")
		if isinstance(content, list) and content:
			parts: list[str] = []
			for b in content:
				if not isinstance(b, dict):
					continue
				if b.get("type") == "text" and isinstance(b.get("text"), str):
					parts.append(b["text"])
			text = "".join(parts).strip()
			return _parse_content_as_json(text)
	# Fall back to raw body (may already be a JSON object)
	return body


def _parse_openai_style_json(body: Any) -> Any:
	"""Extract a JSON object from common OpenAI-compatible response shapes."""

	if isinstance(body, dict) and isinstance(body.get("choices"), list) and body["choices"]:
		choice0 = body["choices"][0]
		if isinstance(choice0, dict):
			msg = choice0.get("message")
			if isinstance(msg, dict):
				content = msg.get("content")
				return _parse_content_as_json(content)
			# Some providers return 'text'
			if "text" in choice0:
				return _parse_content_as_json(choice0.get("text"))

	# Responses API-ish: output[0].content[0].text
	if isinstance(body, dict) and isinstance(body.get("output"), list) and body["output"]:
		out0 = body["output"][0]
		if isinstance(out0, dict):
			content = out0.get("content")
			if isinstance(content, list) and content:
				c0 = content[0]
				if isinstance(c0, dict) and "text" in c0:
					return _parse_content_as_json(c0.get("text"))

	# If provider directly returns the JSON object.
	return body


def _parse_content_as_json(content: Any) -> Any:
	if isinstance(content, dict):
		return content
	if not isinstance(content, str):
		return content

	text = _strip_code_fences(content)
	try:
		return json.loads(text)
	except json.JSONDecodeError:
		sub = _extract_json_object(text)
		if sub:
			try:
				return json.loads(sub)
			except json.JSONDecodeError:
				pass
		# keep safe debug via hash only
		raise AnalyzeError(
			code=ErrorCode.JOB_STAGE_FAILED,
			message="LLM returned invalid JSON",
			details={"reason": "invalid_llm_output", "contentHash": _hash_text(text), "contentLen": len(text)},
		)


def llm_provider_from_env(*, transport: httpx.BaseTransport | None = None) -> AnalyzeProvider:
	api_base = _env_str("LLM_API_BASE")
	api_key = _env_str("LLM_API_KEY")
	model = _normalize_model_id(_env_str("LLM_MODEL") or "minimaxai/minimax-m2.1")
	# Default to a higher timeout to tolerate slow first-byte latency.
	timeout_s = float(_env_int("LLM_TIMEOUT_S", 180))

	if not api_base or not api_key:
		raise AnalyzeError(
			code=ErrorCode.JOB_STAGE_FAILED,
			message="LLM credentials missing",
			details={
				"reason": "missing_credentials",
				"suggest": "Set LLM_API_BASE and LLM_API_KEY",
			},
		)

	api_kind = (_env_str("LLM_API_KIND") or "").strip().lower() or None
	if api_kind == "anthropic" or _is_anthropic_base_url(api_base):
		return AnthropicAnalyzeProvider(api_base=api_base, api_key=api_key, model=model, timeout_s=timeout_s, transport=transport)
	return LLMAnalyzeProvider(api_base=api_base, api_key=api_key, model=model, timeout_s=timeout_s, transport=transport)


def _try_llm_runtime_from_sqlite(*, transport: httpx.BaseTransport | None = None) -> LLMRuntimeConfig | None:
	"""Build an LLM provider from SQLite (active selection + encrypted secret).

	Returns None when there is no active selection.
	Falls back to custom providers table when provider_id is not in the static catalog.
	"""
	from core.db.repositories.llm_settings import get_custom_provider, list_custom_models

	SessionLocal = get_sessionmaker()
	with SessionLocal() as session:
		try:
			active = get_llm_active(session)
		except OperationalError:
			# DB not initialized yet (e.g., unit tests) -> behave as if no active selection.
			return None
		if not isinstance(active, dict):
			return None

		provider_id = (active.get("providerId") or "").strip().lower()
		model_id = (active.get("modelId") or "").strip()

		# Try static catalog first.
		static_provider = find_provider(provider_id)

		if static_provider is not None:
			# Static provider: check if the model exists in catalog OR as a custom model.
			runtime_model = resolve_runtime_model_name(provider_id=static_provider.provider_id, model_id=model_id)
			if runtime_model is None:
				# Check if it's a custom model appended to this provider.
				custom_models = list_custom_models(session, provider_id=provider_id)
				if any(c["modelId"] == model_id for c in custom_models):
					runtime_model = model_id  # Custom model IDs are used as-is.
			if not runtime_model:
				raise AnalyzeError(
					code=ErrorCode.JOB_STAGE_FAILED,
					message="Invalid LLM settings",
					details={"reason": "model_not_found", "providerId": static_provider.provider_id, "modelId": model_id},
				)
			api_base = static_provider.base_url
			resolved_provider_id = static_provider.provider_id
		else:
			# Check custom providers table.
			custom_provider = get_custom_provider(session, provider_id=provider_id)
			if custom_provider is None:
				raise AnalyzeError(
					code=ErrorCode.JOB_STAGE_FAILED,
					message="Invalid LLM settings",
					details={"reason": "unknown_provider", "providerId": provider_id},
				)
			api_base = custom_provider.get("baseUrl", "")
			resolved_provider_id = provider_id
			# For custom providers, runtime model = model_id as-is.
			custom_models = list_custom_models(session, provider_id=provider_id)
			if not any(c["modelId"] == model_id for c in custom_models):
				raise AnalyzeError(
					code=ErrorCode.JOB_STAGE_FAILED,
					message="Invalid LLM settings",
					details={"reason": "model_not_found", "providerId": provider_id, "modelId": model_id},
				)
			runtime_model = model_id

		try:
			ciphertext = get_llm_provider_secret_ciphertext(session, provider_id=resolved_provider_id)
		except OperationalError:
			return None
		if not ciphertext:
			raise AnalyzeError(
				code=ErrorCode.JOB_STAGE_FAILED,
				message="LLM credentials missing",
				details={"reason": "missing_credentials"},
			)

		try:
			api_key = decrypt_api_key(ciphertext)
		except Exception:
			raise AnalyzeError(
				code=ErrorCode.JOB_STAGE_FAILED,
				message="Invalid LLM credentials",
				details={"reason": "invalid_credentials"},
			)

	timeout_s = float(_env_int("LLM_TIMEOUT_S", 180))
	return LLMRuntimeConfig(
		provider_id=resolved_provider_id,
		api_base=api_base,
		api_key=api_key,
		model=runtime_model,
		timeout_s=float(timeout_s),
	)


def llm_runtime_for_jobs(*, transport: httpx.BaseTransport | None = None) -> LLMRuntimeConfig | None:
	"""Resolve LLM runtime config for background jobs."""
	r = _try_llm_runtime_from_sqlite(transport=transport)
	if r is not None:
		return r

	api_base = _env_str("LLM_API_BASE")
	api_key = _env_str("LLM_API_KEY")
	model = _normalize_model_id(_env_str("LLM_MODEL") or "minimaxai/minimax-m2.1")
	timeout_s = float(_env_int("LLM_TIMEOUT_S", 180))
	if not api_base or not api_key:
		return None
	return LLMRuntimeConfig(provider_id=None, api_base=api_base, api_key=api_key, model=model, timeout_s=timeout_s)


def llm_provider_for_jobs(*, transport: httpx.BaseTransport | None = None) -> AnalyzeProvider | None:
	"""Resolve an AnalyzeProvider for background jobs."""
	rt = llm_runtime_for_jobs(transport=transport)
	if rt is None:
		logger.error("LLM not configured")
		return None
	return llm_provider_from_runtime(
		provider_id=rt.provider_id,
		api_base=rt.api_base,
		api_key=rt.api_key,
		model=rt.model,
		timeout_s=int(rt.timeout_s),
		transport=transport,
	)


def llm_provider_from_runtime(
	*,
	provider_id: str | None = None,
	api_base: str | None,
	api_key: str | None,
	model: str | None,
	timeout_s: int,
	transport: httpx.BaseTransport | None = None,
) -> AnalyzeProvider:
	"""Build an LLM provider from already-resolved runtime config.

	This is used by pipeline stages that support dynamic, non-sensitive settings.
	"""

	api_base = (api_base or "").strip() or None
	api_key = (api_key or "").strip() or None
	model = (model or "").strip() or None

	if not api_base:
		raise AnalyzeError(
			code=ErrorCode.JOB_STAGE_FAILED,
			message="Invalid analyze settings",
			details={"reason": "invalid_settings", "missingField": "baseUrl"},
		)

	# Minimal URL validation for operator-friendliness.
	try:
		p = urlparse(api_base)
		scheme = (p.scheme or "").lower()
		if scheme not in {"http", "https"} or not p.netloc:
			raise ValueError("bad url")
	except Exception:
		raise AnalyzeError(
			code=ErrorCode.JOB_STAGE_FAILED,
			message="Invalid analyze settings",
			details={"reason": "invalid_settings", "badField": "baseUrl"},
		)

	if not model:
		raise AnalyzeError(
			code=ErrorCode.JOB_STAGE_FAILED,
			message="Invalid analyze settings",
			details={"reason": "invalid_settings", "missingField": "model"},
		)

	if not api_key:
		raise AnalyzeError(
			code=ErrorCode.JOB_STAGE_FAILED,
			message="LLM credentials missing",
			details={"reason": "missing_credentials", "suggest": "Set LLM_API_KEY"},
		)

	api_kind = (_env_str("LLM_API_KIND") or "").strip().lower() or None
	if (provider_id or "").strip().lower() == "anthropic" or api_kind == "anthropic" or _is_anthropic_base_url(api_base):
		return AnthropicAnalyzeProvider(
			api_base=api_base,
			api_key=api_key,
			model=model,
			timeout_s=float(max(1, int(timeout_s))),
			transport=transport,
		)

	return LLMAnalyzeProvider(
		api_base=api_base,
		api_key=api_key,
		model=_normalize_model_id(model),
		timeout_s=float(max(1, int(timeout_s))),
		transport=transport,
	)
