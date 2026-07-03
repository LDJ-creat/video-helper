from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
import time
import logging
from urllib.parse import urlparse
from typing import Any, Iterable, Protocol

import httpx
from sqlalchemy.exc import OperationalError

from core.contracts.error_codes import ErrorCode
from core.db.repositories.llm_settings import get_llm_active, get_llm_provider_secret_ciphertext
from core.db.session import get_data_dir
from core.db.session import get_sessionmaker
from core.llm.catalog import find_provider, resolve_runtime_model_name
from core.llm.secrets_crypto import decrypt_api_key

logger = logging.getLogger(__name__)

class AnalyzeProvider(Protocol):
	def generate_json(self, task_name: str, input_dict: dict, *, max_tokens: int | None = None) -> dict: ...


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


def _truncate_text(text: str, *, max_chars: int) -> str:
	if max_chars <= 0:
		return ""
	if len(text) <= max_chars:
		return text
	return text[:max_chars]


def _maybe_dump_text_under_data_dir(*, rel_dir: str, filename: str, text: str, force: bool = False) -> str | None:
	"""Best-effort dump debug text under DATA_DIR.

	Returns relative path (posix) when written.
	Controlled by env LLM_DUMP_INVALID_JSON.
	"""
	if (not force) and (not _env_bool("LLM_DUMP_INVALID_JSON", False)):
		return None
	try:
		data_dir = get_data_dir().resolve()
		base = (data_dir / rel_dir).resolve()
		if not base.is_relative_to(data_dir):
			return None
		base.mkdir(parents=True, exist_ok=True)
		path = (base / filename).resolve()
		if not path.is_relative_to(data_dir):
			return None

		# Avoid gigantic DB payloads / accidental huge dumps.
		content = _truncate_text(text, max_chars=_env_int("LLM_DUMP_MAX_CHARS", 200_000))
		path.write_text(content, encoding="utf-8", errors="ignore")
		return path.relative_to(data_dir).as_posix()
	except Exception:
		return None


def _normalize_model_id(model: str) -> str:
	"""Normalize common shorthand model names to NVIDIA NIM OpenAI-compatible ids."""

	m = (model or "").strip()
	lower = m.lower().replace("_", "-")
	if lower in {"minimax-2.1", "minimax2.1", "minimax 2.1", "minimax-m2.1", "minimax-m2_1"}:
		return "minimaxai/minimax-m2.1"
	return m


def _messages_char_len(messages: list[Any]) -> int:
	return len(
		"\n".join(f"{m.get('role','')}: {m.get('content','')}" for m in messages if isinstance(m, dict))
	)


_VISION_REJECTION_HINTS = (
	"image",
	"vision",
	"multimodal",
	"content type",
	"content_type",
	"unsupported image",
	"unsupported media",
	"does not support",
	"not support",
	"invalid content",
	"image_url",
)


def is_vision_rejection_error(exc: BaseException) -> bool:
	"""True when an upstream LLM call likely rejected image/multimodal input.

	Used by keyframe_verify to fall back to OCR without pre-detecting model capabilities.
	"""

	if not isinstance(exc, AnalyzeError):
		return False
	details = exc.details or {}
	if str(details.get("reason") or "") != "upstream_error":
		return False
	status = details.get("httpStatus")
	if status not in {400, 422}:
		return False
	msg = " ".join(
		str(x)
		for x in (
			exc.message,
			details.get("errorBody"),
			details.get("upstreamMessage"),
		)
		if x
	).lower()
	return any(h in msg for h in _VISION_REJECTION_HINTS)


def _truncate_upstream_error_body(text: str) -> str:
	return _truncate_text(text, max_chars=_env_int("LLM_UPSTREAM_ERROR_BODY_MAX_CHARS", 2000))


def _read_http_error_body(raw: bytes | str | None) -> str:
	if raw is None:
		return ""
	try:
		if isinstance(raw, bytes):
			text = raw.decode("utf-8", errors="replace")
		else:
			text = str(raw)
		return _truncate_upstream_error_body(text)
	except Exception:
		return ""


def _upstream_http_error_details(*, task_name: str, status: int, error_body: str) -> dict[str, Any]:
	details: dict[str, Any] = {
		"reason": "upstream_error",
		"task": task_name,
		"httpStatus": int(status),
	}
	if error_body:
		details["errorBody"] = error_body
	return details


