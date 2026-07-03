from __future__ import annotations

import pytest

from core.llm.http_headers import http_header_value_error


def test_http_header_value_error_ascii_ok() -> None:
	assert http_header_value_error("sk-test123") is None


def test_http_header_value_error_non_ascii() -> None:
	assert http_header_value_error("sk-小米") == "invalid_api_key"


def test_http_header_value_error_latin1_ok() -> None:
	# Latin-1 supplement is valid in HTTP header values.
	assert http_header_value_error("sk-\xe9") is None
