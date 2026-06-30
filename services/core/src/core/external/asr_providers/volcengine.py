from __future__ import annotations

import base64
import json
import time
import uuid
from pathlib import Path
from typing import Callable

import httpx

from core.external.asr_faster_whisper import AsrResult
from core.external.asr_providers.base import (
	AsrCloudError,
	AsrCloudTimingsMs,
	compute_cloud_timeout_s,
	poll_until,
)
from core.external.asr_providers.normalize import segments_from_volcengine_result

SUBMIT_URL = "https://openspeech.bytedance.com/api/v3/auc/bigmodel/submit"
QUERY_URL = "https://openspeech.bytedance.com/api/v3/auc/bigmodel/query"
POLL_INTERVAL_S = 0.5

VOLCENGINE_SUCCESS = "20000000"
VOLCENGINE_PENDING = {"20000001", "20000002"}


def _volcengine_language(language_hints: list[str]) -> str | None:
	if not language_hints:
		return "zh-CN"
	first = language_hints[0].strip().lower()
	mapping = {
		"zh": "zh-CN",
		"en": "en-US",
		"ja": "ja-JP",
		"ko": "ko-KR",
		"yue": "yue-CN",
	}
	if first in mapping:
		return mapping[first]
	if "-" in first:
		return first
	return None


def transcribe_volcengine_bigmodel(
	*,
	audio_path: Path,
	api_key: str,
	resource_id: str,
	language_hints: list[str],
	audio_duration_s: float | None,
	progress_cb: Callable[[str], None] | None = None,
) -> tuple[AsrResult, AsrCloudTimingsMs]:
	if not audio_path.is_file():
		raise AsrCloudError("content_error", "audio file not readable", fallback_eligible=False)

	timeout_s = compute_cloud_timeout_s(audio_duration_s)
	timings = AsrCloudTimingsMs()
	total_start = time.perf_counter()
	task_id = str(uuid.uuid4())

	audio_bytes = audio_path.read_bytes()
	audio_b64 = base64.b64encode(audio_bytes).decode("ascii")

	headers = {
		"X-Api-Key": api_key,
		"X-Api-Resource-Id": resource_id,
		"X-Api-Request-Id": task_id,
		"X-Api-Sequence": "-1",
		"Content-Type": "application/json",
	}

	body: dict = {
		"user": {"uid": "video-helper"},
		"audio": {
			"data": audio_b64,
			"format": "wav",
			"rate": 16000,
			"bits": 16,
			"channel": 1,
		},
		"request": {
			"model_name": "bigmodel",
			"enable_itn": True,
			"show_utterances": True,
		},
	}
	lang = _volcengine_language(language_hints)
	if lang:
		body["audio"]["language"] = lang

	if progress_cb:
		progress_cb(f"asr=cloud provider=volcengine resource={resource_id}")

	with httpx.Client(timeout=timeout_s, trust_env=False) as client:
		t0 = time.perf_counter()
		submit_resp = client.post(SUBMIT_URL, headers=headers, content=json.dumps(body))
		submit_code = submit_resp.headers.get("X-Api-Status-Code", "")
		if submit_code and submit_code != VOLCENGINE_SUCCESS:
			msg = submit_resp.headers.get("X-Api-Message", submit_resp.text)
			raise AsrCloudError("provider_error", f"Volcengine submit failed: {submit_code} {msg}")
		if submit_resp.status_code >= 400:
			raise AsrCloudError("provider_error", f"Volcengine submit HTTP {submit_resp.status_code}: {submit_resp.text[:200]}")
		x_tt_logid = submit_resp.headers.get("X-Tt-Logid", "")
		timings.submit_ms = (time.perf_counter() - t0) * 1000.0
		timings.upload_ms = timings.submit_ms

		query_headers = dict(headers)
		if x_tt_logid:
			query_headers["X-Tt-Logid"] = x_tt_logid

		def _poll() -> tuple[str, dict | None]:
			resp = client.post(QUERY_URL, headers=query_headers, content="{}")
			code = resp.headers.get("X-Api-Status-Code", "")
			if code == VOLCENGINE_SUCCESS:
				try:
					return "SUCCEEDED", resp.json()
				except Exception:
					return "SUCCEEDED", {}
			if code in VOLCENGINE_PENDING:
				return "PENDING", None
			if code:
				msg = resp.headers.get("X-Api-Message", resp.text)
				raise AsrCloudError("provider_error", f"Volcengine query failed: {code} {msg}")
			if resp.status_code >= 400:
				raise AsrCloudError("provider_error", f"Volcengine query HTTP {resp.status_code}")
			return "PENDING", None

		def _heartbeat(status: str, _now: float) -> None:
			if progress_cb:
				progress_cb(f"asr=cloud provider=volcengine status={status}")

		t0 = time.perf_counter()
		result_body = poll_until(
			poll_fn=_poll,
			terminal_statuses={"SUCCEEDED"},
			pending_statuses={"PENDING"},
			poll_interval_s=POLL_INTERVAL_S,
			timeout_s=timeout_s,
			heartbeat_cb=_heartbeat,
		)
		timings.wait_ms = (time.perf_counter() - t0) * 1000.0

	segments, language = segments_from_volcengine_result(result_body or {})
	if not segments:
		raise AsrCloudError("empty_transcript", "Volcengine produced empty transcript", fallback_eligible=False)

	timings.total_ms = (time.perf_counter() - total_start) * 1000.0
	provider_label = f"volcengine/{resource_id}"
	return AsrResult(provider=provider_label, language=language, segments=segments), timings
