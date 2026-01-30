from __future__ import annotations

from enum import Enum


class ErrorCode(str, Enum):
    """Frozen error code registry shared across BE/FE.

    Error codes MUST be stable once published.
    """

    # Input validation
    VALIDATION_ERROR = "VALIDATION_ERROR"
    UNSUPPORTED_SOURCE_TYPE = "UNSUPPORTED_SOURCE_TYPE"
    INVALID_SOURCE_URL = "INVALID_SOURCE_URL"

    # Not found
    PROJECT_NOT_FOUND = "PROJECT_NOT_FOUND"
    JOB_NOT_FOUND = "JOB_NOT_FOUND"
    ASSET_NOT_FOUND = "ASSET_NOT_FOUND"
    RESULT_NOT_FOUND = "RESULT_NOT_FOUND"

    # Missing dependencies
    FFMPEG_MISSING = "FFMPEG_MISSING"
    YTDLP_MISSING = "YTDLP_MISSING"

    # Job lifecycle
    JOB_STAGE_FAILED = "JOB_STAGE_FAILED"
    JOB_CANCELED = "JOB_CANCELED"
    JOB_NOT_CANCELLABLE = "JOB_NOT_CANCELLABLE"

    # Resources
    RESOURCE_EXHAUSTED = "RESOURCE_EXHAUSTED"

    # Auth
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"

    # Security
    PATH_TRAVERSAL_BLOCKED = "PATH_TRAVERSAL_BLOCKED"


ERROR_CODES: tuple[ErrorCode, ...] = tuple(ErrorCode)
