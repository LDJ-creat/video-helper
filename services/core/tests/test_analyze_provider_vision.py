from __future__ import annotations

from core.app.pipeline.analyze_provider import (
	AnalyzeError,
	is_vision_rejection_error,
	openai_content_to_anthropic_blocks,
)
from core.contracts.error_codes import ErrorCode


def test_is_vision_rejection_error_accepts_400_with_hint() -> None:
	exc = AnalyzeError(
		code=ErrorCode.JOB_STAGE_FAILED,
		message="LLM returned error",
		details={"reason": "upstream_error", "httpStatus": 400, "errorBody": "image input not supported"},
	)
	assert is_vision_rejection_error(exc) is True


def test_is_vision_rejection_error_rejects_400_without_vision_hint() -> None:
	exc = AnalyzeError(
		code=ErrorCode.JOB_STAGE_FAILED,
		message="LLM returned error",
		details={"reason": "upstream_error", "httpStatus": 400, "errorBody": "model not found"},
	)
	assert is_vision_rejection_error(exc) is False


def test_is_vision_rejection_error_rejects_non_upstream() -> None:
	exc = AnalyzeError(
		code=ErrorCode.JOB_STAGE_FAILED,
		message="LLM rate limited",
		details={"reason": "rate_limited", "httpStatus": 429},
	)
	assert is_vision_rejection_error(exc) is False


def test_openai_content_to_anthropic_blocks_text() -> None:
	blocks = openai_content_to_anthropic_blocks("hello")
	assert blocks == [{"type": "text", "text": "hello"}]


def test_openai_content_to_anthropic_blocks_image() -> None:
	content = [
		{"type": "text", "text": "check slide"},
		{"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,QUJD"}},
	]
	blocks = openai_content_to_anthropic_blocks(content)
	assert blocks[0]["type"] == "text"
	assert blocks[1]["type"] == "image"
	assert blocks[1]["source"]["type"] == "base64"
	assert blocks[1]["source"]["media_type"] == "image/jpeg"
	assert blocks[1]["source"]["data"] == "QUJD"
