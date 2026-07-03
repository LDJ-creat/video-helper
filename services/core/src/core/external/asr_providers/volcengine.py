from __future__ import annotations

import base64
import json
import time
import uuid
from pathlib import Path
from typing import Callable, Literal

import httpx

from core.external.asr_faster_whisper import AsrResult
from core.external.asr_providers.base import (
	AsrCloudError,
	AsrCloudTimingsMs,
	compute_cloud_timeout_s,
	poll_until,
)
from core.external.asr_providers.normalize import segments_from_volcengine_result
from core.external.asr_providers.volcengine_auth import (
	VolcengineCredentials,
	build_volcengine_headers,
	parse_volcengine_credentials,
)

SUBMIT_URL = "https://openspeech.bytedance.com/api/v3/auc/bigmodel/submit"
QUERY_URL = "https://openspeech.bytedance.com/api/v3/auc/bigmodel/query"
FLASH_URL = "https://openspeech.bytedance.com/api/v3/auc/bigmodel/recognize/flash"
POLL_INTERVAL_S = 0.5

VOLCENGINE_SUCCESS = "20000000"
VOLCENGINE_PENDING = {"20000001", "20000002"}

# Official doc sample URL for connectivity probes (standard submit requires url).
VOLCENGINE_CONNECTIVITY_SAMPLE_URL = (
	"https://pro-en-ali-pub.en5static.com/easinote5_public/uwixkwvzhhqjjhnohwvyzzwnykhhihhh.mp3"
)

VolcengineApiKind = Literal["standard", "flash"]


def volcengine_api_kind(resource_id: str) -> VolcengineApiKind:
	rid = (resource_id or "").strip()
	if rid.endswith("_turbo") or rid == "volc.bigasr.auc_turbo":
		return "flash"
	return "standard"


def _parse_status(resp: httpx.Response) -> tuple[str, str]:
	code = resp.headers.get("X-Api-Status-Code", "")
	msg = resp.headers.get("X-Api-Message", resp.text[:300])
	return code, msg


def _raise_submit_error(resp: httpx.Response) -> None:
	code, msg = _parse_status(resp)
	if resp.status_code in {401, 403}:
		raise AsrCloudError("auth", f"Volcengine auth failed ({resp.status_code}): {msg}", fallback_eligible=True)
	if code and code != VOLCENGINE_SUCCESS:
		raise AsrCloudError("provider_error", f"Volcengine submit failed: {code} {msg}")
	if resp.status_code >= 400:
		raise AsrCloudError("provider_error", f"Volcengine submit HTTP {resp.status_code}: {msg}")


def volcengine_submit_probe(
	*,
	creds: VolcengineCredentials,
	resource_id: str,
	audio_url: str,
	timeout_s: float = 20.0,
) -> tuple[bool, str | None]:
	"""Lightweight submit probe using public audio URL (standard API contract)."""

	request_id = str(uuid.uuid4())
	headers = build_volcengine_headers(creds, resource_id=resource_id, request_id=request_id)
	body = {
		"user": {"uid": "video-helper-probe"},
		"audio": {"url": audio_url, "format": "mp3"},
		"request": {"model_name": "bigmodel", "enable_itn": True, "show_utterances": True},
	}
	with httpx.Client(timeout=timeout_s, trust_env=False) as client:
		resp = client.post(SUBMIT_URL, headers=headers, content=json.dumps(body))
	code, msg = _parse_status(resp)
	if code == VOLCENGINE_SUCCESS or resp.status_code == 200:
		return True, None
	if resp.status_code in {401, 403} or code in {"20000003", "45000001", "45000002"}:
		return False, "auth" if resp.status_code != 403 else "forbidden"
	return False, "provider_error"


def _transcribe_flash(
	*,
	client: httpx.Client,
	creds: VolcengineCredentials,
	resource_id: str,
	audio_path: Path,
	timings: AsrCloudTimingsMs,
	total_start: float,
) -> tuple[AsrResult, AsrCloudTimingsMs]:
	request_id = str(uuid.uuid4())
	headers = build_volcengine_headers(creds, resource_id=resource_id, request_id=request_id)
	audio_b64 = base64.b64encode(audio_path.read_bytes()).decode("ascii")
	body: dict = {
		"user": {"uid": "video-helper"},
		"audio": {"data": audio_b64, "format": "wav", "rate": 16000, "bits": 16, "channel": 1},
		"request": {"model_name": "bigmodel", "enable_itn": True, "show_utterances": True},
	}

	t0 = time.perf_counter()
	resp = client.post(FLASH_URL, headers=headers, content=json.dumps(body))
	timings.submit_ms = (time.perf_counter() - t0) * 1000.0
	timings.upload_ms = timings.submit_ms
	code, msg = _parse_status(resp)
	if code != VOLCENGINE_SUCCESS:
		_raise_submit_error(resp)
	try:
		result_body = resp.json()
	except Exception as exc:
		raise AsrCloudError("provider_error", "Volcengine flash returned invalid JSON") from exc

	segments, language = segments_from_volcengine_result(result_body or {})
	if not segments:
		raise AsrCloudError("empty_transcript", "Volcengine produced empty transcript", fallback_eligible=False)
	timings.total_ms = (time.perf_counter() - total_start) * 1000.0
	return AsrResult(provider=f"volcengine/{resource_id}", language=language, segments=segments), timings


