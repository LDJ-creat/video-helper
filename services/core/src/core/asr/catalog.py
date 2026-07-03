from __future__ import annotations

from dataclasses import dataclass

# Official X-Api-Resource-Id values from Volcengine doc 1354868 / 1631584.
OFFICIAL_VOLCENGINE_RESOURCES: tuple[tuple[str, str, str], ...] = (
	("volc.seedasr.auc", "豆包录音文件识别 2.0", "standard"),
	("volc.bigasr.auc", "豆包录音文件识别 1.0", "standard"),
	("volc.bigasr.auc_turbo", "豆包录音文件极速版", "flash"),
)


@dataclass(frozen=True)
class AsrCatalogModel:
	model_id: str
	display_name: str
	description: str | None = None


@dataclass(frozen=True)
class AsrCatalogProvider:
	provider_id: str
	display_name: str
	models: tuple[AsrCatalogModel, ...]
	notes: str | None = None
	supports_remote_models: bool = True


_PROVIDERS: tuple[AsrCatalogProvider, ...] = (
	AsrCatalogProvider(
		provider_id="dashscope",
		display_name="阿里云百炼 (DashScope)",
		models=(),
		notes="需将音频上传至临时 OSS 后异步识别；配置 API Key 后从上游拉取可用模型",
	),
	AsrCatalogProvider(
		provider_id="openai",
		display_name="OpenAI",
		models=(),
		notes="超长音频会先压缩为 mp3；仍超限则降级本地 faster-whisper",
	),
	AsrCatalogProvider(
		provider_id="volcengine",
		display_name="火山引擎 (豆包 ASR)",
		models=(),
		notes="新版控制台使用 X-Api-Key；旧版可存 app_id|access_token。标准版 submit 需 audio.url，极速版支持 base64",
	),
)


def list_asr_catalog_providers() -> tuple[AsrCatalogProvider, ...]:
	return _PROVIDERS


def find_asr_provider(provider_id: str) -> AsrCatalogProvider | None:
	pid = (provider_id or "").strip().lower()
	for provider in _PROVIDERS:
		if provider.provider_id == pid:
			return provider
	return None


def find_asr_model(provider_id: str, model_id: str) -> AsrCatalogModel | None:
	provider = find_asr_provider(provider_id)
	if provider is None:
		return None
	mid = (model_id or "").strip()
	for model in provider.models:
		if model.model_id == mid:
			return model
	# Volcengine resource IDs are documented enums.
	if provider.provider_id == "volcengine":
		for resource_id, display_name, _kind in OFFICIAL_VOLCENGINE_RESOURCES:
			if resource_id == mid:
				return AsrCatalogModel(model_id=resource_id, display_name=display_name)
	return None


def asr_model_exists(*, provider_id: str, model_id: str) -> bool:
	"""Known provider + non-empty model id (remote-listed or manual)."""

	mid = (model_id or "").strip()
	if not mid:
		return False
	return find_asr_provider(provider_id) is not None
