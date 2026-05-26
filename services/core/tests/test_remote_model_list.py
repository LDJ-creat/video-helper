from __future__ import annotations

import httpx

from core.llm.catalog import LLMCatalogProvider
from core.llm.remote_model_list import fetch_remote_models_for_provider


def test_openai_compat_parses_models() -> None:
	p = LLMCatalogProvider(
		provider_id="openai",
		display_name="OpenAI",
		base_url="https://api.openai.com/v1",
		listing_kind="openai_compat",
	)
	body = {"data": [{"id": "gpt-4o", "owned_by": "openai"}, {"id": "gpt-4o-mini"}]}
	transport = httpx.MockTransport(
		lambda req: httpx.Response(
			200,
			json=body,
			request=req,
		)
	)
	items, err = fetch_remote_models_for_provider(
		provider=p,
		base_url="https://api.openai.com/v1",
		api_key="sk-test",
		transport=transport,
	)
	assert err is None
	assert len(items) == 2
	assert items[0].model_id == "gpt-4o"


def test_openai_compat_strips_chat_suffix_for_list_url() -> None:
	p = LLMCatalogProvider(
		provider_id="qwen",
		display_name="Qwen",
		base_url="https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
		listing_kind="openai_compat",
	)
	captured: list[str] = []

	def handler(req: httpx.Request) -> httpx.Response:
		captured.append(str(req.url))
		return httpx.Response(200, json={"data": [{"id": "qwen-max"}]}, request=req)

	transport = httpx.MockTransport(handler)
	items, err = fetch_remote_models_for_provider(
		provider=p,
		base_url="https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
		api_key="sk-q",
		transport=transport,
	)
	assert err is None
	assert len(items) == 1
	assert captured
	assert str(captured[0]).endswith("/compatible-mode/v1/models")


def test_missing_key_returns_error() -> None:
	p = LLMCatalogProvider(
		provider_id="openai",
		display_name="OpenAI",
		base_url="https://api.openai.com/v1",
		listing_kind="openai_compat",
	)
	items, err = fetch_remote_models_for_provider(provider=p, base_url="https://api.openai.com/v1", api_key="  ")
	assert err == "missing_api_key"
	assert items == []