def _transcribe_standard(
	*,
	client: httpx.Client,
	creds: VolcengineCredentials,
	resource_id: str,
	audio_path: Path,
	timeout_s: float,
	timings: AsrCloudTimingsMs,
	total_start: float,
	progress_cb: Callable[[str], None] | None,
) -> tuple[AsrResult, AsrCloudTimingsMs]:
	# Standard API (doc 1354868): submit requires audio.url — use base64 only as fallback for small local files.
	request_id = str(uuid.uuid4())
	headers = build_volcengine_headers(creds, resource_id=resource_id, request_id=request_id)
	audio_b64 = base64.b64encode(audio_path.read_bytes()).decode("ascii")
	body: dict = {
		"user": {"uid": "video-helper"},
		"audio": {
			"data": audio_b64,
			"format": "wav",
			"rate": 16000,
			"bits": 16,
			"channel": 1,
		},
		"request": {"model_name": "bigmodel", "enable_itn": True, "show_utterances": True},
	}

	if progress_cb:
		progress_cb(f"asr=cloud provider=volcengine resource={resource_id}")

	t0 = time.perf_counter()
	submit_resp = client.post(SUBMIT_URL, headers=headers, content=json.dumps(body))
	submit_code, submit_msg = _parse_status(submit_resp)
	if submit_code and submit_code != VOLCENGINE_SUCCESS:
		if submit_resp.status_code in {401, 403}:
			raise AsrCloudError(
				"auth",
				f"Volcengine auth failed ({submit_resp.status_code}): {submit_msg}. "
				"Ensure OpenSpeech API Key (not Ark chat key) and activated ASR service.",
				fallback_eligible=True,
			)
		raise AsrCloudError("provider_error", f"Volcengine submit failed: {submit_code} {submit_msg}")
	if submit_resp.status_code >= 400:
		raise AsrCloudError("provider_error", f"Volcengine submit HTTP {submit_resp.status_code}: {submit_msg}")

	x_tt_logid = submit_resp.headers.get("X-Tt-Logid", "")
	timings.submit_ms = (time.perf_counter() - t0) * 1000.0
	timings.upload_ms = timings.submit_ms

	query_headers = build_volcengine_headers(
		creds,
		resource_id=resource_id,
		request_id=request_id,
		x_tt_logid=x_tt_logid or None,
	)

	def _poll() -> tuple[str, dict | None]:
		resp = client.post(QUERY_URL, headers=query_headers, content="{}")
		code, msg = _parse_status(resp)
		if code == VOLCENGINE_SUCCESS:
			try:
				return "SUCCEEDED", resp.json()
			except Exception:
				return "SUCCEEDED", {}
		if code in VOLCENGINE_PENDING:
			return "PENDING", None
		if code:
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
	return AsrResult(provider=f"volcengine/{resource_id}", language=language, segments=segments), timings


def transcribe_volcengine_bigmodel(
	*,
	audio_path: Path,
	api_key: str,
	resource_id: str,
	audio_duration_s: float | None,
	progress_cb: Callable[[str], None] | None = None,
) -> tuple[AsrResult, AsrCloudTimingsMs]:
	if not audio_path.is_file():
		raise AsrCloudError("content_error", "audio file not readable", fallback_eligible=False)

	creds = parse_volcengine_credentials(api_key)
	rid = (resource_id or "volc.seedasr.auc").strip()
	timeout_s = compute_cloud_timeout_s(audio_duration_s)
	timings = AsrCloudTimingsMs()
	total_start = time.perf_counter()

	with httpx.Client(timeout=timeout_s, trust_env=False) as client:
		if volcengine_api_kind(rid) == "flash":
			return _transcribe_flash(
				client=client,
				creds=creds,
				resource_id=rid,
				audio_path=audio_path,
				timings=timings,
				total_start=total_start,
			)
		return _transcribe_standard(
			client=client,
			creds=creds,
			resource_id=rid,
			audio_path=audio_path,
			timeout_s=timeout_s,
			timings=timings,
			total_start=total_start,
			progress_cb=progress_cb,
		)
