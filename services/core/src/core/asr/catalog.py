from __future__ import annotations

from dataclasses import dataclass


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


_PROVIDERS: tuple[AsrCatalogProvider, ...] = (
	AsrCatalogProvider(
		provider_id="dashscope",
		display_name="阿里云百炼 (DashScope)",
		models=(
			AsrCatalogModel("paraformer-v2", "Paraformer v2", "中文/多语录音文件识别，推荐"),
			AsrCatalogModel("paraformer-8k-v2", "Paraformer 8k v2", "8kHz 电话场景"),
		),
		notes="需将音频上传至临时 OSS 后异步识别",
	),
	AsrCatalogProvider(
		provider_id="openai",
		display_name="OpenAI",
		models=(
			AsrCatalogModel("whisper-1", "Whisper v2", "同步上传，单文件 ≤25MB"),
		),
		notes="超长音频会先压缩为 mp3；仍超限则降级本地 faster-whisper",
	),
	AsrCatalogProvider(
		provider_id="volcengine",
		display_name="火山引擎 (豆包 ASR)",
		models=(
			AsrCatalogModel("volc.seedasr.auc", "豆包录音识别 2.0", "推荐"),
			AsrCatalogModel("volc.bigasr.auc", "豆包录音识别 1.0", ""),
		),
		notes="新版控制台 X-Api-Key 鉴权，异步 submit + query",
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
	return None
