from __future__ import annotations

import httpx

from core.asr.runtime import AsrRuntimeSettings
from core.external.asr_dashscope_upload import UPLOAD_POLICY_URL
from core.external.asr_providers.base import classify_http_error
from core.external.asr_providers.volcengine import VOLCENGINE_CONNECTIVITY_SAMPLE_URL, volcengine_submit_probe
from core.external.asr_providers.volcengine_auth import parse_volcengine_credentials


class AsrActiveTestError(Exception):
	def __init__(self, code: str, message: str):
		super().__init__(message)
		self.code = code
		self.message = message


def _raise_from_http(resp: httpx.Response) -> None:
	err = classify_http_error(resp.status_code, resp.text)
	raise AsrActiveTestError(err.kind, str(err)) from err


def _test_dashscope_connectivity(*, api_key: str, model_id: str) -> None:
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
	with httpx.Client(timeout=30.0, trust_env=False) as client:
		resp = client.get(
			"https://api.openai.com/v1/models",
			headers={"Authorization": f"Bearer {api_key}"},
		)
	if resp.status_code != 200:
		_raise_from_http(resp)


def _test_volcengine_connectivity(*, api_key: str, resource_id: str) -> None:
	try:
		creds = parse_volcengine_credentials(api_key)
	except ValueError as exc:
		raise AsrActiveTestError("invalid_credentials", str(exc)) from exc

	rid = (resource_id or "volc.seedasr.auc").strip()
	ok, reason = volcengine_submit_probe(
		creds=creds,
		resource_id=rid,
		audio_url=VOLCENGINE_CONNECTIVITY_SAMPLE_URL,
	)
	if ok:
		return
	if reason in {"auth", "forbidden"}:
		raise AsrActiveTestError(
			"auth",
			"Volcengine rejected credentials (HTTP 403). Use OpenSpeech API Key from 豆包语音控制台, "
			"not Ark/LLM key; legacy console may use app_id|access_token.",
		)
	raise AsrActiveTestError("provider_error", "Volcengine connectivity probe failed")


def run_asr_connectivity_test(settings: AsrRuntimeSettings) -> tuple[bool, int, str, str | None]:
	if not settings.api_key:
		raise AsrActiveTestError("missing_credentials", "API key not configured")

	import time

	start = time.perf_counter()
	if settings.provider_id == "dashscope":
		_test_dashscope_connectivity(api_key=settings.api_key, model_id=settings.model_id)
	elif settings.provider_id == "openai":
		_test_openai_connectivity(api_key=settings.api_key)
	elif settings.provider_id == "volcengine":
		_test_volcengine_connectivity(api_key=settings.api_key, resource_id=settings.model_id)
	else:
		raise AsrActiveTestError("unknown_provider", f"Unknown provider: {settings.provider_id}")

	latency_ms = int((time.perf_counter() - start) * 1000)
	return True, latency_ms, "cloud", None
