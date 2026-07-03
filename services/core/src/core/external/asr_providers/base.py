from __future__ import annotations

import time
from dataclasses import dataclass
from http import HTTPStatus
from typing import Any, Callable

import httpx


@dataclass
class AsrCloudTimingsMs:
	upload_ms: float = 0.0
	submit_ms: float = 0.0
	wait_ms: float = 0.0
	download_ms: float = 0.0
	total_ms: float = 0.0


class AsrCloudError(Exception):
	def __init__(
		self,
		kind: str,
		message: str,
		*,
		fallback_eligible: bool = True,
		details: dict | None = None,
	):
		super().__init__(message)
		self.kind = kind
		self.fallback_eligible = fallback_eligible
		self.details = details or {}


def compute_cloud_timeout_s(audio_duration_s: float | None, *, minimum_s: float = 600.0) -> float:
	base = float(audio_duration_s or 60.0)
	return max(minimum_s, base * 2.0)


def poll_until(
	*,
	poll_fn: Callable[[], tuple[str, Any | None]],
	terminal_statuses: set[str],
	pending_statuses: set[str],
	poll_interval_s: float,
	timeout_s: float,
	heartbeat_cb: Callable[[str, float], None] | None = None,
) -> Any:
	deadline = time.perf_counter() + timeout_s
	last_status = "UNKNOWN"
	last_heartbeat = time.perf_counter()
	while True:
		status, payload = poll_fn()
		last_status = status
		if status in terminal_statuses:
			return payload
		if status not in pending_statuses:
			raise AsrCloudError("provider_error", f"unexpected task status: {status}")
		now = time.perf_counter()
		if heartbeat_cb and (now - last_heartbeat) >= 15.0:
			heartbeat_cb(status, now)
			last_heartbeat = now
		if now >= deadline:
			raise AsrCloudError("timeout", "cloud ASR task timed out", details={"lastStatus": last_status})
		time.sleep(max(0.1, poll_interval_s))


def classify_http_error(status_code: int, body: str) -> AsrCloudError:
	if status_code in {401, 403}:
		return AsrCloudError("auth", f"cloud ASR auth failed ({status_code})", fallback_eligible=True)
	if status_code == 429:
		return AsrCloudError("rate_limited", "cloud ASR rate limited", fallback_eligible=True)
	if status_code >= 500:
		return AsrCloudError("provider_unavailable", f"cloud ASR server error ({status_code})", fallback_eligible=True)
	return AsrCloudError("provider_error", f"cloud ASR request failed ({status_code}): {body[:200]}", fallback_eligible=True)


def http_ok(resp: httpx.Response) -> None:
	if resp.status_code == HTTPStatus.OK:
		return
	raise classify_http_error(resp.status_code, resp.text)
