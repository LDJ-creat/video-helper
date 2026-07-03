from __future__ import annotations

import re

_CHAT_ENDPOINT_SUFFIXES = (
	"/chat/completions",
	"/v1/chat/completions",
	"/responses",
	"/v1/responses",
)

# Matches version roots like /v1, /v3, /v1beta (e.g. .../api/v3, .../paas/v4).
_VERSION_SEGMENT_RE = re.compile(r"/v\d+(?:beta)?$", re.IGNORECASE)


def normalize_openai_compat_base_url(base_url: str) -> str:
	return (base_url or "").strip().rstrip("/")


def is_complete_openai_compat_chat_endpoint(base_url: str) -> bool:
	lower = normalize_openai_compat_base_url(base_url).lower()
	return any(lower.endswith(suffix) for suffix in _CHAT_ENDPOINT_SUFFIXES)


def resolve_openai_compat_chat_endpoint(base_url: str) -> str:
	"""Resolve POST URL for OpenAI-compatible chat from a user-configured base URL.

	If the URL already ends with a known chat endpoint path (``/chat/completions``,
	``/responses``, etc.), it is returned unchanged. Version roots like ``/v1`` or
	``/api/v3`` receive ``/chat/completions`` (not ``/v1/chat/completions``).
	Bare host roots receive ``/v1/chat/completions``.
	"""

	url = normalize_openai_compat_base_url(base_url)
	if not url:
		return url
	lower = url.lower()
	if lower.endswith("/v1"):
		return f"{url}/chat/completions"
	if is_complete_openai_compat_chat_endpoint(url):
		return url
	if _VERSION_SEGMENT_RE.search(url):
		return f"{url}/chat/completions"
	return f"{url}/v1/chat/completions"


def openai_compat_models_list_url(base_url: str) -> str:
	"""Derive ``GET .../models`` URL from a chat endpoint or version root ``base_url``."""

	u = normalize_openai_compat_base_url(base_url)
	if not u:
		return ""
	lower = u.lower()
	if lower.endswith("/v1/chat/completions"):
		u = u[: -len("/chat/completions")].rstrip("/")
		lower = u.lower()
	elif lower.endswith("/chat/completions"):
		u = u[: -len("/chat/completions")].rstrip("/")
		lower = u.lower()
	if lower.endswith("/responses"):
		u = u[: -len("/responses")].rstrip("/")
		lower = u.lower()
	if lower.endswith("/models"):
		return u
	return f"{u}/models"
