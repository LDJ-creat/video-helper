from __future__ import annotations


def http_header_value_error(value: str) -> str | None:
	"""Return a stable error code when *value* cannot be used in HTTP headers.

	httpx encodes header values as latin-1; non-ASCII characters (e.g. pasted
	Chinese text mistaken for an API key) raise UnicodeEncodeError and would
	otherwise surface as 500 Internal Server Error.
	"""

	try:
		value.encode("latin-1")
	except UnicodeEncodeError:
		return "invalid_api_key"
	return None
