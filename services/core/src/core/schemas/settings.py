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
	baseUrl: str | None = None


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
	providerId: str | None = None
	displayName: str
	baseUrl: str
	modelId: str | None = None
	modelDisplayName: str | None = None


class UpdateCustomProviderRequestDTO(BaseModel):
	displayName: str | None = None
	baseUrl: str | None = None


class UpdateProviderProfileRequestDTO(BaseModel):
	displayName: str | None = None
	baseUrl: str | None = None


# ─── yt-dlp Cookies DTOs ────────────────────────────────────────────────────────


class YtdlpCookiesStatusDTO(BaseModel):
	hasFile: bool
	fileName: str | None = None
	updatedAtMs: int | None = None


# ─── ASR Prefetch DTOs ───────────────────────────────────────────────────────


class AsrPrefetchRequestDTO(BaseModel):
	modelSize: str | None = None


# ─── ASR Settings DTOs ───────────────────────────────────────────────────────


class AsrCatalogModelDTO(BaseModel):
	modelId: str
	displayName: str
	description: str | None = None


class AsrCatalogProviderDTO(BaseModel):
	providerId: str
	displayName: str
	hasKey: bool
	secretUpdatedAtMs: int | None = None
	models: list[AsrCatalogModelDTO]
	notes: str | None = None


class AsrCatalogDTO(BaseModel):
	providers: list[AsrCatalogProviderDTO]
	updatedAtMs: int


class PutAsrProviderSecretRequestDTO(BaseModel):
	apiKey: str


class AsrActiveDTO(BaseModel):
	configured: bool = True
	cloudEnabled: bool = True
	providerId: str | None = None
	modelId: str | None = None
	languageHints: list[str] = []
	localModelSize: str = "base"
	localDevice: str = "auto"
	fallbackToLocal: bool = True
	hasKey: bool = False
	updatedAtMs: int | None = None


class PutAsrActiveRequestDTO(BaseModel):
	cloudEnabled: bool = True
	providerId: str
	modelId: str
	languageHints: list[str] | None = None
	fallbackToLocal: bool = True


class AsrActiveTestDTO(BaseModel):
	ok: bool
	latencyMs: int
	mode: str | None = None
	message: str | None = None


class ProviderAsrTestRequestDTO(BaseModel):
	modelId: str
	languageHints: list[str] | None = None
