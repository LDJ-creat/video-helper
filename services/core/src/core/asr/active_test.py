from __future__ import annotations

import time
import wave
from pathlib import Path

import httpx

from core.asr.runtime import AsrRuntimeSettings
from core.external.asr_dashscope_upload import UPLOAD_POLICY_URL
from core.external.asr_providers.base import classify_http_error
from core.external.asr_providers.volcengine import SUBMIT_URL, VOLCENGINE_SUCCESS, _volcengine_language


class AsrActiveTestError(Exception):
	def __init__(self, code: str, message: str):
		super().__init__(message)
		self.code = code
		self.message = message


def _raise_from_http(resp: httpx.Response) -> None:
	err = classify_http_error(resp.status_code, resp.text)
	raise AsrActiveTestError(err.kind, str(err)) from err


def _test_dashscope_connectivity(*, api_key: str, model_id: str) -> None:
	"""Validate DashScope API key via upload policy (no full transcribe)."""
	with httpx.Client(timeout=30.0, trust_env=False) as client:
		resp = client.get(
			UPLOAD_POLICY_URL,
			headers={"Authorization": f"Bearer {api_key}"},
			params={"action": "getPolicy", "model": model_id},
		)
	if resp.status_code != 200:
		_raise_from_http(resp)
	data = resp.json().get("data")
	if not isinstance(data, dict) or not data.get("upload_host"):
		raise AsrActiveTestError("provider_error", "unexpected getPolicy response")


def _test_openai_connectivity(*, api_key: str) -> None:
	"""Validate OpenAI API key via models list."""
	with httpx.Client(timeout=30.0, trust_env=False) as client:
		resp = client.get(
			"https://api.openai.com/v1/models",
			headers={"Authorization": f"Bearer {api_key}"},
		)
	if resp.status_code != 200:
		_raise_from_http(resp)


def _make_test_wav(path: Path, *, duration_s: float = 0.5, sample_rate: int = 16000) -> None:
	n_frames = int(sample_rate * duration_s)
	with wave.open(str(path), "wb") as wf:
		wf.setnchannels(1)
		wf.setsampwidth(2)
		wf.setframerate(sample_rate)
		wf.writeframes(b"\x00\x00" * n_frames)


def _test_volcengine_connectivity(
	*,
	api_key: str,
	resource_id: str,
	language_hints: list[str],
) -> None:
	"""Validate Volcengine credentials via submit accept (no poll for transcript)."""
	import base64
	import json
	import tempfile
	import uuid

	with tempfile.TemporaryDirectory(prefix="asr-test-") as tmp:
		wav_path = Path(tmp) / "test.wav"
		_make_test_wav(wav_path)
		audio_b64 = base64.b64encode(wav_path.read_bytes()).decode("ascii")

	headers = {
		"X-Api-Key": api_key,
		"X-Api-Resource-Id": resource_id,
		"X-Api-Request-Id": str(uuid.uuid4()),
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

	with httpx.Client(timeout=60.0, trust_env=False) as client:
		resp = client.post(SUBMIT_URL, headers=headers, content=json.dumps(body))
	submit_code = resp.headers.get("X-Api-Status-Code", "")
	if submit_code == VOLCENGINE_SUCCESS:
		return
	if resp.status_code in {401, 403}:
		_raise_from_http(resp)
	if submit_code in {"20000003", "45000001", "45000002"}:
		msg = resp.headers.get("X-Api-Message", resp.text)
		raise AsrActiveTestError("auth", f"Volcengine auth failed: {submit_code} {msg}")
	# Non-auth business errors (e.g. invalid audio) still prove credentials reached the API.
	return


def run_asr_connectivity_test(settings: AsrRuntimeSettings) -> tuple[bool, int, str, str | None]:
	if not settings.api_key:
		raise AsrActiveTestError("missing_credentials", "API key not configured")

	start = time.perf_counter()
	if settings.provider_id == "dashscope":
		_test_dashscope_connectivity(api_key=settings.api_key, model_id=settings.model_id)
	elif settings.provider_id == "openai":
		_test_openai_connectivity(api_key=settings.api_key)
	elif settings.provider_id == "volcengine":
		_test_volcengine_connectivity(
			api_key=settings.api_key,
			resource_id=settings.model_id,
			language_hints=settings.language_hints,
		)
	else:
		raise AsrActiveTestError("unknown_provider", f"Unknown provider: {settings.provider_id}")

	latency_ms = int((time.perf_counter() - start) * 1000)
	return True, latency_ms, "cloud", None
