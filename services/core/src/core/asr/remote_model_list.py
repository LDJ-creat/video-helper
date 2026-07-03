from __future__ import annotations

from dataclasses import dataclass

import httpx

from core.asr.catalog import OFFICIAL_VOLCENGINE_RESOURCES
from core.external.asr_dashscope_upload import UPLOAD_POLICY_URL
from core.llm.http_headers import http_header_value_error
from core.llm.openai_compat_url import openai_compat_models_list_url


@dataclass
class RemoteAsrModelItem:
	model_id: str
	display_name: str


def fetch_dashscope_asr_models(*, api_key: str, timeout_s: float = 15.0) -> tuple[list[RemoteAsrModelItem], str | None]:
	key = (api_key or "").strip()
	if not key:
		return [], "missing_api_key"
	if http_header_value_error(key):
		return [], "invalid_api_key"

	candidates = [
		("paraformer-v2", "Paraformer v2"),
		("paraformer-8k-v2", "Paraformer 8k v2"),
		("paraformer-v1", "Paraformer v1"),
		("paraformer-mtl-v1", "Paraformer multilingual v1"),
	]
	out: list[RemoteAsrModelItem] = []
	with httpx.Client(timeout=timeout_s, trust_env=False) as client:
		for model_id, display_name in candidates:
			resp = client.get(
				UPLOAD_POLICY_URL,
				headers={"Authorization": f"Bearer {key}"},
				params={"action": "getPolicy", "model": model_id},
			)
			if resp.status_code == 200:
				data = resp.json().get("data")
				if isinstance(data, dict) and data.get("upload_host"):
					out.append(RemoteAsrModelItem(model_id=model_id, display_name=display_name))
			elif resp.status_code in {401, 403}:
				return [], "invalid_credentials"
	if not out:
		return [], "list_models_failed"
	return out, None


def fetch_openai_whisper_models(*, api_key: str, timeout_s: float = 15.0) -> tuple[list[RemoteAsrModelItem], str | None]:
	key = (api_key or "").strip()
	if not key:
		return [], "missing_api_key"
	if http_header_value_error(key):
		return [], "invalid_api_key"
	list_url = openai_compat_models_list_url("https://api.openai.com/v1")
	if not list_url:
		return [], "invalid_base_url"
	with httpx.Client(timeout=timeout_s, trust_env=False) as client:
		resp = client.get(list_url, headers={"Authorization": f"Bearer {key}", "Accept": "application/json"})
	if resp.status_code in {401, 403}:
		return [], "invalid_credentials"
	if resp.status_code >= 400:
		return [], "list_models_failed"
	try:
		payload = resp.json()
	except Exception:
		return [], "invalid_response"
	data = payload.get("data")
	if not isinstance(data, list):
		return [], "invalid_response"
	out: list[RemoteAsrModelItem] = []
	for row in data:
		if not isinstance(row, dict):
			continue
		mid = row.get("id")
		if not isinstance(mid, str) or not mid.strip():
			continue
		mid = mid.strip()
		if "whisper" not in mid.lower():
			continue
		out.append(RemoteAsrModelItem(model_id=mid, display_name=mid))
	if not out:
		out.append(RemoteAsrModelItem(model_id="whisper-1", display_name="whisper-1"))
	return out, None


def fetch_volcengine_asr_resources(*, api_key: str, timeout_s: float = 20.0) -> tuple[list[RemoteAsrModelItem], str | None]:
	from core.external.asr_providers.volcengine import VOLCENGINE_CONNECTIVITY_SAMPLE_URL, volcengine_submit_probe
	from core.external.asr_providers.volcengine_auth import parse_volcengine_credentials

	raw = (api_key or "").strip()
	if not raw:
		return [], "missing_api_key"
	if http_header_value_error(raw):
		return [], "invalid_api_key"
	try:
		creds = parse_volcengine_credentials(raw)
	except ValueError:
		return [], "invalid_credentials"

	out: list[RemoteAsrModelItem] = []
	auth_failed = False
	for resource_id, display_name, _kind in OFFICIAL_VOLCENGINE_RESOURCES:
		ok, reason = volcengine_submit_probe(
			creds=creds,
			resource_id=resource_id,
			audio_url=VOLCENGINE_CONNECTIVITY_SAMPLE_URL,
			timeout_s=timeout_s,
		)
		if ok:
			out.append(RemoteAsrModelItem(model_id=resource_id, display_name=display_name))
		elif reason in {"auth", "forbidden"}:
			auth_failed = True
	if auth_failed and not out:
		return [], "invalid_credentials"
	if not out:
		return [RemoteAsrModelItem(model_id=r[0], display_name=r[1]) for r in OFFICIAL_VOLCENGINE_RESOURCES], None
	return out, None


def fetch_remote_asr_models_for_provider(
	*,
	provider_id: str,
	api_key: str,
) -> tuple[list[RemoteAsrModelItem], str | None]:
	pid = (provider_id or "").strip().lower()
	if pid == "dashscope":
		return fetch_dashscope_asr_models(api_key=api_key)
	if pid == "openai":
		return fetch_openai_whisper_models(api_key=api_key)
	if pid == "volcengine":
		return fetch_volcengine_asr_resources(api_key=api_key)
	return [], "unknown_provider"
