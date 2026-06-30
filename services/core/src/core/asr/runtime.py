from __future__ import annotations

import os
from dataclasses import dataclass

from sqlalchemy.orm import Session

from core.asr.catalog import find_asr_model, find_asr_provider
from core.db.repositories.asr_settings import get_asr_active, get_asr_provider_secret_ciphertext
from core.llm.secrets_crypto import decrypt_api_key


@dataclass(frozen=True)
class AsrRuntimeSettings:
	cloud_enabled: bool
	provider_id: str
	model_id: str
	language_hints: list[str]
	local_model_size: str
	local_device: str
	fallback_to_local: bool
	api_key: str | None
	configured: bool


def _env_bool(name: str, default: bool = False) -> bool:
	raw = (os.environ.get(name) or "").strip().lower()
	if raw in {"1", "true", "yes", "y", "on"}:
		return True
	if raw in {"0", "false", "no", "n", "off"}:
		return False
	return default


def _local_transcribe_settings() -> tuple[str, str]:
	return (
		(os.environ.get("TRANSCRIBE_MODEL_SIZE") or "base").strip() or "base",
		(os.environ.get("TRANSCRIBE_DEVICE") or "auto").strip() or "auto",
	)


def _env_api_key_for_provider(provider_id: str) -> str | None:
	pid = (provider_id or "").strip().lower()
	env_map = {
		"dashscope": "DASHSCOPE_API_KEY",
		"openai": "OPENAI_API_KEY",
		"volcengine": "VOLCENGINE_ASR_API_KEY",
	}
	key_name = env_map.get(pid)
	if not key_name:
		return None
	val = (os.environ.get(key_name) or "").strip()
	return val or None


def asr_runtime_for_jobs(session: Session | None = None) -> AsrRuntimeSettings:
	"""Resolve effective ASR settings: DB active + secret, then env fallback."""

	active: dict | None = None
	api_key: str | None = None
	if session is not None:
		active = get_asr_active(session)

	local_model_size, local_device = _local_transcribe_settings()

	if active is not None:
		provider_id = str(active.get("providerId") or "dashscope").strip().lower()
		model_id = str(active.get("modelId") or "paraformer-v2").strip()
		language_hints = active.get("languageHints")
		if not isinstance(language_hints, list):
			language_hints = ["zh", "en"]
		language_hints = [str(x).strip() for x in language_hints if str(x).strip()]
		ciphertext = get_asr_provider_secret_ciphertext(session, provider_id=provider_id) if session else None
		if ciphertext:
			try:
				api_key = decrypt_api_key(ciphertext)
			except Exception:
				api_key = None
		if not api_key:
			api_key = _env_api_key_for_provider(provider_id)
		return AsrRuntimeSettings(
			cloud_enabled=bool(active.get("cloudEnabled", True)),
			provider_id=provider_id,
			model_id=model_id,
			language_hints=language_hints or ["zh", "en"],
			local_model_size=local_model_size,
			local_device=local_device,
			fallback_to_local=bool(active.get("fallbackToLocal", True)),
			api_key=api_key,
			configured=True,
		)

	provider_id = (os.environ.get("ASR_PROVIDER_ID") or "dashscope").strip().lower()
	model_id = (os.environ.get("ASR_MODEL_ID") or "paraformer-v2").strip()
	api_key = _env_api_key_for_provider(provider_id)
	cloud_enabled = _env_bool("ASR_CLOUD_ENABLED", default=bool(api_key))
	language_raw = (os.environ.get("ASR_LANGUAGE_HINTS") or "zh,en").strip()
	language_hints = [p.strip() for p in language_raw.split(",") if p.strip()]
	return AsrRuntimeSettings(
		cloud_enabled=cloud_enabled,
		provider_id=provider_id,
		model_id=model_id,
		language_hints=language_hints or ["zh", "en"],
		local_model_size=local_model_size,
		local_device=local_device,
		fallback_to_local=_env_bool("ASR_FALLBACK_TO_LOCAL", default=True),
		api_key=api_key,
		configured=bool(api_key) and find_asr_provider(provider_id) is not None and find_asr_model(provider_id, model_id) is not None,
	)


def validate_asr_runtime(settings: AsrRuntimeSettings) -> str | None:
	if find_asr_provider(settings.provider_id) is None:
		return "unknown_provider"
	if find_asr_model(settings.provider_id, settings.model_id) is None:
		return "unknown_model"
	return None
