from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import httpx

from core.llm.catalog import (
	LLMCatalogProvider,
	anthropic_models_list_url,
	gemini_models_list_url,
	openai_compat_models_list_url,
)
from core.llm.catalog import ListingKind

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RemoteModelItem:
	model_id: str
	display_name: str


def listing_kind_of_provider(provider: LLMCatalogProvider | dict) -> ListingKind:
	if isinstance(provider, LLMCatalogProvider):
		return provider.listing_kind
	return "openai_compat"


def _parse_openai_compat_models(payload: Any) -> list[RemoteModelItem]:
	out: list[RemoteModelItem] = []
	if not isinstance(payload, dict):
		return out
	data = payload.get("data")
	if not isinstance(data, list):
		return out
	for row in data:
		if not isinstance(row, dict):
			continue
		mid = row.get("id")
		if not isinstance(mid, str) or not mid.strip():
			continue
		owned = row.get("owned_by")
		dname = f"{mid} ({owned})" if isinstance(owned, str) and owned.strip() else mid
		out.append(RemoteModelItem(model_id=mid.strip(), display_name=dname))
	return out


def _parse_anthropic_models(payload: Any) -> list[RemoteModelItem]:
	out: list[RemoteModelItem] = []
	if not isinstance(payload, dict):
		return out
	data = payload.get("data")
	if not isinstance(data, list):
		return out
	for row in data:
		if not isinstance(row, dict):
			continue
		mid = row.get("id")
		if not isinstance(mid, str) or not mid.strip():
			continue
		disp = row.get("display_name")
		dname = disp.strip() if isinstance(disp, str) and disp.strip() else mid.strip()
		out.append(RemoteModelItem(model_id=mid.strip(), display_name=dname))
	return out


def _parse_gemini_models(payload: Any) -> list[RemoteModelItem]:
	out: list[RemoteModelItem] = []
	if not isinstance(payload, dict):
		return out
	models = payload.get("models")
	if not isinstance(models, list):
		return out
	for row in models:
		if not isinstance(row, dict):
			continue
		name = row.get("name")
		if not isinstance(name, str) or not name.strip():
			continue
		raw = name.strip()
		# e.g. models/gemini-2.0-flash -> gemini-2.0-flash (align with typical generateContent model ids)
		short = raw.split("/", 1)[-1].strip() if "/" in raw else raw
		if not short:
			continue
		methods = row.get("supportedGenerationMethods")
		if isinstance(methods, list) and len(methods) > 0 and "generateContent" not in methods:
			continue
		disp = row.get("displayName")
		dname = disp.strip() if isinstance(disp, str) and disp.strip() else short
		out.append(RemoteModelItem(model_id=short, display_name=dname))
	return out


def fetch_remote_models_for_provider(
	*,
	provider: LLMCatalogProvider | dict,
	base_url: str,
	api_key: str,
	timeout_s: float = 15.0,
	transport: httpx.BaseTransport | None = None,
) -> tuple[list[RemoteModelItem], str | None]:
	"""Return (models, error_message). error_message is set on failure."""

	key = (api_key or "").strip()
	if not key:
		return [], "missing_api_key"

	kind = listing_kind_of_provider(provider)
	url: str
	headers: dict[str, str]

	if kind == "anthropic":
		list_url = anthropic_models_list_url(base_url)
		if not list_url:
			return [], "invalid_base_url"
		version = (os.environ.get("ANTHROPIC_VERSION") or "2023-06-01").strip() or "2023-06-01"
		headers = {
			"x-api-key": key,
			"anthropic-version": version,
			"Accept": "application/json",
		}
		url = list_url
	elif kind == "gemini":
		list_url = gemini_models_list_url(base_url)
		if not list_url:
			return [], "invalid_base_url"
		# Prefer query key (documented for Google AI); avoid logging URL with key.
		qs = urlencode({"key": key})
		url = f"{list_url}?{qs}"
		headers = {"Accept": "application/json"}
	else:
		list_url = openai_compat_models_list_url(base_url)
		if not list_url:
			return [], "invalid_base_url"
		url = list_url
		headers = {
			"Authorization": f"Bearer {key}",
			"Accept": "application/json",
		}

	client = httpx.Client(timeout=max(5.0, float(timeout_s)), transport=transport, headers=headers, trust_env=False)
	try:
		resp = client.get(url)
	except httpx.RequestError as e:
		logger.info("remote model list request error: %s", type(e).__name__)
		return [], "provider_unavailable"

	status = int(resp.status_code)
	if status == 401 or status == 403:
		return [], "invalid_credentials"
	if status >= 500:
		return [], "provider_unavailable"
	if status >= 400:
		return [], "list_models_failed"

	try:
		payload = resp.json()
	except Exception:
		return [], "invalid_response"

	if kind == "anthropic":
		items = _parse_anthropic_models(payload)
	elif kind == "gemini":
		items = _parse_gemini_models(payload)
	else:
		items = _parse_openai_compat_models(payload)

	return items, None
