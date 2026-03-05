from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LLMCatalogModel:
	model_id: str
	display_name: str


@dataclass(frozen=True)
class LLMCatalogProvider:
	provider_id: str
	display_name: str
	base_url: str
	models: tuple[LLMCatalogModel, ...]


_PROVIDERS: tuple[LLMCatalogProvider, ...] = (
	LLMCatalogProvider(
		provider_id="anthropic",
		display_name="Anthropic",
		base_url="https://api.anthropic.com",
		models=(
			LLMCatalogModel(model_id="claude-opus-4-6", display_name="Claude Opus 4.6"),
			LLMCatalogModel(model_id="claude-sonnet-4-6", display_name="Claude Sonnet 4.6"),
			LLMCatalogModel(model_id="claude-haiku-4-5", display_name="Claude Haiku 4.5"),
		),
	),
	LLMCatalogProvider(
		provider_id="openrouter",
		display_name="OpenRouter",
		base_url="https://openrouter.ai/api/v1",
		models=(
			LLMCatalogModel(model_id="openai/gpt-5-3-chat", display_name="GPT-5.3 Chat"),
			LLMCatalogModel(model_id="anthropic/claude-opus-4-6", display_name="Claude Opus 4.6"),
			LLMCatalogModel(model_id="anthropic/claude-sonnet-4-6", display_name="Claude Sonnet 4.6"),
			LLMCatalogModel(model_id="anthropic/claude-haiku-4-5", display_name="Claude Haiku 4.5"),
			LLMCatalogModel(model_id="google/gemini-3-1-flash-lite-preview", display_name="Gemini 3.1 Flash Lite Preview"),
			LLMCatalogModel(model_id="google/gemini-3-1-pro-preview", display_name="Gemini 3.1 Pro Preview"),
			LLMCatalogModel(model_id="deepseek/deepseek-v3.2", display_name="DeepSeek V3.2"),
			LLMCatalogModel(model_id="xai/grok-4-1-fast", display_name="Grok 4.1 Fast"),
		),
	),
	LLMCatalogProvider(
		provider_id="openai",
		display_name="OpenAI",
		base_url="https://api.openai.com/v1",
		models=(
			LLMCatalogModel(model_id="gpt-5-2", display_name="GPT-5.2"),
			LLMCatalogModel(model_id="gpt-5-mini", display_name="GPT-5 Mini"),
			LLMCatalogModel(model_id="gpt-5-nano", display_name="GPT-5 Nano"),
			LLMCatalogModel(model_id="gpt-4-1", display_name="GPT-4.1"),
			LLMCatalogModel(model_id="gpt-4-1-mini", display_name="GPT-4.1 Mini"),
			LLMCatalogModel(model_id="gpt-4o", display_name="GPT-4o"),
			LLMCatalogModel(model_id="gpt-4o-mini", display_name="GPT-4o Mini"),
		),
	),
	LLMCatalogProvider(
		provider_id="google",
		display_name="Google Gemini",
		base_url="https://generativelanguage.googleapis.com/v1beta",
		models=(
			LLMCatalogModel(model_id="gemini-3-pro-preview", display_name="Gemini 3 Pro Preview"),
			LLMCatalogModel(model_id="gemini-3-flash-preview", display_name="Gemini 3 Flash Preview"),
			LLMCatalogModel(model_id="gemini-2-5-pro", display_name="Gemini 2.5 Pro"),
			LLMCatalogModel(model_id="gemini-2-5-flash", display_name="Gemini 2.5 Flash"),
		),
	),
	LLMCatalogProvider(
		provider_id="qwen",
		display_name="阿里百炼",
		base_url="https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
		models=(
			LLMCatalogModel(model_id="qwen-max", display_name="Qwen Max"),
			LLMCatalogModel(model_id="qwen-plus", display_name="Qwen Plus"),
			LLMCatalogModel(model_id="qwen-flash", display_name="Qwen Flash"),
		),
	),
	LLMCatalogProvider(
		provider_id="nvidia",
		display_name="NVIDIA NIM",
		base_url="https://integrate.api.nvidia.com/v1/chat/completions",
		models=(
			LLMCatalogModel(model_id="z-ai/glm-5", display_name="GLM-5"),
			LLMCatalogModel(model_id="minimaxai/minimax-m2.5", display_name="MiniMax M2.5"),
			LLMCatalogModel(model_id="meta/llama-3-1-405b-instruct", display_name="Llama 3.1 405B"),
			LLMCatalogModel(model_id="mistralai/mistral-large", display_name="Mistral Large"),
		),
	),
	LLMCatalogProvider(
		provider_id="deepseek",
		display_name="DeepSeek",
		base_url="https://api.deepseek.com/v1",
		models=(
			LLMCatalogModel(model_id="deepseek-v3-2", display_name="DeepSeek V3.2"),
			LLMCatalogModel(model_id="deepseek-chat", display_name="DeepSeek Chat"),
			LLMCatalogModel(model_id="deepseek-reasoner", display_name="DeepSeek Reasoner"),
		),
	),
	LLMCatalogProvider(
		provider_id="xai",
		display_name="xAI Grok",
		base_url="https://api.x.ai/v1",
		models=(
			LLMCatalogModel(model_id="grok-4-1-fast-reasoning", display_name="Grok 4.1 Fast Reasoning"),
			LLMCatalogModel(model_id="grok-4-1-fast-non-reasoning", display_name="Grok 4.1 Fast Non-Reasoning"),
			LLMCatalogModel(model_id="grok-4", display_name="Grok 4"),
			LLMCatalogModel(model_id="grok-4-20", display_name="Grok 4.20"),
		),
	),
	LLMCatalogProvider(
		provider_id="zhipu",
		display_name="Z.ai(智谱AI)",
		base_url="https://open.bigmodel.cn/api/paas/v4",
		models=(
			LLMCatalogModel(model_id="glm-5", display_name="GLM-5"),
			LLMCatalogModel(model_id="glm-4-7-flash", display_name="GLM-4.7 Flash"),
			LLMCatalogModel(model_id="glm-4-7", display_name="GLM-4.7"),
			LLMCatalogModel(model_id="glm-4-6", display_name="GLM-4.6"),
			LLMCatalogModel(model_id="glm-4-5", display_name="GLM-4.5"),
		),
	),
	LLMCatalogProvider(
		provider_id="minimax",
		display_name="MiniMax",
		base_url="https://api.minimaxi.com/v1",
		models=(
			LLMCatalogModel(model_id="minimax-m2-5", display_name="MiniMax M2.5"),
			LLMCatalogModel(model_id="minimax-m2-5-highspeed", display_name="MiniMax M2.5 Highspeed"),
			LLMCatalogModel(model_id="minimax-m2-her", display_name="MiniMax M2 Her"),
		),
	),
)


def list_llm_catalog_providers() -> tuple[LLMCatalogProvider, ...]:
	return _PROVIDERS


def find_provider(provider_id: str) -> LLMCatalogProvider | None:
	pid = (provider_id or "").strip().lower()
	for p in _PROVIDERS:
		if p.provider_id == pid:
			return p
	return None


def model_exists(*, provider_id: str, model_id: str) -> bool:
	p = find_provider(provider_id)
	if p is None:
		return False
	mid = (model_id or "").strip()
	return any(m.model_id == mid for m in p.models)


def resolve_runtime_model_name(*, provider_id: str, model_id: str) -> str | None:
	"""Map modelId to the provider runtime 'model' string.

Current convention: modelId is `${providerId}:${modelName}`.
"""
	if not model_exists(provider_id=provider_id, model_id=model_id):
		return None
	mid = (model_id or "").strip()
	if ":" in mid:
		_, name = mid.split(":", 1)
		name = name.strip()
		return name or None
	return mid or None
