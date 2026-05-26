from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


ListingKind = Literal["openai_compat", "anthropic", "gemini"]


@dataclass(frozen=True)
class LLMCatalogModel:
	model_id: str
	display_name: str


@dataclass(frozen=True)
class LLMCatalogProvider:
	provider_id: str
	display_name: str
	base_url: str
	listing_kind: ListingKind


_PROVIDERS: tuple[LLMCatalogProvider, ...] = (
	LLMCatalogProvider(
		provider_id="anthropic",
		display_name="Anthropic",
		base_url="https://api.anthropic.com",
		listing_kind="anthropic",
	),
	LLMCatalogProvider(
		provider_id="openrouter",
		display_name="OpenRouter",
		base_url="https://openrouter.ai/api/v1",
		listing_kind="openai_compat",
	),
	LLMCatalogProvider(
		provider_id="openai",
		display_name="OpenAI",
		base_url="https://api.openai.com/v1",
		listing_kind="openai_compat",
	),
	LLMCatalogProvider(
		provider_id="google",
		display_name="Google Gemini",
		base_url="https://generativelanguage.googleapis.com/v1beta",
		listing_kind="gemini",
	),
	LLMCatalogProvider(
		provider_id="qwen",
		display_name="阿里百炼",
		base_url="https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
		listing_kind="openai_compat",
	),
	LLMCatalogProvider(
		provider_id="nvidia",
		display_name="NVIDIA NIM",
		base_url="https://integrate.api.nvidia.com/v1/chat/completions",
		listing_kind="openai_compat",
	),
	LLMCatalogProvider(
		provider_id="deepseek",
		display_name="DeepSeek",
		base_url="https://api.deepseek.com/v1",
		listing_kind="openai_compat",
	),
	LLMCatalogProvider(
		provider_id="xai",
		display_name="xAI Grok",
		base_url="https://api.x.ai/v1",
		listing_kind="openai_compat",
	),
	LLMCatalogProvider(
		provider_id="zhipu",
		display_name="Z.ai(智谱AI)",
		base_url="https://open.bigmodel.cn/api/paas/v4",
		listing_kind="openai_compat",
	),
	LLMCatalogProvider(
		provider_id="minimax",
		display_name="MiniMax",
		base_url="https://api.minimaxi.com/v1",
		listing_kind="openai_compat",
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


def openai_compat_models_list_url(base_url: str) -> str:
	"""Derive ``GET .../models`` URL from a chat-completions style or ``/v1`` root ``base_url``."""

	u = (base_url or "").strip().rstrip("/")
	if not u:
		return ""
	lower = u.lower()
	if lower.endswith("/v1/chat/completions"):
		u = u[: -len("/chat/completions")].rstrip("/")
		lower = u.lower()
	elif lower.endswith("/chat/completions"):
		u = u[: -len("/chat/completions")].rstrip("/")
		lower = u.lower()
	if lower.endswith("/v1/responses"):
		u = u[: -len("/responses")].rstrip("/")
		lower = u.lower()
	if lower.endswith("/models"):
		return u
	return f"{u}/models"


def anthropic_models_list_url(base_url: str) -> str:
	u = (base_url or "").strip().rstrip("/")
	if not u:
		return ""
	lower = u.lower()
	if lower.endswith("/v1/models"):
		return u
	if lower.endswith("/v1"):
		return f"{u}/models"
	return f"{u}/v1/models"


def gemini_models_list_url(base_url: str) -> str:
	u = (base_url or "").strip().rstrip("/")
	if not u:
		return ""
	lower = u.lower()
	if lower.endswith("/models"):
		return u
	return f"{u}/models"


def model_exists(*, provider_id: str, model_id: str) -> bool:
	"""Static catalog no longer enumerates models; always False (custom models live in DB)."""

	_ = (provider_id, model_id)
	return False


def resolve_runtime_model_name(*, provider_id: str, model_id: str) -> str | None:
	"""Map stored ``modelId`` to the provider runtime ``model`` string.

	Legacy: ``providerId:modelName`` uses the segment after the first colon as the runtime id.
	Otherwise the full ``model_id`` is used when the provider exists in the static catalog.
	"""

	p = find_provider(provider_id)
	if p is None:
		return None
	mid = (model_id or "").strip()
	if not mid:
		return None
	if ":" in mid:
		_, name = mid.split(":", 1)
		name = name.strip()
		return name or None
	return mid

