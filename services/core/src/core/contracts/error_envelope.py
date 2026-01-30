from __future__ import annotations

from typing import Any

from .error_codes import ErrorCode


def build_error_envelope(
    *,
    code: ErrorCode | str,
    message: str,
    details: dict[str, Any] | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    """Build the frozen error envelope shape.

    Contract (all non-2xx):
    { "error": { "code": string, "message": string, "details"?: any, "requestId"?: string } }

    Note: uses camelCase requestId (NOT request_id).
    """

    error: dict[str, Any] = {
        "code": code.value if isinstance(code, ErrorCode) else str(code),
        "message": message,
    }
    if details is not None:
        error["details"] = details
    if request_id is not None:
        error["requestId"] = request_id

    return {"error": error}
