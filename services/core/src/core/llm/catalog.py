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
		display_name="Anthropic (官方 Claude API)",
		base_url="https://api.anthropic.com",
		models=(
			LLMCatalogModel(model_id="claude-opus-4-6", display_name="Claude Opus 4.6"),
			LLMCatalogModel(model_id="claude-sonnet-4-6", display_name="Claude Sonnet 4.6"),
		),
	),
	LLMCatalogProvider(
		provider_id="openrouter",
		display_name="OpenRouter",
		base_url="https://openrouter.ai/api/v1",
		models=(
			# Claude 系列 (最新旗舰)
			LLMCatalogModel(model_id="anthropic/claude-opus-4.6", display_name="Claude Opus 4.5"),
			LLMCatalogModel(model_id="anthropic/claude-sonnet-4.6", display_name="Claude Sonnet 4.5"),
			LLMCatalogModel(model_id="anthropic/claude-3.7-sonnet", display_name="Claude 3.7 Sonnet"),
			# OpenAI 系列 (最新)
			LLMCatalogModel(model_id="openai/gpt-5", display_name="GPT-5"),
			LLMCatalogModel(model_id="openai/gpt-4.1", display_name="GPT-4.1"),
			LLMCatalogModel(model_id="openai/gpt-4o", display_name="GPT-4o"),
			# Google Gemini 系列
			LLMCatalogModel(model_id="google/gemini-3-flash-preview", display_name="Gemini 3 Flash Preview"),
			LLMCatalogModel(model_id="google/gemini-3-pro-preview", display_name="Gemini 3 Pro Preview"),
			LLMCatalogModel(model_id="google/gemini-2.5-pro", display_name="Gemini 2.5 Pro"),
			LLMCatalogModel(model_id="google/gemini-2.5-flash", display_name="Gemini 2.5 Flash"),
			# DeepSeek 系列
			LLMCatalogModel(model_id="deepseek/deepseek-r1", display_name="DeepSeek R1"),
			LLMCatalogModel(model_id="deepseek/deepseek-chat", display_name="DeepSeek Chat"),
			# xAI Grok 系列
			LLMCatalogModel(model_id="x-ai/grok-4", display_name="Grok 4"),
			LLMCatalogModel(model_id="x-ai/grok-3", display_name="Grok 3"),
		),
	),
	LLMCatalogProvider(
		provider_id="openai",
		display_name="OpenAI",
		base_url="https://api.openai.com/v1",
		models=(
			# GPT-5 系列 (最新旗舰)
			LLMCatalogModel(model_id="gpt-5", display_name="GPT-5"),
			LLMCatalogModel(model_id="gpt-5-mini", display_name="GPT-5 Mini"),
			# GPT-4.1 系列
			LLMCatalogModel(model_id="gpt-4.1", display_name="GPT-4.1"),
			LLMCatalogModel(model_id="gpt-4.1-mini", display_name="GPT-4.1 Mini"),
			# GPT-4o 系列 (多模态)
			LLMCatalogModel(model_id="gpt-4o", display_name="GPT-4o"),
			LLMCatalogModel(model_id="gpt-4o-mini", display_name="GPT-4o Mini"),
		),
	),
	LLMCatalogProvider(
		provider_id="qwen",
		display_name="阿里通义千问 (OpenAI-compatible)",
		base_url="https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
		models=(
			LLMCatalogModel(model_id="qwen-max", display_name="Qwen Max"),
			LLMCatalogModel(model_id="qwen-plus", display_name="Qwen Plus"),
			LLMCatalogModel(model_id="qwen-flash", display_name="Qwen Flash"),
			LLMCatalogModel(model_id="qwen-turbo", display_name="Qwen Turbo"),
		),
	),
	LLMCatalogProvider(
		provider_id="nvidia",
		display_name="NVIDIA NIM (OpenAI-compatible)",
		base_url="https://integrate.api.nvidia.com/v1/chat/completions",
		models=(
			LLMCatalogModel(model_id="z-ai/glm-4.7", display_name="GLM-4.7"),
			LLMCatalogModel(model_id="minimaxai/minimax-m2.1", display_name="Minimax M2.1"),
			LLMCatalogModel(model_id="kimi-k2", display_name="Kimi K2"),
			LLMCatalogModel(model_id="meta/llama-3.1-405b-instruct", display_name="Llama 3.1 405B"),
			LLMCatalogModel(model_id="mistralai/mistral-large", display_name="Mistral Large"),
		),
	),
	LLMCatalogProvider(
		provider_id="groq",
		display_name="Groq (OpenAI-compatible)",
		base_url="https://api.groq.com/openai/v1",
		models=(
			LLMCatalogModel(model_id="llama-3.1-8b-instant", display_name="Llama 3.1 8B Instant"),
			LLMCatalogModel(model_id="llama-3.3-70b-versatile", display_name="Llama 3.3 70B Versatile"),
		),
	),
	LLMCatalogProvider(
		provider_id="deepseek",
		display_name="DeepSeek (OpenAI-compatible)",
		base_url="https://api.deepseek.com/v1",
		models=(
			LLMCatalogModel(model_id="deepseek-chat", display_name="DeepSeek Chat"),
			LLMCatalogModel(model_id="deepseek-reasoner", display_name="DeepSeek Reasoner"),
		),
	),
	LLMCatalogProvider(
		provider_id="xai",
		display_name="xAI Grok (OpenAI-compatible)",
		base_url="https://api.x.ai/v1",
		models=(
			# Grok 4.1 系列 (最新)
			LLMCatalogModel(model_id="grok-4-1-fast-reasoning", display_name="Grok 4.1 Fast Reasoning"),
			LLMCatalogModel(model_id="grok-4-1-fast-non-reasoning", display_name="Grok 4.1 Fast Non-Reasoning"),
			# Grok 4 系列
			LLMCatalogModel(model_id="grok-4", display_name="Grok 4"),
			LLMCatalogModel(model_id="grok-4-fast", display_name="Grok 4 Fast"),
			# Grok 3 系列
			LLMCatalogModel(model_id="grok-3", display_name="Grok 3"),
			LLMCatalogModel(model_id="grok-3-mini", display_name="Grok 3 Mini"),
		),
	),
	LLMCatalogProvider(
		provider_id="doubao",
		display_name="火山引擎豆包 (OpenAI-compatible)",
		base_url="https://ark.cn-beijing.volces.com/api/v3",
		models=(
			LLMCatalogModel(model_id="doubao-seed-1-6-251015", display_name="豆包 Seed 1.6 (2024-10)"),
			LLMCatalogModel(model_id="doubao-pro-32k", display_name="豆包 Pro 32K"),
			LLMCatalogModel(model_id="doubao-lite-32k", display_name="豆包 Lite 32K"),
		),
	),
	LLMCatalogProvider(
		provider_id="zhipu",
		display_name="智谱AI (OpenAI-compatible)",
		base_url="https://open.bigmodel.cn/api/paas/v4",
		models=(
			LLMCatalogModel(model_id="GLM-4.7", display_name="GLM-4.7"),
			LLMCatalogModel(model_id="GLM-4.6", display_name="GLM-4.6"),
			LLMCatalogModel(model_id="GLM-4.5", display_name="GLM-4.5"),
			LLMCatalogModel(model_id="GLM-4.5-Air", display_name="GLM-4.5 Air"),
			LLMCatalogModel(model_id="GLM-4-Flash", display_name="GLM-4 Flash"),
		),
	),
	LLMCatalogProvider(
		provider_id="minimax",
		display_name="MiniMax (OpenAI-compatible)",
		base_url="https://api.minimaxi.com/v1",
		models=(
			LLMCatalogModel(model_id="MiniMax-M2.1", display_name="MiniMax M2.1"),
			LLMCatalogModel(model_id="MiniMax-M2", display_name="MiniMax M2"),
			LLMCatalogModel(model_id="abab6.5s-chat", display_name="abab6.5s (超长上下文)"),
			LLMCatalogModel(model_id="abab6.5t-chat", display_name="abab6.5t (中文优化)"),
		),
	),
	LLMCatalogProvider(
		provider_id="google",
		display_name="Google Gemini",
		base_url="https://generativelanguage.googleapis.com/v1beta",
		models=(
			# Gemini 3 系列 (最新旗舰)
			LLMCatalogModel(model_id="gemini-3-pro-preview", display_name="Gemini 3 Pro Preview"),
			LLMCatalogModel(model_id="gemini-3-flash-preview", display_name="Gemini 3 Flash Preview"),
			# Gemini 2.5 系列
			LLMCatalogModel(model_id="gemini-2.5-pro-latest", display_name="Gemini 2.5 Pro"),
			LLMCatalogModel(model_id="gemini-2.5-flash-latest", display_name="Gemini 2.5 Flash"),
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
