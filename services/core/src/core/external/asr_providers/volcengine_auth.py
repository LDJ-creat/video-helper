from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class VolcengineCredentials:
	mode: Literal["api_key", "legacy"]
	api_key: str | None = None
	app_key: str | None = None
	access_key: str | None = None


def parse_volcengine_credentials(raw: str) -> VolcengineCredentials:
	"""Parse stored secret for OpenSpeech v3.

	New console: single X-Api-Key string.
	Legacy console: ``app_id|access_token`` (pipe-separated).
	"""

	text = (raw or "").strip()
	if not text:
		raise ValueError("empty credentials")
	if "|" in text:
		app_key, access_key = text.split("|", 1)
		app_key = app_key.strip()
		access_key = access_key.strip()
		if not app_key or not access_key:
			raise ValueError("legacy credentials must be app_id|access_token")
		return VolcengineCredentials(mode="legacy", app_key=app_key, access_key=access_key)
	return VolcengineCredentials(mode="api_key", api_key=text)


def build_volcengine_headers(
	creds: VolcengineCredentials,
	*,
	resource_id: str,
	request_id: str,
	x_tt_logid: str | None = None,
	sequence: str = "-1",
) -> dict[str, str]:
	headers: dict[str, str] = {
		"Content-Type": "application/json",
		"X-Api-Resource-Id": resource_id,
		"X-Api-Request-Id": request_id,
		"X-Api-Sequence": sequence,
	}
	if creds.mode == "legacy":
		headers["X-Api-App-Key"] = str(creds.app_key)
		headers["X-Api-Access-Key"] = str(creds.access_key)
	else:
		headers["X-Api-Key"] = str(creds.api_key)
	if x_tt_logid:
		headers["X-Tt-Logid"] = x_tt_logid
	return headers
