from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Protocol

import httpx

from core.contracts.error_codes import ErrorCode


class AnalyzeProvider(Protocol):
	def generate_json(self, task_name: str, input_dict: dict) -> dict: ...


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

		try:
			resp = self._client.post(self._endpoint_url(), json=payload)
		except httpx.TimeoutException:
			details = {"reason": "timeout", "task": task_name}
			if debug_enabled:
				details["debug"] = debug_meta
			raise AnalyzeError(code=ErrorCode.JOB_STAGE_FAILED, message="LLM request timed out", details=details)
		except httpx.RequestError as e:
			# Network/transport errors.
			details = {"reason": "upstream_error", "task": task_name, "errorType": type(e).__name__}
			if debug_enabled:
				details["debug"] = debug_meta
			raise AnalyzeError(code=ErrorCode.JOB_STAGE_FAILED, message="LLM request failed", details=details)

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


def llm_provider_from_env(*, transport: httpx.BaseTransport | None = None) -> LLMAnalyzeProvider:
	provider = (os.environ.get("ANALYZE_PROVIDER") or "").strip().lower()
	if provider != "llm":
		raise AnalyzeError(code=ErrorCode.JOB_STAGE_FAILED, message="LLM provider not enabled", details={"reason": "disabled"})

	api_base = _env_str("LLM_API_BASE")
	api_key = _env_str("LLM_API_KEY")
	model = _normalize_model_id(_env_str("LLM_MODEL") or "minimaxai/minimax-m2.1")
	timeout_s = float(_env_int("LLM_TIMEOUT_S", 60))

	if not api_base or not api_key:
		raise AnalyzeError(
			code=ErrorCode.JOB_STAGE_FAILED,
			message="LLM credentials missing",
			details={
				"reason": "missing_credentials",
				"suggest": "Set LLM_API_BASE and LLM_API_KEY",
			},
		)

	return LLMAnalyzeProvider(api_base=api_base, api_key=api_key, model=model, timeout_s=timeout_s, transport=transport)
