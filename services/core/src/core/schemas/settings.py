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
	isCustom: bool = False


class LLMCatalogProviderDTO(BaseModel):
	providerId: str
	displayName: str
	hasKey: bool
	secretUpdatedAtMs: int | None = None
	models: list[LLMCatalogModelDTO]
	isCustom: bool = False


class LLMCatalogDTO(BaseModel):
	providers: list[LLMCatalogProviderDTO]
	updatedAtMs: int


class LLMRemoteModelDTO(BaseModel):
	modelId: str
	displayName: str


class LLMRemoteModelsErrorDTO(BaseModel):
	code: str
	message: str


class LLMRemoteModelsDTO(BaseModel):
	ok: bool
	models: list[LLMRemoteModelDTO]
	error: LLMRemoteModelsErrorDTO | None = None


class PutLLMProviderSecretRequestDTO(BaseModel):
	apiKey: str


class LLMActiveDTO(BaseModel):
	configured: bool = True
	providerId: str | None = None
	modelId: str | None = None
	hasKey: bool = False
	updatedAtMs: int | None = None


class PutLLMActiveRequestDTO(BaseModel):
	providerId: str
	modelId: str


class LLMActiveTestDTO(BaseModel):
	ok: bool
	latencyMs: int


class ProviderLLMTestRequestDTO(BaseModel):
	modelId: str


# ─── Custom model DTOs ────────────────────────────────────────────────────────


class AddCustomModelRequestDTO(BaseModel):
	modelId: str
	displayName: str


# ─── Custom provider DTOs ─────────────────────────────────────────────────────


class AddCustomProviderRequestDTO(BaseModel):
	providerId: str
	displayName: str
	baseUrl: str
	modelId: str
	modelDisplayName: str


# ─── yt-dlp Cookies DTOs ────────────────────────────────────────────────────────


class YtdlpCookiesStatusDTO(BaseModel):
	hasFile: bool
	fileName: str | None = None
	updatedAtMs: int | None = None


# ─── ASR Prefetch DTOs ───────────────────────────────────────────────────────


class AsrPrefetchRequestDTO(BaseModel):
	modelSize: str | None = None
