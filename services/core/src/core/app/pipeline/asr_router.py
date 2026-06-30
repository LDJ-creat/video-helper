from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from core.asr.runtime import AsrRuntimeSettings
from core.external.asr_faster_whisper import AsrError, AsrResult, transcribe_with_faster_whisper
from core.external.asr_providers.base import AsrCloudError, AsrCloudTimingsMs
from core.external.asr_providers.dashscope import transcribe_dashscope_paraformer
from core.external.asr_providers.openai_whisper import transcribe_openai_whisper
from core.external.asr_providers.volcengine import transcribe_volcengine_bigmodel


def _openai_language(language_hints: list[str]) -> str | None:
	if not language_hints:
		return None
	first = language_hints[0].strip().lower()
	if first in {"zh", "en", "ja", "ko", "de", "fr", "ru"}:
		return first
	return None


@dataclass
class AsrRouterResult:
	result: AsrResult
	asr_mode: str
	fallback_from: str | None
	fallback_reason: str | None
	timings_ms: dict[str, float] | None


def _local_transcribe(
	*,
	audio_path: Path,
	settings: AsrRuntimeSettings,
) -> AsrResult:
	return transcribe_with_faster_whisper(
		audio_path=audio_path,
		model_size=settings.local_model_size,
		device=settings.local_device,
	)


def _cloud_transcribe(
	*,
	audio_path: Path,
	settings: AsrRuntimeSettings,
	audio_duration_s: float | None,
	progress_cb: Callable[[str], None] | None,
) -> tuple[AsrResult, AsrCloudTimingsMs]:
	if not settings.api_key:
		raise AsrCloudError("missing_credentials", "cloud ASR API key not configured")

	pid = settings.provider_id
	if pid == "dashscope":
		return transcribe_dashscope_paraformer(
			audio_path=audio_path,
			api_key=settings.api_key,
			model=settings.model_id,
			language_hints=settings.language_hints,
			audio_duration_s=audio_duration_s,
			progress_cb=progress_cb,
		)
	if pid == "openai":
		return transcribe_openai_whisper(
			audio_path=audio_path,
			api_key=settings.api_key,
			model=settings.model_id,
			language=_openai_language(settings.language_hints),
			audio_duration_s=audio_duration_s,
			progress_cb=progress_cb,
		)
	if pid == "volcengine":
		return transcribe_volcengine_bigmodel(
			audio_path=audio_path,
			api_key=settings.api_key,
			resource_id=settings.model_id,
			language_hints=settings.language_hints,
			audio_duration_s=audio_duration_s,
			progress_cb=progress_cb,
		)
	raise AsrCloudError("unknown_provider", f"unknown cloud ASR provider: {pid}")


def transcribe_with_router(
	*,
	audio_path: Path,
	settings: AsrRuntimeSettings,
	audio_duration_s: float | None,
	progress_cb: Callable[[str], None] | None = None,
	log_cb: Callable[[str], None] | None = None,
) -> AsrRouterResult:
	use_cloud = bool(settings.cloud_enabled and settings.api_key)

	if not use_cloud:
		if progress_cb:
			progress_cb("asr=starting provider=faster-whisper mode=local")
		result = _local_transcribe(audio_path=audio_path, settings=settings)
		return AsrRouterResult(
			result=result,
			asr_mode="local",
			fallback_from=None,
			fallback_reason=None,
			timings_ms=None,
		)

	if progress_cb:
		progress_cb(f"asr=starting provider={settings.provider_id} mode=cloud")

	try:
		result, cloud_timings = _cloud_transcribe(
			audio_path=audio_path,
			settings=settings,
			audio_duration_s=audio_duration_s,
			progress_cb=progress_cb,
		)
		return AsrRouterResult(
			result=result,
			asr_mode="cloud",
			fallback_from=None,
			fallback_reason=None,
			timings_ms={
				"upload": cloud_timings.upload_ms,
				"submit": cloud_timings.submit_ms,
				"wait": cloud_timings.wait_ms,
				"download": cloud_timings.download_ms,
				"total": cloud_timings.total_ms,
			},
		)
	except AsrCloudError as exc:
		if not settings.fallback_to_local or not exc.fallback_eligible:
			raise
		reason = exc.kind
		msg = f"asr_fallback provider={settings.provider_id} reason={reason} message={exc}"
		if log_cb:
			log_cb(msg)
		if progress_cb:
			progress_cb(f"asr=fallback local reason={reason}")
		try:
			result = _local_transcribe(audio_path=audio_path, settings=settings)
		except AsrError:
			raise exc
		return AsrRouterResult(
			result=result,
			asr_mode="local",
			fallback_from=settings.provider_id,
			fallback_reason=reason,
			timings_ms=None,
		)