def _parse_data_image_url(url: str) -> tuple[str, str] | None:
	"""Return (media_type, base64_data) for data:image/...;base64,... URLs."""

	raw = (url or "").strip()
	if not raw.lower().startswith("data:"):
		return None
	comma = raw.find(",")
	if comma <= 0:
		return None
	header = raw[5:comma].strip()
	payload = raw[comma + 1 :].strip()
	if not payload or ";base64" not in header.lower():
		return None
	media_type = header.split(";", 1)[0].strip().lower()
	if not media_type.startswith("image/"):
		return None
	return media_type, payload


def openai_content_has_image_url(content: Any) -> bool:
	if not isinstance(content, list):
		return False
	for part in content:
		if isinstance(part, dict) and str(part.get("type") or "").strip().lower() == "image_url":
			return True
	return False


def anthropic_blocks_has_image(blocks: list[dict[str, Any]]) -> bool:
	return any(isinstance(b, dict) and b.get("type") == "image" for b in blocks)


def openai_content_to_anthropic_blocks(content: Any) -> list[dict[str, Any]]:
	"""Convert OpenAI-style message content to Anthropic Messages API blocks."""

	if isinstance(content, str):
		return [{"type": "text", "text": content}]
	if not isinstance(content, list):
		return [{"type": "text", "text": "" if content is None else str(content)}]

	had_image_url = openai_content_has_image_url(content)
	blocks: list[dict[str, Any]] = []
	for part in content:
		if not isinstance(part, dict):
			continue
		part_type = str(part.get("type") or "").strip().lower()
		if part_type == "text":
			text = part.get("text")
			if isinstance(text, str) and text:
				blocks.append({"type": "text", "text": text})
			continue
		if part_type == "image_url":
			image_url = part.get("image_url")
			url = image_url.get("url") if isinstance(image_url, dict) else None
			if not isinstance(url, str):
				continue
			parsed = _parse_data_image_url(url)
			if parsed is None:
				continue
			media_type, data = parsed
			blocks.append(
				{
					"type": "image",
					"source": {"type": "base64", "media_type": media_type, "data": data},
				}
			)
	if had_image_url and not anthropic_blocks_has_image(blocks):
		logger.warning("[LLM] dropped image_url during Anthropic content conversion (unsupported or invalid data URL)")
	if not blocks:
		return [{"type": "text", "text": ""}]
	return blocks


def _record_llm_usage_after_call(
	*,
	task_name: str,
	model: str,
	attempt: int,
	duration_ms: int,
	usage: Any,
	provider_kind: str,
	prompt_chars: int,
	completion_chars: int,
) -> None:
	if task_name == "benchmark_faithfulness_judge":
		return
	from core.app.pipeline.llm_usage import append_llm_usage_record, normalize_anthropic_usage, normalize_openai_usage, resolve_usage_for_record

	normalized = None
	if provider_kind == "anthropic" and isinstance(usage, dict):
		normalized = normalize_anthropic_usage(
			input_tokens=usage.get("input_tokens"),
			output_tokens=usage.get("output_tokens"),
		)
	elif isinstance(usage, dict):
		normalized = normalize_openai_usage(usage)

	resolved = resolve_usage_for_record(
		usage=normalized,
		provider_kind=provider_kind,
		prompt_chars=prompt_chars,
		completion_chars=completion_chars,
	)
	append_llm_usage_record(
		task=task_name,
		model=model,
		usage=resolved,
		attempt=attempt,
		duration_ms=duration_ms,
	)


def _parse_openai_sse_chunks(line_iter: Iterable[str]) -> tuple[str, int, dict[str, Any] | None]:
	"""Parse OpenAI-compatible SSE stream, concatenate delta.content.

	Returns (full_text, chunk_count, usage_dict).
	"""
	parts: list[str] = []
	chunk_count = 0
	usage: dict[str, Any] | None = None
	for line in line_iter:
		line = line.strip()
		if not line or line.startswith(":"):
			continue
		if line == "data: [DONE]":
			break
		if line.startswith("data: "):
			payload_str = line[6:]
			try:
				obj = json.loads(payload_str)
				if isinstance(obj.get("usage"), dict):
					usage = obj["usage"]
				choices = obj.get("choices")
				if isinstance(choices, list) and choices:
					delta = choices[0].get("delta", {})
					content = delta.get("content")
					if isinstance(content, str):
						parts.append(content)
						chunk_count += 1
			except json.JSONDecodeError:
				pass
	return "".join(parts), chunk_count, usage


