from __future__ import annotations

import time
from http import HTTPStatus
from pathlib import Path
from typing import Any, Callable

import httpx

from core.external.asr_dashscope_upload import upload_audio_to_dashscope_temp_oss
from core.external.asr_faster_whisper import AsrResult
from core.external.asr_providers.base import (
	AsrCloudError,
	AsrCloudTimingsMs,
	compute_cloud_timeout_s,
	http_ok,
	poll_until,
)
from core.external.asr_providers.normalize import segments_from_dashscope_transcription

SUBMIT_TASK_URL = "https://dashscope.aliyuncs.com/api/v1/services/audio/asr/transcription"
TASK_QUERY_URL = "https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}"
POLL_INTERVAL_S = 0.5


def transcribe_dashscope_paraformer(
	*,
	audio_path: Path,
	api_key: str,
	model: str,
	language_hints: list[str],
	audio_duration_s: float | None,
	progress_cb: Callable[[str], None] | None = None,
) -> tuple[AsrResult, AsrCloudTimingsMs]:
	if not audio_path.is_file():
		raise AsrCloudError("content_error", "audio file not readable", fallback_eligible=False)

	timeout_s = compute_cloud_timeout_s(audio_duration_s)
	timings = AsrCloudTimingsMs()
	total_start = time.perf_counter()

	with httpx.Client(timeout=timeout_s, trust_env=False) as client:
		t0 = time.perf_counter()
		if progress_cb:
			progress_cb("asr=cloud upload=starting")
		oss_url = upload_audio_to_dashscope_temp_oss(client, api_key=api_key, model=model, file_path=audio_path)
		timings.upload_ms = (time.perf_counter() - t0) * 1000.0

		headers = {
			"Authorization": f"Bearer {api_key}",
			"Content-Type": "application/json",
			"X-DashScope-Async": "enable",
			"X-DashScope-OssResourceResolve": "enable",
		}
		payload = {
			"model": model,
			"input": {"file_urls": [oss_url]},
			"parameters": {
				"channel_id": [0],
				"language_hints": language_hints,
				"timestamp_alignment_enabled": True,
			},
		}
		t0 = time.perf_counter()
		submit_resp = client.post(SUBMIT_TASK_URL, headers=headers, json=payload)
		http_ok(submit_resp)
		task_id = (submit_resp.json().get("output") or {}).get("task_id")
		if not isinstance(task_id, str) or not task_id:
			raise AsrCloudError("provider_error", "missing task_id from DashScope")
		timings.submit_ms = (time.perf_counter() - t0) * 1000.0

		def _poll() -> tuple[str, dict[str, Any] | None]:
			resp = client.post(
				TASK_QUERY_URL.format(task_id=task_id),
				headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
			)
			http_ok(resp)
			body = resp.json()
			output = body.get("output") or {}
			status = str(output.get("task_status") or "UNKNOWN")
			return status, body

		def _heartbeat(status: str, _now: float) -> None:
			if progress_cb:
				progress_cb(f"asr=cloud provider=dashscope status={status}")

		t0 = time.perf_counter()
		task_body = poll_until(
			poll_fn=_poll,
			terminal_statuses={"SUCCEEDED", "FAILED"},
			pending_statuses={"PENDING", "RUNNING"},
			poll_interval_s=POLL_INTERVAL_S,
			timeout_s=timeout_s,
			heartbeat_cb=_heartbeat,
		)
		timings.wait_ms = (time.perf_counter() - t0) * 1000.0

		output = task_body.get("output") or {}
		if output.get("task_status") != "SUCCEEDED":
			results = output.get("results") or []
			detail = results[0] if results else {}
			raise AsrCloudError(
				"provider_error",
				f"DashScope task failed: {detail.get('code')} {detail.get('message')}",
			)

		results = output.get("results") or []
		if not results:
			raise AsrCloudError("provider_error", "DashScope returned empty results")
		first = results[0]
		if first.get("subtask_status") != "SUCCEEDED":
			raise AsrCloudError(
				"provider_error",
				f"DashScope subtask failed: {first.get('code')} {first.get('message')}",
			)
		transcription_url = first.get("transcription_url")
		if not isinstance(transcription_url, str) or not transcription_url:
			raise AsrCloudError("provider_error", "missing transcription_url")

		t0 = time.perf_counter()
		tr_resp = client.get(transcription_url)
		if tr_resp.status_code != HTTPStatus.OK:
			raise classify_transcription_download(tr_resp.status_code, tr_resp.text)
		transcription = tr_resp.json()
		timings.download_ms = (time.perf_counter() - t0) * 1000.0

	segments, language = segments_from_dashscope_transcription(transcription)
	if not segments:
		raise AsrCloudError("empty_transcript", "DashScope produced empty transcript", fallback_eligible=False)

	timings.total_ms = (time.perf_counter() - total_start) * 1000.0
	provider_label = f"dashscope/{model}"
	return AsrResult(provider=provider_label, language=language, segments=segments), timings


def classify_transcription_download(status_code: int, body: str) -> AsrCloudError:
	from core.external.asr_providers.base import classify_http_error

	return classify_http_error(status_code, body)
