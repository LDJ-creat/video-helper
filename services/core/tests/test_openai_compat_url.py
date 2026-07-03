from __future__ import annotations

from core.llm.openai_compat_url import openai_compat_models_list_url, resolve_openai_compat_chat_endpoint


def test_volcengine_responses_endpoint_used_as_is() -> None:
	base = "https://ark.cn-beijing.volces.com/api/v3/responses"
	assert resolve_openai_compat_chat_endpoint(base) == base
	assert openai_compat_models_list_url(base) == "https://ark.cn-beijing.volces.com/api/v3/models"


def test_volcengine_v3_root_appends_chat_completions_not_v1() -> None:
	base = "https://ark.cn-beijing.volces.com/api/v3"
	assert (
		resolve_openai_compat_chat_endpoint(base)
		== "https://ark.cn-beijing.volces.com/api/v3/chat/completions"
	)
	assert openai_compat_models_list_url(base) == "https://ark.cn-beijing.volces.com/api/v3/models"


def test_openai_v1_root_appends_chat_completions() -> None:
	base = "https://api.openai.com/v1"
	assert resolve_openai_compat_chat_endpoint(base) == "https://api.openai.com/v1/chat/completions"


def test_bare_host_appends_v1_chat_completions() -> None:
	base = "https://proxy.example.com"
	assert resolve_openai_compat_chat_endpoint(base) == "https://proxy.example.com/v1/chat/completions"
