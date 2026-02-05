from __future__ import annotations

from pydantic import BaseModel


class OkDTO(BaseModel):
	ok: bool


class AnalyzeSettingsDTO(BaseModel):
	provider: str
	baseUrl: str | None = None
	model: str | None = None
	timeoutS: int
	allowRulesFallback: bool
	debug: bool


class LLMCatalogModelDTO(BaseModel):
	modelId: str
	displayName: str


class LLMCatalogProviderDTO(BaseModel):
	providerId: str
	displayName: str
	hasKey: bool
	secretUpdatedAtMs: int | None = None
	models: list[LLMCatalogModelDTO]


class LLMCatalogDTO(BaseModel):
	providers: list[LLMCatalogProviderDTO]
	updatedAtMs: int


class PutLLMProviderSecretRequestDTO(BaseModel):
	apiKey: str


class LLMActiveDTO(BaseModel):
	providerId: str
	modelId: str
	hasKey: bool
	updatedAtMs: int


class PutLLMActiveRequestDTO(BaseModel):
	providerId: str
	modelId: str


class LLMActiveTestDTO(BaseModel):
	ok: bool
	latencyMs: int