def _parse_anthropic_sse_chunks(line_iter: Iterable[str]) -> tuple[str, int, dict[str, int] | None]:
	"""Parse Anthropic SSE stream, concatenate content_block_delta delta.text.

	Returns (full_text, chunk_count, usage_dict with input_tokens/output_tokens).
	"""
	parts: list[str] = []
	chunk_count = 0
	current_event = ""
	input_tokens: int | None = None
	output_tokens: int | None = None
	for line in line_iter:
		line = line.strip()
		if not line:
			continue
		if line.startswith(":"):
			continue
		if line.startswith("event: "):
			current_event = line[7:].strip()
			if current_event == "message_stop":
				break
			continue
		if line.startswith("data: "):
			payload_str = line[6:]
			try:
				obj = json.loads(payload_str)
			except json.JSONDecodeError:
				continue
			if current_event == "message_start":
				message = obj.get("message") if isinstance(obj.get("message"), dict) else {}
				msg_usage = message.get("usage") if isinstance(message.get("usage"), dict) else {}
				in_tok = msg_usage.get("input_tokens")
				if isinstance(in_tok, int):
					input_tokens = in_tok
			elif current_event == "message_delta":
				msg_usage = obj.get("usage") if isinstance(obj.get("usage"), dict) else {}
				out_tok = msg_usage.get("output_tokens")
				if isinstance(out_tok, int):
					output_tokens = out_tok
			elif current_event == "content_block_delta":
				delta = obj.get("delta", {})
				text = delta.get("text")
				if isinstance(text, str):
					parts.append(text)
					chunk_count += 1
	usage: dict[str, int] | None = None
	if input_tokens is not None or output_tokens is not None:
		usage = {}
		if input_tokens is not None:
			usage["input_tokens"] = input_tokens
		if output_tokens is not None:
			usage["output_tokens"] = output_tokens
	return "".join(parts), chunk_count, usage


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
			timeout=httpx.Timeout(connect=30.0, read=120.0, write=30.0, pool=10.0),
			transport=self._transport,
			trust_env=False,
			headers={
				"Authorization": f"Bearer {self._api_key}",
				"Content-Type": "application/json",
				"Accept": "text/event-stream",
			},
		)

	def _endpoint_url(self) -> str:
		from core.llm.openai_compat_url import resolve_openai_compat_chat_endpoint

		return resolve_openai_compat_chat_endpoint(self._api_base)

	def generate_json(self, task_name: str, input_dict: dict, *, max_tokens: int | None = None) -> dict:
		t_start = time.perf_counter()
		messages = input_dict.get("messages")
		if not isinstance(messages, list) or not messages:
			raise AnalyzeError(code=ErrorCode.JOB_STAGE_FAILED, message="Invalid LLM input", details={"reason": "invalid_input", "task": task_name})

		effective_max_tokens = max_tokens or _env_int("LLM_MAX_TOKENS", 4096)
		payload: dict[str, Any] = {
			"model": self._model,
			"messages": messages,
			"temperature": 0.2,
			"response_format": {"type": "json_object"},
			"stream": True,
			"max_tokens": effective_max_tokens,
		}
		if _env_bool("LLM_STREAM_INCLUDE_USAGE", True):
			payload["stream_options"] = {"include_usage": True}

		prompt_chars = _messages_char_len(messages)

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

		if debug_enabled:
			logger.info(
				"[LLM] request queued task=%s model=%s endpoint=%s promptHash=%s promptLen=%s maxTokens=%s",
				task_name,
				self._model,
				self._endpoint_url(),
				debug_meta.get("promptHash"),
				debug_meta.get("promptLen"),
				payload["max_tokens"],
			)

		# Default retries: reduces flakiness on providers with slow first-byte latency.
		max_attempts = max(1, _env_int("LLM_MAX_ATTEMPTS", 3))
		attempt = 0
		full_text: str | None = None
		status: int | None = None
		error_body = ""
		chunk_count = 0
		stream_elapsed_s = 0.0
		raw_usage: dict[str, Any] | None = None
		while attempt < max_attempts:
			attempt += 1
			try:
				if debug_enabled:
					logger.info("[LLM] request start task=%s attempt=%s/%s (streaming)", task_name, attempt, max_attempts)
				t_stream_start = time.perf_counter()
				with self._client.stream("POST", self._endpoint_url(), json=payload) as stream:
					status = int(stream.status_code)
					# For error status codes, read body from stream for error details.
					if status >= 400:
						error_body = _read_http_error_body(stream.read())
						break
					full_text, chunk_count, raw_usage = _parse_openai_sse_chunks(stream.iter_lines())
				stream_elapsed_s = time.perf_counter() - t_stream_start
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
			if status is not None and status >= 500 and attempt < max_attempts:
				time.sleep(min(8.0, 0.5 * (2 ** (attempt - 1))))
				continue
			break

		assert status is not None
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
			details = _upstream_http_error_details(task_name=task_name, status=status, error_body=error_body)
			if debug_enabled:
				details["debug"] = debug_meta
			raise AnalyzeError(code=ErrorCode.JOB_STAGE_FAILED, message="LLM returned error", details=details)

		# Parse assembled text as JSON.
		if full_text is None:
			raise AnalyzeError(
				code=ErrorCode.JOB_STAGE_FAILED,
				message="LLM returned empty stream",
				details={"reason": "invalid_llm_output", "task": task_name},
			)

		t_parse_start = time.perf_counter()
		parsed = _parse_content_as_json(full_text, task_name)
		parse_elapsed_s = time.perf_counter() - t_parse_start
		if not isinstance(parsed, dict):
			raise AnalyzeError(
				code=ErrorCode.JOB_STAGE_FAILED,
				message="LLM output is not a JSON object",
				details={"reason": "invalid_llm_output", "task": task_name},
			)

		total_elapsed_s = time.perf_counter() - t_start
		from core.app.pipeline.llm_usage import normalize_openai_usage

		normalized_usage = normalize_openai_usage(raw_usage) if raw_usage else None
		_record_llm_usage_after_call(
			task_name=task_name,
			model=self._model,
			attempt=attempt,
			duration_ms=int(total_elapsed_s * 1000),
			usage=raw_usage,
			provider_kind="openai_compat",
			prompt_chars=prompt_chars,
			completion_chars=len(full_text),
		)
		usage_source = normalized_usage.source if normalized_usage else "unavailable"
		usage_total = normalized_usage.total_tokens if normalized_usage else None
		usage_prompt = normalized_usage.prompt_tokens if normalized_usage else None
		usage_completion = normalized_usage.completion_tokens if normalized_usage else None
		if usage_total is None and _env_bool("LLM_USAGE_ESTIMATE_FALLBACK", True):
			usage_source = "estimated"
			usage_prompt = max(0, prompt_chars // 4)
			usage_completion = max(0, len(full_text) // 4)
			usage_total = usage_prompt + usage_completion
		# Always log timing info for performance tracking (not gated by LLM_DEBUG).
		logger.info(
			"[LLM] ok task=%s model=%s maxTokens=%s streamDur=%.1fs chunks=%d contentLen=%d parseDur=%.2fs totalDur=%.1fs attempt=%s/%s promptTokens=%s completionTokens=%s totalTokens=%s usageSource=%s",
			task_name,
			self._model,
			effective_max_tokens,
			stream_elapsed_s,
			chunk_count,
			len(full_text),
			parse_elapsed_s,
			total_elapsed_s,
			attempt,
			max_attempts,
			usage_prompt,
			usage_completion,
			usage_total,
			usage_source,
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
			timeout=httpx.Timeout(connect=30.0, read=120.0, write=30.0, pool=10.0),
			transport=self._transport,
			trust_env=False,
			headers={
				"x-api-key": self._api_key,
				"anthropic-version": self._anthropic_version,
				"Content-Type": "application/json",
				"Accept": "text/event-stream",
			},
		)

	def _endpoint_url(self) -> str:
		lower = self._api_base.lower()
		if lower.endswith("/v1/messages"):
			return self._api_base
		if lower.endswith("/v1"):
			return self._api_base + "/messages"
		return self._api_base + "/v1/messages"

	def generate_json(self, task_name: str, input_dict: dict, *, max_tokens: int | None = None) -> dict:
		t_start = time.perf_counter()
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
			if role == "system":
				if isinstance(content, str):
					system_parts.append(content)
				elif isinstance(content, list):
					for block in openai_content_to_anthropic_blocks(content):
						if block.get("type") == "text" and isinstance(block.get("text"), str):
							system_parts.append(block["text"])
				continue
			if role not in {"user", "assistant"}:
				role = "user"
				if isinstance(content, str):
					content = f"[{m.get('role')}]: {content}"
				else:
					content = f"[{m.get('role')}]: {content!s}"
			blocks = (
				openai_content_to_anthropic_blocks(content)
				if not isinstance(content, str)
				else [{"type": "text", "text": content}]
			)
			anthropic_messages.append({"role": role, "content": blocks})

		effective_max_tokens = max(64, max_tokens or _env_int("LLM_MAX_TOKENS", 4096))

		payload: dict[str, Any] = {
			"model": self._model,
			"messages": anthropic_messages or [{"role": "user", "content": [{"type": "text", "text": "{}"}]}],
			"temperature": 0.2,
			"max_tokens": effective_max_tokens,
			"stream": True,
		}
		if system_parts:
			payload["system"] = "\n\n".join([p for p in system_parts if p.strip()])

		prompt_chars = _messages_char_len(messages)

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

		if debug_enabled:
			logger.info(
				"[LLM] request queued task=%s model=%s endpoint=%s promptHash=%s promptLen=%s maxTokens=%s",
				task_name,
				self._model,
				self._endpoint_url(),
				debug_meta.get("promptHash"),
				debug_meta.get("promptLen"),
				effective_max_tokens,
			)

		max_attempts = max(1, _env_int("LLM_MAX_ATTEMPTS", 3))
		attempt = 0
		full_text: str | None = None
		status: int | None = None
		error_body = ""
		chunk_count = 0
		stream_elapsed_s = 0.0
		raw_usage: dict[str, int] | None = None
		while attempt < max_attempts:
			attempt += 1
			try:
				if debug_enabled:
					logger.info("[LLM] request start task=%s attempt=%s/%s (streaming)", task_name, attempt, max_attempts)
				t_stream_start = time.perf_counter()
				with self._client.stream("POST", self._endpoint_url(), json=payload) as stream:
					status = int(stream.status_code)
					if status >= 400:
						error_body = _read_http_error_body(stream.read())
						break
					full_text, chunk_count, raw_usage = _parse_anthropic_sse_chunks(stream.iter_lines())
				stream_elapsed_s = time.perf_counter() - t_stream_start
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

			if status is not None and status >= 500 and attempt < max_attempts:
				time.sleep(min(8.0, 0.5 * (2 ** (attempt - 1))))
				continue
			break

		assert status is not None
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
			details = _upstream_http_error_details(task_name=task_name, status=status, error_body=error_body)
			if debug_enabled:
				details["debug"] = debug_meta
			raise AnalyzeError(code=ErrorCode.JOB_STAGE_FAILED, message="LLM returned error", details=details)

		# Parse assembled text as JSON.
		if full_text is None:
			raise AnalyzeError(
				code=ErrorCode.JOB_STAGE_FAILED,
				message="LLM returned empty stream",
				details={"reason": "invalid_llm_output", "task": task_name},
			)

		t_parse_start = time.perf_counter()
		parsed = _parse_content_as_json(full_text, task_name)
		parse_elapsed_s = time.perf_counter() - t_parse_start
		if not isinstance(parsed, dict):
			raise AnalyzeError(
				code=ErrorCode.JOB_STAGE_FAILED,
				message="LLM output is not a JSON object",
				details={"reason": "invalid_llm_output", "task": task_name},
			)

		total_elapsed_s = time.perf_counter() - t_start
		from core.app.pipeline.llm_usage import normalize_anthropic_usage

		normalized_usage = None
		if raw_usage:
			normalized_usage = normalize_anthropic_usage(
				input_tokens=raw_usage.get("input_tokens"),
				output_tokens=raw_usage.get("output_tokens"),
			)
		_record_llm_usage_after_call(
			task_name=task_name,
			model=self._model,
			attempt=attempt,
			duration_ms=int(total_elapsed_s * 1000),
			usage=raw_usage,
			provider_kind="anthropic",
			prompt_chars=prompt_chars,
			completion_chars=len(full_text),
		)
		usage_source = normalized_usage.source if normalized_usage else "unavailable"
		usage_total = normalized_usage.total_tokens if normalized_usage else None
		usage_prompt = normalized_usage.prompt_tokens if normalized_usage else None
		usage_completion = normalized_usage.completion_tokens if normalized_usage else None
		if usage_total is None and _env_bool("LLM_USAGE_ESTIMATE_FALLBACK", True):
			usage_source = "estimated"
			usage_prompt = max(0, prompt_chars // 4)
			usage_completion = max(0, len(full_text) // 4)
			usage_total = usage_prompt + usage_completion
		logger.info(
			"[LLM] ok task=%s model=%s maxTokens=%s streamDur=%.1fs chunks=%d contentLen=%d parseDur=%.2fs totalDur=%.1fs attempt=%s/%s promptTokens=%s completionTokens=%s totalTokens=%s usageSource=%s provider=anthropic",
			task_name,
			self._model,
			effective_max_tokens,
			stream_elapsed_s,
			chunk_count,
			len(full_text),
			parse_elapsed_s,
			total_elapsed_s,
			attempt,
			max_attempts,
			usage_prompt,
			usage_completion,
			usage_total,
			usage_source,
		)
		return parsed


def _parse_anthropic_style_json(body: Any, task_name: str | None) -> Any:
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
			return _parse_content_as_json(text, task_name=task_name)
	# Fall back to raw body (may already be a JSON object)
	return body


def _parse_openai_style_json(body: Any, task_name: str | None) -> Any:
	"""Extract a JSON object from common OpenAI-compatible response shapes."""

	if isinstance(body, dict) and isinstance(body.get("choices"), list) and body["choices"]:
		choice0 = body["choices"][0]
		if isinstance(choice0, dict):
			msg = choice0.get("message")
			if isinstance(msg, dict):
				content = msg.get("content")
				return _parse_content_as_json(content, task_name=task_name)
			# Some providers return 'text'
			if "text" in choice0:
				return _parse_content_as_json(choice0.get("text"), task_name=task_name)

	# Responses API-ish: output[0].content[0].text
	if isinstance(body, dict) and isinstance(body.get("output"), list) and body["output"]:
		out0 = body["output"][0]
		if isinstance(out0, dict):
			content = out0.get("content")
			if isinstance(content, list) and content:
				c0 = content[0]
				if isinstance(c0, dict) and "text" in c0:
						return _parse_content_as_json(c0.get("text"), task_name=task_name)

	# If provider directly returns the JSON object.
	return body


def _parse_content_as_json(content: Any, task_name: str | None) -> Any:
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
		content_hash = _hash_text(text)
		dump_ref = _maybe_dump_text_under_data_dir(
			rel_dir="logs/llm_invalid_json",
			filename=f"{(task_name or 'unknown')}-invalid-json-{content_hash}.txt",
			text=text,
			force=True,
		)
		# keep safe debug via hash only by default; allow opt-in dumps via env.
		raise AnalyzeError(
			code=ErrorCode.JOB_STAGE_FAILED,
			message="LLM returned invalid JSON",
			details={
				"reason": "invalid_llm_output",
				"task": task_name,
				"contentHash": content_hash,
				"contentLen": len(text),
				"dumpRef": dump_ref,
				"hint": "Set LLM_DUMP_INVALID_JSON=1 to dump raw model output under DATA_DIR/logs/llm_invalid_json",
			},
		)


def llm_provider_from_env(*, transport: httpx.BaseTransport | None = None) -> AnalyzeProvider:
	api_base = _env_str("LLM_API_BASE")
	api_key = _env_str("LLM_API_KEY")
	model = _normalize_model_id(_env_str("LLM_MODEL") or "minimaxai/minimax-m2.1")
	# Default to a higher timeout to tolerate slow first-byte latency.
	timeout_s = float(_env_int("LLM_TIMEOUT_S", 360))

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
	from core.db.repositories.llm_settings import get_custom_provider
	from core.llm.provider_profile import get_resolved_builtin_base_url

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
			runtime_model = resolve_runtime_model_name(provider_id=static_provider.provider_id, model_id=model_id)
			if not runtime_model:
				raise AnalyzeError(
					code=ErrorCode.JOB_STAGE_FAILED,
					message="Invalid LLM settings",
					details={"reason": "model_not_found", "providerId": static_provider.provider_id, "modelId": model_id},
				)
			api_base = get_resolved_builtin_base_url(session, provider_id=static_provider.provider_id) or static_provider.base_url
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
			mid = (model_id or "").strip()
			if not mid:
				raise AnalyzeError(
					code=ErrorCode.JOB_STAGE_FAILED,
					message="Invalid LLM settings",
					details={"reason": "model_not_found", "providerId": provider_id, "modelId": model_id},
				)
			if ":" in mid:
				_, rest = mid.split(":", 1)
				runtime_model = rest.strip() or mid
			else:
				runtime_model = mid

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

	timeout_s = float(_env_int("LLM_TIMEOUT_S", 360))
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
	timeout_s = float(_env_int("LLM_TIMEOUT_S", 360))
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
