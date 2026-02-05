from __future__ import annotations

import os

from fastapi import Request
from fastapi.responses import JSONResponse

from core.contracts.error_codes import ErrorCode
from core.contracts.error_envelope import build_error_envelope


def _env_str(name: str) -> str | None:
	raw = os.environ.get(name)
	if raw is None:
		return None
	raw = raw.strip()
	return raw or None


def _env_bool(name: str, default: bool = False) -> bool:
	raw = (os.environ.get(name) or "").strip().lower()
	if raw in {"1", "true", "yes", "y", "on"}:
		return True
	if raw in {"0", "false", "no", "n", "off"}:
		return False
	return default


def _is_loopback_request(request: Request) -> bool:
	client = getattr(request, "client", None)
	host = getattr(client, "host", None)
	return host in {"127.0.0.1", "::1", "localhost"}


def ensure_llm_settings_write_authorized(request: Request) -> JSONResponse | None:
	"""Guard for LLM settings write endpoints.

Policy:
- If `AUTH_ALLOW_LOOPBACK_WRITE=1` AND request is from loopback -> allow.
- Else require `Authorization: Bearer <AUTH_BEARER_TOKEN>`.

If token is not configured and loopback not explicitly enabled -> deny.
"""

	if _env_bool("AUTH_ALLOW_LOOPBACK_WRITE", False) and _is_loopback_request(request):
		return None

	expected = _env_str("AUTH_BEARER_TOKEN")
	auth = _env_str("AUTHORIZATION") or (request.headers.get("authorization") or "").strip()
	if expected and auth == f"Bearer {expected}":
		return None

	return JSONResponse(
		status_code=401,
		content=build_error_envelope(
			code=ErrorCode.UNAUTHORIZED,
			message="Unauthorized",
			request_id=getattr(request.state, "request_id", None),
		),
	)
