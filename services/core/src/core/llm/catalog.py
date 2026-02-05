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
		provider_id="openrouter",
		display_name="OpenRouter",
		base_url="https://openrouter.ai/api/v1",
		models=(
			LLMCatalogModel(model_id="openrouter:anthropic/claude-3.5-sonnet", display_name="Claude 3.5 Sonnet"),
			LLMCatalogModel(model_id="openrouter:openai/gpt-4o-mini", display_name="GPT-4o mini"),
		),
	),
	LLMCatalogProvider(
		provider_id="openai",
		display_name="OpenAI",
		base_url="https://api.openai.com/v1",
		models=(
			LLMCatalogModel(model_id="openai:gpt-4o-mini", display_name="GPT-4o mini"),
			LLMCatalogModel(model_id="openai:gpt-4o", display_name="GPT-4o"),
		),
	),
	LLMCatalogProvider(
		provider_id="nvidia",
		display_name="NVIDIA (OpenAI-compatible)",
		base_url="https://integrate.api.nvidia.com/v1",
		models=(
			LLMCatalogModel(model_id="nvidia:minimaxai/minimax-m2.1", display_name="Minimax M2.1"),
		),
	),
	LLMCatalogProvider(
		provider_id="groq",
		display_name="Groq (OpenAI-compatible)",
		base_url="https://api.groq.com/openai/v1",
		models=(
			LLMCatalogModel(model_id="groq:llama-3.1-70b-versatile", display_name="Llama 3.1 70B Versatile"),
			LLMCatalogModel(model_id="groq:llama3-70b-8192", display_name="Llama 3 70B 8192"),
			LLMCatalogModel(model_id="groq:mixtral-8x7b-32768", display_name="Mixtral 8x7B 32768"),
		),
	),
	LLMCatalogProvider(
		provider_id="together",
		display_name="Together (OpenAI-compatible)",
		base_url="https://api.together.xyz/v1",
		models=(
			LLMCatalogModel(
				model_id="together:meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo",
				display_name="Llama 3.1 70B Instruct Turbo",
			),
			LLMCatalogModel(
				model_id="together:mistralai/Mixtral-8x7B-Instruct-v0.1",
				display_name="Mixtral 8x7B Instruct v0.1",
			),
		),
	),
	LLMCatalogProvider(
		provider_id="mistral",
		display_name="Mistral (OpenAI-compatible)",
		base_url="https://api.mistral.ai/v1",
		models=(
			LLMCatalogModel(model_id="mistral:mistral-large-latest", display_name="Mistral Large (latest)"),
			LLMCatalogModel(model_id="mistral:mistral-small-latest", display_name="Mistral Small (latest)"),
		),
	),
	LLMCatalogProvider(
		provider_id="deepseek",
		display_name="DeepSeek (OpenAI-compatible)",
		base_url="https://api.deepseek.com/v1",
		models=(
			LLMCatalogModel(model_id="deepseek:deepseek-chat", display_name="DeepSeek Chat"),
			LLMCatalogModel(model_id="deepseek:deepseek-reasoner", display_name="DeepSeek Reasoner"),
		),
	),
	LLMCatalogProvider(
		provider_id="xai",
		display_name="xAI (OpenAI-compatible)",
		base_url="https://api.x.ai/v1",
		models=(
			LLMCatalogModel(model_id="xai:grok-2-latest", display_name="Grok 2 (latest)"),
			LLMCatalogModel(model_id="xai:grok-2-mini-latest", display_name="Grok 2 mini (latest)"),
		),
	),
	LLMCatalogProvider(
		provider_id="perplexity",
		display_name="Perplexity (OpenAI-compatible)",
		base_url="https://api.perplexity.ai/chat/completions",
		models=(
			LLMCatalogModel(model_id="perplexity:sonar-pro", display_name="Sonar Pro"),
			LLMCatalogModel(model_id="perplexity:sonar", display_name="Sonar"),
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
