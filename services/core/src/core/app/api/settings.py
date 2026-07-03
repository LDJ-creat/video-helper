from __future__ import annotations

import os
import time
import logging
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from core.contracts.error_codes import ErrorCode
from core.contracts.error_envelope import build_error_envelope
from core.llm.catalog import list_llm_catalog_providers, LLMCatalogProvider
from core.llm.catalog import find_provider
from core.llm.catalog import resolve_runtime_model_name
from core.db.repositories.llm_settings import (
	get_llm_provider_secret_meta,
	delete_llm_provider_secret,
	upsert_llm_provider_secret_ciphertext,
	get_llm_active,
	set_llm_active,
	get_llm_provider_secret_ciphertext,
	list_custom_models,
	add_custom_model,
	delete_custom_model,
	list_custom_providers,
	get_custom_provider,
	add_custom_provider,
	update_custom_provider,
	delete_custom_provider,
	upsert_provider_override,
)
from core.db.session import get_db_session
from core.llm.active_test import LLMActiveTestError, run_llm_connectivity_test
from core.llm.remote_model_list import fetch_remote_models_for_provider
from core.llm.secrets_crypto import decrypt_api_key, encrypt_api_key
from core.schemas.settings import (
	AnalyzeSettingsDTO,
	LLMCatalogDTO,
	LLMCatalogModelDTO,
	LLMCatalogProviderDTO,
	LLMRemoteModelDTO,
	LLMRemoteModelsDTO,
	LLMRemoteModelsErrorDTO,
	LLMActiveDTO,
	LLMActiveTestDTO,
	ProviderLLMTestRequestDTO,
	AsrPrefetchRequestDTO,
	AsrCatalogDTO,
	AsrCatalogModelDTO,
	AsrCatalogProviderDTO,
	AsrRemoteModelsDTO,
	AsrRemoteModelDTO,
	AsrRemoteModelsErrorDTO,
	AddCustomAsrModelRequestDTO,
	AsrActiveDTO,
	PutAsrActiveRequestDTO,
	PutAsrProviderSecretRequestDTO,
	AsrActiveTestDTO,
	ProviderAsrTestRequestDTO,
	OkDTO,
	PutLLMActiveRequestDTO,
	PutLLMProviderSecretRequestDTO,
	AddCustomModelRequestDTO,
	AddCustomProviderRequestDTO,
	UpdateCustomProviderRequestDTO,
	UpdateProviderProfileRequestDTO,
	YtdlpCookiesStatusDTO,
)
from core.llm.provider_profile import resolve_builtin_provider
from core.settings import get_effective_analyze_settings
from core.db.session import get_data_dir

from core.external.asr_faster_whisper import AsrError, prefetch_faster_whisper_model
from core.asr.catalog import asr_model_exists, find_asr_provider, list_asr_catalog_providers
from core.asr.remote_model_list import fetch_remote_asr_models_for_provider
from core.asr.runtime import AsrRuntimeSettings, _local_transcribe_settings, asr_runtime_for_jobs, validate_asr_runtime
from core.asr.active_test import AsrActiveTestError, run_asr_connectivity_test
from core.db.repositories.asr_settings import (
	add_custom_asr_model,
	delete_asr_provider_secret,
	delete_custom_asr_model,
	get_asr_active,
	get_asr_provider_secret_ciphertext,
	get_asr_provider_secret_meta,
	list_custom_asr_models,
	set_asr_active,
	upsert_asr_provider_secret_ciphertext,
)


router = APIRouter(tags=["settings"])

logger = logging.getLogger(__name__)


def _now_ms() -> int:
	return int(time.time() * 1000)


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _build_merged_catalog(session: Session) -> list[LLMCatalogProviderDTO]:
	"""Merge static catalog providers with DB-stored custom models / custom providers."""

	# --- Static providers merged with custom models ---
	static_providers = list_llm_catalog_providers()
	custom_providers_raw = list_custom_providers(session)

	# Build a set of static provider_ids for conflict detection.
	static_ids = {p.provider_id for p in static_providers}

	result: list[LLMCatalogProviderDTO] = []

	for p in static_providers:
		meta = get_llm_provider_secret_meta(session, provider_id=p.provider_id)
		has_key = bool(meta.get("hasKey")) if isinstance(meta, dict) else False
		secret_updated_at_ms = meta.get("secretUpdatedAtMs") if isinstance(meta, dict) else None
		if not isinstance(secret_updated_at_ms, int):
			secret_updated_at_ms = None

		resolved = resolve_builtin_provider(session, provider_id=p.provider_id) or {
			"displayName": p.display_name,
			"baseUrl": p.base_url,
		}

		# Custom models only (built-in model list comes from remote-models API).
		models: list[LLMCatalogModelDTO] = []
		custom_models = list_custom_models(session, provider_id=p.provider_id)
		for cm in custom_models:
			models.append(
				LLMCatalogModelDTO(
					modelId=cm["modelId"],
					displayName=cm["displayName"],
					isCustom=True,
				)
			)

		result.append(
			LLMCatalogProviderDTO(
				providerId=p.provider_id,
				displayName=str(resolved.get("displayName") or p.display_name),
				hasKey=has_key,
				secretUpdatedAtMs=secret_updated_at_ms,
				models=models,
				isCustom=False,
				baseUrl=str(resolved.get("baseUrl") or p.base_url),
			)
		)

	# --- Fully custom providers (not in static catalog) ---
	for cp in custom_providers_raw:
		pid = cp["providerId"]
		if pid in static_ids:
			continue  # Conflict with static; skip (static takes precedence).

		meta = get_llm_provider_secret_meta(session, provider_id=pid)
		has_key = bool(meta.get("hasKey")) if isinstance(meta, dict) else False
		secret_updated_at_ms = meta.get("secretUpdatedAtMs") if isinstance(meta, dict) else None
		if not isinstance(secret_updated_at_ms, int):
			secret_updated_at_ms = None

		custom_models = list_custom_models(session, provider_id=pid)
		models = [
			LLMCatalogModelDTO(
				modelId=cm["modelId"],
				displayName=cm["displayName"],
				isCustom=True,
			)
			for cm in custom_models
		]

		result.append(
			LLMCatalogProviderDTO(
				providerId=pid,
				displayName=cp["displayName"],
				hasKey=has_key,
				secretUpdatedAtMs=secret_updated_at_ms,
				models=models,
				isCustom=True,
				baseUrl=cp.get("baseUrl"),
			)
		)

	return result


def _find_provider_merged(provider_id: str, session: Session) -> LLMCatalogProvider | dict | None:
	"""Find a provider from static catalog or custom providers table."""
	static = find_provider(provider_id)
	if static is not None:
		return static
	return get_custom_provider(session, provider_id=provider_id)


def _model_exists_merged(*, provider_id: str, model_id: str, session: Session) -> bool:
	"""Known provider + non-empty model id (remote-listed or manual)."""

	mid = (model_id or "").strip()
	if not mid:
		return False
	return _find_provider_merged(provider_id, session) is not None


def _resolve_runtime_model_merged(*, provider_id: str, model_id: str, session: Session) -> str | None:
	"""Resolve the runtime model name for static or custom providers."""

	static = find_provider(provider_id)
	if static is not None:
		return resolve_runtime_model_name(provider_id=static.provider_id, model_id=model_id)

	cp = get_custom_provider(session, provider_id=provider_id)
	if cp is None:
		return None
	mid = (model_id or "").strip()
	if not mid:
		return None
	if ":" in mid:
		_, name = mid.split(":", 1)
		name = name.strip()
		return name or None
	return mid


def _get_provider_base_url(provider_id: str, session: Session) -> str | None:
	"""Get base_url from static catalog (with overrides), or custom providers."""
	from core.llm.provider_profile import get_resolved_builtin_base_url

	resolved = get_resolved_builtin_base_url(session, provider_id=provider_id)
	if resolved:
		return resolved
	cp = get_custom_provider(session, provider_id=provider_id)
	if cp is not None:
		return cp.get("baseUrl")
	return None


# ─── Analyze settings ─────────────────────────────────────────────────────────


@router.get("/settings/analyze", response_model=AnalyzeSettingsDTO)
def get_analyze_settings(request: Request):
	settings = get_effective_analyze_settings()
	return AnalyzeSettingsDTO(**settings.to_public_payload())


# ─── Catalog ──────────────────────────────────────────────────────────────────


@router.get("/settings/llm/catalog", response_model=LLMCatalogDTO)
def get_llm_catalog(_: Request, session: Session = Depends(get_db_session)):
	providers = _build_merged_catalog(session)
	return LLMCatalogDTO(providers=providers, updatedAtMs=_now_ms())


def _remote_models_error_dto(code: str) -> LLMRemoteModelsErrorDTO:
	msgs: dict[str, str] = {
		"missing_credentials": "Save an API key for this provider first.",
		"invalid_credentials": "The stored API key could not be decrypted or was rejected.",
		"invalid_base_url": "Provider base URL is missing or invalid.",
		"missing_api_key": "No API key available for this provider.",
		"invalid_api_key": "API key contains characters that cannot be sent in HTTP headers. Check for extra spaces or non-ASCII text.",
		"provider_unavailable": "Could not reach the provider to list models.",
		"list_models_failed": "The provider rejected the models list request.",
		"invalid_response": "Unexpected response when listing models.",
		"unknown_provider": "Unknown provider.",
	}
	return LLMRemoteModelsErrorDTO(code=code, message=msgs.get(code, code))


@router.get("/settings/llm/providers/{provider_id}/remote-models", response_model=LLMRemoteModelsDTO)
def get_llm_remote_models(
	provider_id: str,
	_: Request,
	session: Session = Depends(get_db_session),
):
	"""List models from the upstream provider using the saved API key (server-side only)."""

	pid = (provider_id or "").strip().lower()
	provider = _find_provider_merged(pid, session)
	if provider is None:
		return LLMRemoteModelsDTO(ok=False, models=[], error=_remote_models_error_dto("unknown_provider"))

	ciphertext = get_llm_provider_secret_ciphertext(session, provider_id=pid)
	if not ciphertext:
		return LLMRemoteModelsDTO(ok=False, models=[], error=_remote_models_error_dto("missing_credentials"))

	try:
		api_key = decrypt_api_key(ciphertext)
	except Exception:
		return LLMRemoteModelsDTO(ok=False, models=[], error=_remote_models_error_dto("invalid_credentials"))

	base_url = _get_provider_base_url(pid, session)
	if not (base_url or "").strip():
		return LLMRemoteModelsDTO(ok=False, models=[], error=_remote_models_error_dto("invalid_base_url"))

	items, err = fetch_remote_models_for_provider(provider=provider, base_url=str(base_url), api_key=api_key)
	if err:
		return LLMRemoteModelsDTO(ok=False, models=[], error=_remote_models_error_dto(err))

	return LLMRemoteModelsDTO(
		ok=True,
		models=[LLMRemoteModelDTO(modelId=i.model_id, displayName=i.display_name) for i in items],
		error=None,
	)


# ─── Provider secrets ─────────────────────────────────────────────────────────


@router.put("/settings/llm/providers/{provider_id}/secret", response_model=OkDTO)
def put_llm_provider_secret(
	provider_id: str,
	body: PutLLMProviderSecretRequestDTO,
	request: Request,
	session: Session = Depends(get_db_session),
):
	provider = _find_provider_merged(provider_id, session)
	if provider is None:
		return JSONResponse(
			status_code=400,
			content=build_error_envelope(
				code=ErrorCode.VALIDATION_ERROR,
				message="Unknown provider",
				details={"reason": "unknown_provider", "providerId": provider_id},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	api_key = (body.apiKey or "").strip()
	if not api_key:
		return JSONResponse(
			status_code=400,
			content=build_error_envelope(
				code=ErrorCode.VALIDATION_ERROR,
				message="Invalid request",
				details={"reason": "invalid_api_key"},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	pid = provider_id.strip().lower()
	ciphertext = encrypt_api_key(api_key)
	upsert_llm_provider_secret_ciphertext(session, provider_id=pid, ciphertext_b64=ciphertext, now_ms=_now_ms())
	session.commit()
	return OkDTO(ok=True)


@router.delete("/settings/llm/providers/{provider_id}/secret", response_model=OkDTO)
def delete_llm_provider_secret_api(
	provider_id: str,
	request: Request,
	session: Session = Depends(get_db_session),
):
	provider = _find_provider_merged(provider_id, session)
	if provider is None:
		return JSONResponse(
			status_code=400,
			content=build_error_envelope(
				code=ErrorCode.VALIDATION_ERROR,
				message="Unknown provider",
				details={"reason": "unknown_provider", "providerId": provider_id},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	pid = provider_id.strip().lower()
	_ = delete_llm_provider_secret(session, provider_id=pid)
	session.commit()
	return OkDTO(ok=True)


# ─── Active selection ─────────────────────────────────────────────────────────


@router.get("/settings/llm/active", response_model=LLMActiveDTO)
def get_llm_active_api(request: Request, session: Session = Depends(get_db_session)):
	active = get_llm_active(session)
	if active is None:
		return LLMActiveDTO(configured=False, providerId=None, modelId=None, hasKey=False, updatedAtMs=None)

	provider_id = str(active.get("providerId") or "").strip()
	model_id = str(active.get("modelId") or "").strip()
	updated_at_ms = int(active.get("updatedAtMs") or 0)

	if not provider_id and not model_id:
		return LLMActiveDTO(configured=False, providerId=None, modelId=None, hasKey=False, updatedAtMs=None)

	meta = get_llm_provider_secret_meta(session, provider_id=provider_id)
	has_key = bool(meta.get("hasKey")) if isinstance(meta, dict) else False

	return LLMActiveDTO(
		configured=True,
		providerId=provider_id,
		modelId=model_id,
		hasKey=has_key,
		updatedAtMs=updated_at_ms,
	)


@router.put("/settings/llm/active", response_model=OkDTO)
def put_llm_active_api(
	body: PutLLMActiveRequestDTO,
	request: Request,
	session: Session = Depends(get_db_session),
):
	provider_id = (body.providerId or "").strip().lower()
	model_id = (body.modelId or "").strip()

	provider = _find_provider_merged(provider_id, session)
	if provider is None:
		return JSONResponse(
			status_code=400,
			content=build_error_envelope(
				code=ErrorCode.VALIDATION_ERROR,
				message="Unknown provider",
				details={"reason": "unknown_provider", "providerId": body.providerId},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	if not _model_exists_merged(provider_id=provider_id, model_id=model_id, session=session):
		return JSONResponse(
			status_code=400,
			content=build_error_envelope(
				code=ErrorCode.VALIDATION_ERROR,
				message="Model not found",
				details={"reason": "model_not_found", "providerId": provider_id, "modelId": body.modelId},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	set_llm_active(session, provider_id=provider_id, model_id=model_id, now_ms=_now_ms())
	session.commit()
	return OkDTO(ok=True)


# ─── LLM connectivity test ───────────────────────────────────────────────────


def _llm_connectivity_test_response(
	*,
	request: Request,
	session: Session,
	provider_id: str,
	model_id: str,
	log_prefix: str = "llm-test",
) -> LLMActiveTestDTO | JSONResponse:
	import time as _time

	_t0 = _time.perf_counter()
	provider_id = str(provider_id or "").strip().lower()
	model_id = str(model_id or "").strip()
	if not provider_id or not model_id:
		return JSONResponse(
			status_code=400,
			content=build_error_envelope(
				code=ErrorCode.VALIDATION_ERROR,
				message="LLM is not configured",
				details={"reason": "llm_not_configured"},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	provider = _find_provider_merged(provider_id, session)
	_t1 = _time.perf_counter()
	logger.info("%s breakdown: _find_provider_merged %.1f ms", log_prefix, (_t1 - _t0) * 1000)
	if provider is None:
		return JSONResponse(
			status_code=400,
			content=build_error_envelope(
				code=ErrorCode.VALIDATION_ERROR,
				message="Unknown provider",
				details={"reason": "unknown_provider", "providerId": provider_id},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	if not _model_exists_merged(provider_id=provider_id, model_id=model_id, session=session):
		return JSONResponse(
			status_code=400,
			content=build_error_envelope(
				code=ErrorCode.VALIDATION_ERROR,
				message="Model not found",
				details={"reason": "model_not_found", "providerId": provider_id, "modelId": model_id},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	ciphertext = get_llm_provider_secret_ciphertext(session, provider_id=provider_id)
	if not ciphertext:
		return JSONResponse(
			status_code=400,
			content=build_error_envelope(
				code=ErrorCode.VALIDATION_ERROR,
				message="Missing credentials",
				details={"reason": "missing_credentials"},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	try:
		api_key = decrypt_api_key(ciphertext)
	except Exception:
		return JSONResponse(
			status_code=400,
			content=build_error_envelope(
				code=ErrorCode.VALIDATION_ERROR,
				message="Invalid credentials",
				details={"reason": "invalid_credentials"},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	runtime_model = _resolve_runtime_model_merged(provider_id=provider_id, model_id=model_id, session=session)
	if not runtime_model:
		return JSONResponse(
			status_code=400,
			content=build_error_envelope(
				code=ErrorCode.VALIDATION_ERROR,
				message="Model not found",
				details={"reason": "model_not_found", "providerId": provider_id, "modelId": model_id},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	base_url = _get_provider_base_url(provider_id, session)
	if not base_url:
		return JSONResponse(
			status_code=400,
			content=build_error_envelope(
				code=ErrorCode.VALIDATION_ERROR,
				message="Provider base URL not configured",
				details={"reason": "missing_base_url"},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	_t_pre = _time.perf_counter()
	logger.info("%s breakdown: pre-flight %.1f ms, starting connectivity test", log_prefix, (_t_pre - _t0) * 1000)
	try:
		latency_ms = run_llm_connectivity_test(
			base_url=base_url,
			api_key=api_key,
			model=runtime_model,
		)
	except LLMActiveTestError as e:
		status = 400 if e.reason in {"invalid_credentials", "model_not_found", "invalid_api_key"} else 503
		msg = {
			"invalid_credentials": "Invalid credentials",
			"invalid_api_key": "API key contains invalid characters",
			"model_not_found": "Model not found",
			"provider_unavailable": "Provider unavailable",
		}.get(e.reason, "Provider unavailable")
		return JSONResponse(
			status_code=status,
			content=build_error_envelope(
				code=ErrorCode.VALIDATION_ERROR,
				message=msg,
				details={"reason": e.reason},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	logger.info("%s breakdown: OK latency_ms=%s", log_prefix, latency_ms)
	return LLMActiveTestDTO(ok=True, latencyMs=int(latency_ms))


@router.post("/settings/llm/active/test", response_model=LLMActiveTestDTO)
def post_llm_active_test(request: Request, session: Session = Depends(get_db_session)):
	active = get_llm_active(session)
	if active is None:
		return JSONResponse(
			status_code=400,
			content=build_error_envelope(
				code=ErrorCode.VALIDATION_ERROR,
				message="LLM is not configured",
				details={"reason": "llm_not_configured"},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	provider_id = str(active.get("providerId") or "").strip()
	model_id = str(active.get("modelId") or "").strip()
	return _llm_connectivity_test_response(
		request=request,
		session=session,
		provider_id=provider_id,
		model_id=model_id,
		log_prefix="active-test",
	)


@router.post("/settings/llm/providers/{provider_id}/test", response_model=LLMActiveTestDTO)
def post_llm_provider_test(
	provider_id: str,
	body: ProviderLLMTestRequestDTO,
	request: Request,
	session: Session = Depends(get_db_session),
):
	return _llm_connectivity_test_response(
		request=request,
		session=session,
		provider_id=provider_id,
		model_id=body.modelId,
		log_prefix=f"provider-test:{provider_id}",
	)


# ─── Custom models ────────────────────────────────────────────────────────────


@router.post("/settings/llm/providers/{provider_id}/models", response_model=OkDTO)
def add_custom_model_api(
	provider_id: str,
	body: AddCustomModelRequestDTO,
	request: Request,
	session: Session = Depends(get_db_session),
):
	"""Add a custom model ID to an existing (or custom) provider."""
	provider = _find_provider_merged(provider_id, session)
	if provider is None:
		return JSONResponse(
			status_code=400,
			content=build_error_envelope(
				code=ErrorCode.VALIDATION_ERROR,
				message="Unknown provider",
				details={"reason": "unknown_provider", "providerId": provider_id},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	model_id = (body.modelId or "").strip()
	display_name = (body.displayName or "").strip()

	if not model_id:
		return JSONResponse(
			status_code=400,
			content=build_error_envelope(
				code=ErrorCode.VALIDATION_ERROR,
				message="modelId is required",
				details={"reason": "missing_model_id"},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	if not display_name:
		display_name = model_id

	custom_existing = list_custom_models(session, provider_id=provider_id.strip().lower())
	if any(c["modelId"] == model_id for c in custom_existing):
		return JSONResponse(
			status_code=400,
			content=build_error_envelope(
				code=ErrorCode.VALIDATION_ERROR,
				message="Model already exists",
				details={"reason": "model_already_exists", "modelId": model_id},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	add_custom_model(
		session,
		provider_id=provider_id.strip().lower(),
		model_id=model_id,
		display_name=display_name,
		now_ms=_now_ms(),
	)
	session.commit()
	return OkDTO(ok=True)


@router.delete("/settings/llm/providers/{provider_id}/models/{model_id:path}", response_model=OkDTO)
def delete_custom_model_api(
	provider_id: str,
	model_id: str,
	request: Request,
	session: Session = Depends(get_db_session),
):
	"""Delete a custom model ID from a provider. Cannot delete static catalog models."""
	deleted = delete_custom_model(session, provider_id=provider_id.strip().lower(), model_id=model_id.strip())
	if not deleted:
		return JSONResponse(
			status_code=404,
			content=build_error_envelope(
				code=ErrorCode.VALIDATION_ERROR,
				message="Custom model not found",
				details={"reason": "model_not_found", "providerId": provider_id, "modelId": model_id},
				request_id=getattr(request.state, "request_id", None),
			),
		)
	session.commit()
	return OkDTO(ok=True)


# ─── Custom providers ─────────────────────────────────────────────────────────


@router.post("/settings/llm/custom-providers", response_model=OkDTO)
def add_custom_provider_api(
	body: AddCustomProviderRequestDTO,
	request: Request,
	session: Session = Depends(get_db_session),
):
	"""Add a fully custom provider (display_name, base_url), optionally with an initial model."""
	display_name = (body.displayName or "").strip()
	provider_id = (body.providerId or display_name).strip().lower()
	base_url = (body.baseUrl or "").strip()
	model_id = (body.modelId or "").strip()
	model_display_name = (body.modelDisplayName or "").strip() or model_id

	# Validate fields.
	if not provider_id:
		return JSONResponse(
			status_code=400,
			content=build_error_envelope(
				code=ErrorCode.VALIDATION_ERROR,
				message="displayName is required",
				details={"reason": "missing_display_name"},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	if not display_name:
		return JSONResponse(
			status_code=400,
			content=build_error_envelope(
				code=ErrorCode.VALIDATION_ERROR,
				message="displayName is required",
				details={"reason": "missing_display_name"},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	# Validate base_url.
	try:
		p = urlparse(base_url)
		if (p.scheme or "").lower() not in {"http", "https"} or not p.netloc:
			raise ValueError("bad url")
	except Exception:
		return JSONResponse(
			status_code=400,
			content=build_error_envelope(
				code=ErrorCode.VALIDATION_ERROR,
				message="baseUrl must be a valid http/https URL",
				details={"reason": "invalid_base_url"},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	# Disallow overriding static providers.
	if find_provider(provider_id) is not None:
		return JSONResponse(
			status_code=400,
			content=build_error_envelope(
				code=ErrorCode.VALIDATION_ERROR,
				message="Provider already exists in static catalog",
				details={"reason": "provider_already_exists", "providerId": provider_id},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	if get_custom_provider(session, provider_id=provider_id) is not None:
		return JSONResponse(
			status_code=400,
			content=build_error_envelope(
				code=ErrorCode.VALIDATION_ERROR,
				message="Custom provider already exists",
				details={"reason": "provider_already_exists", "providerId": provider_id},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	add_custom_provider(
		session,
		provider_id=provider_id,
		display_name=display_name,
		base_url=base_url,
		now_ms=_now_ms(),
	)
	if model_id:
		add_custom_model(
			session,
			provider_id=provider_id,
			model_id=model_id,
			display_name=model_display_name,
			now_ms=_now_ms(),
		)
	session.commit()
	return OkDTO(ok=True)


@router.put("/settings/llm/providers/{provider_id}/profile", response_model=OkDTO)
def update_provider_profile_api(
	provider_id: str,
	body: UpdateProviderProfileRequestDTO,
	request: Request,
	session: Session = Depends(get_db_session),
):
	"""Update display name and/or base URL for a built-in catalog provider."""
	pid = (provider_id or "").strip().lower()
	static = find_provider(pid)
	if static is None:
		return JSONResponse(
			status_code=400,
			content=build_error_envelope(
				code=ErrorCode.VALIDATION_ERROR,
				message="Built-in provider not found",
				details={"reason": "provider_is_not_builtin", "providerId": pid},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	display_name = (body.displayName or "").strip() if body.displayName is not None else None
	base_url = (body.baseUrl or "").strip() if body.baseUrl is not None else None

	if display_name is None and base_url is None:
		return JSONResponse(
			status_code=400,
			content=build_error_envelope(
				code=ErrorCode.VALIDATION_ERROR,
				message="At least one of displayName or baseUrl is required",
				details={"reason": "missing_update_fields"},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	if display_name is not None and not display_name:
		return JSONResponse(
			status_code=400,
			content=build_error_envelope(
				code=ErrorCode.VALIDATION_ERROR,
				message="displayName cannot be empty",
				details={"reason": "missing_display_name"},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	if base_url is not None:
		try:
			p = urlparse(base_url)
			if (p.scheme or "").lower() not in {"http", "https"} or not p.netloc:
				raise ValueError("bad url")
		except Exception:
			return JSONResponse(
				status_code=400,
				content=build_error_envelope(
					code=ErrorCode.VALIDATION_ERROR,
					message="baseUrl must be a valid http/https URL",
					details={"reason": "invalid_base_url"},
					request_id=getattr(request.state, "request_id", None),
				),
			)

	upsert_provider_override(
		session,
		provider_id=pid,
		display_name=display_name,
		base_url=base_url,
		now_ms=_now_ms(),
	)
	session.commit()
	return OkDTO(ok=True)


@router.put("/settings/llm/custom-providers/{provider_id}", response_model=OkDTO)
def update_custom_provider_api(
	provider_id: str,
	body: UpdateCustomProviderRequestDTO,
	request: Request,
	session: Session = Depends(get_db_session),
):
	"""Update display name and/or base URL of a custom provider."""
	pid = (provider_id or "").strip().lower()
	if find_provider(pid) is not None:
		return JSONResponse(
			status_code=400,
			content=build_error_envelope(
				code=ErrorCode.VALIDATION_ERROR,
				message="Cannot update a built-in catalog provider",
				details={"reason": "provider_is_static", "providerId": pid},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	display_name = (body.displayName or "").strip() if body.displayName is not None else None
	base_url = (body.baseUrl or "").strip() if body.baseUrl is not None else None

	if display_name is None and base_url is None:
		return JSONResponse(
			status_code=400,
			content=build_error_envelope(
				code=ErrorCode.VALIDATION_ERROR,
				message="At least one of displayName or baseUrl is required",
				details={"reason": "missing_update_fields"},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	if display_name is not None and not display_name:
		return JSONResponse(
			status_code=400,
			content=build_error_envelope(
				code=ErrorCode.VALIDATION_ERROR,
				message="displayName cannot be empty",
				details={"reason": "missing_display_name"},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	if base_url is not None:
		try:
			p = urlparse(base_url)
			if (p.scheme or "").lower() not in {"http", "https"} or not p.netloc:
				raise ValueError("bad url")
		except Exception:
			return JSONResponse(
				status_code=400,
				content=build_error_envelope(
					code=ErrorCode.VALIDATION_ERROR,
					message="baseUrl must be a valid http/https URL",
					details={"reason": "invalid_base_url"},
					request_id=getattr(request.state, "request_id", None),
				),
			)

	updated = update_custom_provider(
		session,
		provider_id=pid,
		display_name=display_name,
		base_url=base_url,
		now_ms=_now_ms(),
	)
	if not updated:
		return JSONResponse(
			status_code=404,
			content=build_error_envelope(
				code=ErrorCode.VALIDATION_ERROR,
				message="Custom provider not found",
				details={"reason": "unknown_provider", "providerId": pid},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	session.commit()
	return OkDTO(ok=True)


@router.delete("/settings/llm/custom-providers/{provider_id}", response_model=OkDTO)
def delete_custom_provider_api(
	provider_id: str,
	request: Request,
	session: Session = Depends(get_db_session),
):
	"""Delete a custom provider and all its custom models."""
	# Protect against accidental deletion of static providers.
	if find_provider(provider_id) is not None:
		return JSONResponse(
			status_code=400,
			content=build_error_envelope(
				code=ErrorCode.VALIDATION_ERROR,
				message="Cannot delete a built-in catalog provider",
				details={"reason": "provider_is_static", "providerId": provider_id},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	deleted = delete_custom_provider(session, provider_id=provider_id.strip().lower())
	if not deleted:
		return JSONResponse(
			status_code=404,
			content=build_error_envelope(
				code=ErrorCode.VALIDATION_ERROR,
				message="Custom provider not found",
				details={"reason": "unknown_provider", "providerId": provider_id},
				request_id=getattr(request.state, "request_id", None),
			),
		)
	session.commit()
	return OkDTO(ok=True)


# ─── yt-dlp Cookies ─────────────────────────────────────────────────────────────────────────────

_COOKIES_FILE_NAME = "ytdlp_cookies.txt"
_MAX_COOKIES_SIZE = 2 * 1024 * 1024  # 2 MB


def _cookies_path() -> tuple["__import__('pathlib').Path", "__import__('pathlib').Path"]:
	import pathlib
	cookies_dir = pathlib.Path(get_data_dir()) / "cookies"
	cookies_dir.mkdir(parents=True, exist_ok=True)
	return cookies_dir, cookies_dir / _COOKIES_FILE_NAME


@router.post("/settings/ytdlp/cookies", response_model=OkDTO)
async def upload_ytdlp_cookies(
	request: Request,
	file: UploadFile = File(...),
):
	"""Upload a yt-dlp cookies .txt file. Saves it to DATA_DIR/cookies/ and
	updates YTDLP_COOKIES_FILE in-process immediately."""
	filename = (file.filename or "").strip()
	if not filename.lower().endswith(".txt"):
		return JSONResponse(
			status_code=400,
			content=build_error_envelope(
				code=ErrorCode.VALIDATION_ERROR,
				message="Only .txt cookies files are supported",
				details={"reason": "invalid_file_type"},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	content = await file.read(_MAX_COOKIES_SIZE + 1)
	if len(content) > _MAX_COOKIES_SIZE:
		return JSONResponse(
			status_code=400,
			content=build_error_envelope(
				code=ErrorCode.VALIDATION_ERROR,
				message="File too large (max 2 MB)",
				details={"reason": "file_too_large"},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	_, dest = _cookies_path()
	dest.write_bytes(content)

	# Update the environment variable in-process so subsequent yt-dlp calls use
	# the new cookies file immediately (no restart needed).
	os.environ["YTDLP_COOKIES_FILE"] = str(dest)
	logger.info("ytdlp cookies file updated: %s", dest)

	return OkDTO(ok=True)


@router.get("/settings/ytdlp/cookies/status", response_model=YtdlpCookiesStatusDTO)
def get_ytdlp_cookies_status(request: Request):
	"""Return whether a yt-dlp cookies file is currently configured."""
	_, dest = _cookies_path()
	if dest.exists():
		stat = dest.stat()
		return YtdlpCookiesStatusDTO(
			hasFile=True,
			fileName=_COOKIES_FILE_NAME,
			updatedAtMs=int(stat.st_mtime * 1000),
		)
	return YtdlpCookiesStatusDTO(hasFile=False)


# ─── ASR Settings ───────────────────────────────────────────────────────────


@router.get("/settings/asr/catalog", response_model=AsrCatalogDTO)
def get_asr_catalog_api(request: Request, session: Session = Depends(get_db_session)):
	providers_out: list[AsrCatalogProviderDTO] = []
	for provider in list_asr_catalog_providers():
		meta = get_asr_provider_secret_meta(session, provider_id=provider.provider_id)
		has_key = bool(meta.get("hasKey")) if isinstance(meta, dict) else False
		models: list[AsrCatalogModelDTO] = []
		for cm in list_custom_asr_models(session, provider_id=provider.provider_id):
			models.append(
				AsrCatalogModelDTO(
					modelId=cm["modelId"],
					displayName=cm["displayName"],
					isCustom=True,
				)
			)
		providers_out.append(
			AsrCatalogProviderDTO(
				providerId=provider.provider_id,
				displayName=provider.display_name,
				hasKey=has_key,
				secretUpdatedAtMs=int(meta.get("secretUpdatedAtMs")) if isinstance(meta, dict) and meta.get("secretUpdatedAtMs") else None,
				models=models,
				notes=provider.notes,
			)
		)
	return AsrCatalogDTO(providers=providers_out, updatedAtMs=_now_ms())


def _asr_remote_models_error_dto(code: str) -> AsrRemoteModelsErrorDTO:
	msgs: dict[str, str] = {
		"missing_credentials": "Save an API key for this provider first.",
		"invalid_credentials": "The stored API key could not be decrypted or was rejected.",
		"missing_api_key": "No API key available for this provider.",
		"invalid_api_key": "API key contains characters that cannot be sent in HTTP headers.",
		"provider_unavailable": "Could not reach the provider to list models.",
		"list_models_failed": "The provider rejected the models list request.",
		"invalid_response": "Unexpected response when listing models.",
		"unknown_provider": "Unknown provider.",
	}
	return AsrRemoteModelsErrorDTO(code=code, message=msgs.get(code, code))


@router.get("/settings/asr/providers/{provider_id}/remote-models", response_model=AsrRemoteModelsDTO)
def get_asr_remote_models(
	provider_id: str,
	_: Request,
	session: Session = Depends(get_db_session),
):
	pid = (provider_id or "").strip().lower()
	if find_asr_provider(pid) is None:
		return AsrRemoteModelsDTO(ok=False, models=[], error=_asr_remote_models_error_dto("unknown_provider"))

	ciphertext = get_asr_provider_secret_ciphertext(session, provider_id=pid)
	if not ciphertext:
		return AsrRemoteModelsDTO(ok=False, models=[], error=_asr_remote_models_error_dto("missing_credentials"))

	try:
		api_key = decrypt_api_key(ciphertext)
	except Exception:
		return AsrRemoteModelsDTO(ok=False, models=[], error=_asr_remote_models_error_dto("invalid_credentials"))

	items, err = fetch_remote_asr_models_for_provider(provider_id=pid, api_key=api_key)
	if err:
		return AsrRemoteModelsDTO(ok=False, models=[], error=_asr_remote_models_error_dto(err))

	return AsrRemoteModelsDTO(
		ok=True,
		models=[AsrRemoteModelDTO(modelId=i.model_id, displayName=i.display_name) for i in items],
		error=None,
	)


@router.get("/settings/asr/active", response_model=AsrActiveDTO)
def get_asr_active_api(request: Request, session: Session = Depends(get_db_session)):
	active = get_asr_active(session)
	if active is None:
		return AsrActiveDTO(configured=False, cloudEnabled=True, providerId=None, modelId=None, hasKey=False)

	provider_id = str(active.get("providerId") or "").strip()
	model_id = str(active.get("modelId") or "").strip()
	meta = get_asr_provider_secret_meta(session, provider_id=provider_id)
	has_key = bool(meta.get("hasKey")) if isinstance(meta, dict) else False
	local_model_size, local_device = _local_transcribe_settings()

	return AsrActiveDTO(
		configured=True,
		cloudEnabled=bool(active.get("cloudEnabled", True)),
		providerId=provider_id or None,
		modelId=model_id or None,
		localModelSize=local_model_size,
		localDevice=local_device,
		fallbackToLocal=bool(active.get("fallbackToLocal", True)),
		hasKey=has_key,
		updatedAtMs=int(active.get("updatedAtMs") or 0),
	)


@router.put("/settings/asr/active", response_model=OkDTO)
def put_asr_active_api(
	body: PutAsrActiveRequestDTO,
	request: Request,
	session: Session = Depends(get_db_session),
):
	provider_id = (body.providerId or "").strip().lower()
	model_id = (body.modelId or "").strip()
	if find_asr_provider(provider_id) is None:
		return JSONResponse(
			status_code=400,
			content=build_error_envelope(
				code=ErrorCode.VALIDATION_ERROR,
				message="Unknown ASR provider",
				details={"reason": "unknown_provider", "providerId": provider_id},
				request_id=getattr(request.state, "request_id", None),
			),
		)
	if not asr_model_exists(provider_id=provider_id, model_id=model_id):
		return JSONResponse(
			status_code=400,
			content=build_error_envelope(
				code=ErrorCode.VALIDATION_ERROR,
				message="Unknown ASR model",
				details={"reason": "unknown_model", "providerId": provider_id, "modelId": model_id},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	local_model_size, local_device = _local_transcribe_settings()
	set_asr_active(
		session,
		cloud_enabled=bool(body.cloudEnabled),
		provider_id=provider_id,
		model_id=model_id,
		local_model_size=local_model_size,
		local_device=local_device,
		fallback_to_local=bool(body.fallbackToLocal),
		now_ms=_now_ms(),
	)
	session.commit()
	return OkDTO(ok=True)


@router.put("/settings/asr/providers/{provider_id}/secret", response_model=OkDTO)
def put_asr_provider_secret_api(
	provider_id: str,
	body: PutAsrProviderSecretRequestDTO,
	request: Request,
	session: Session = Depends(get_db_session),
):
	if find_asr_provider(provider_id) is None:
		return JSONResponse(
			status_code=400,
			content=build_error_envelope(
				code=ErrorCode.VALIDATION_ERROR,
				message="Unknown ASR provider",
				details={"reason": "unknown_provider", "providerId": provider_id},
				request_id=getattr(request.state, "request_id", None),
			),
		)
	api_key = (body.apiKey or "").strip()
	if not api_key:
		return JSONResponse(
			status_code=400,
			content=build_error_envelope(
				code=ErrorCode.VALIDATION_ERROR,
				message="Invalid request",
				details={"reason": "invalid_api_key"},
				request_id=getattr(request.state, "request_id", None),
			),
		)
	pid = provider_id.strip().lower()
	ciphertext = encrypt_api_key(api_key)
	upsert_asr_provider_secret_ciphertext(session, provider_id=pid, ciphertext_b64=ciphertext, now_ms=_now_ms())
	session.commit()
	return OkDTO(ok=True)


@router.delete("/settings/asr/providers/{provider_id}/secret", response_model=OkDTO)
def delete_asr_provider_secret_api(
	provider_id: str,
	request: Request,
	session: Session = Depends(get_db_session),
):
	if find_asr_provider(provider_id) is None:
		return JSONResponse(
			status_code=400,
			content=build_error_envelope(
				code=ErrorCode.VALIDATION_ERROR,
				message="Unknown ASR provider",
				details={"reason": "unknown_provider", "providerId": provider_id},
				request_id=getattr(request.state, "request_id", None),
			),
		)
	_ = delete_asr_provider_secret(session, provider_id=provider_id.strip().lower())
	session.commit()
	return OkDTO(ok=True)


def _asr_runtime_from_request(
	session: Session,
	*,
	provider_id: str | None = None,
	model_id: str | None = None,
) -> AsrRuntimeSettings:
	runtime = asr_runtime_for_jobs(session)
	if provider_id:
		api_key = None
		ciphertext = get_asr_provider_secret_ciphertext(session, provider_id=provider_id.strip().lower())
		if ciphertext:
			try:
				api_key = decrypt_api_key(ciphertext)
			except Exception:
				api_key = None
		return AsrRuntimeSettings(
			cloud_enabled=True,
			provider_id=provider_id.strip().lower(),
			model_id=(model_id or runtime.model_id).strip(),
			local_model_size=runtime.local_model_size,
			local_device=runtime.local_device,
			fallback_to_local=runtime.fallback_to_local,
			api_key=api_key,
			configured=True,
		)
	return runtime


@router.post("/settings/asr/active/test", response_model=AsrActiveTestDTO)
def post_asr_active_test_api(request: Request, session: Session = Depends(get_db_session)):
	runtime = asr_runtime_for_jobs(session)
	err = validate_asr_runtime(runtime)
	if err:
		return AsrActiveTestDTO(ok=False, latencyMs=0, mode=None, message=err)
	try:
		ok, latency_ms, mode, message = run_asr_connectivity_test(runtime)
		return AsrActiveTestDTO(ok=ok, latencyMs=latency_ms, mode=mode, message=message)
	except AsrActiveTestError as exc:
		return AsrActiveTestDTO(ok=False, latencyMs=0, mode="cloud", message=f"{exc.code}: {exc.message}")


@router.post("/settings/asr/providers/{provider_id}/test", response_model=AsrActiveTestDTO)
def post_asr_provider_test_api(
	provider_id: str,
	body: ProviderAsrTestRequestDTO,
	request: Request,
	session: Session = Depends(get_db_session),
):
	pid = provider_id.strip().lower()
	if find_asr_provider(pid) is None:
		return AsrActiveTestDTO(ok=False, latencyMs=0, message="unknown_provider")
	model_id = (body.modelId or "").strip()
	if not asr_model_exists(provider_id=pid, model_id=model_id):
		return AsrActiveTestDTO(ok=False, latencyMs=0, message="unknown_model")
	runtime = _asr_runtime_from_request(
		session,
		provider_id=pid,
		model_id=model_id,
	)
	try:
		ok, latency_ms, mode, message = run_asr_connectivity_test(runtime)
		return AsrActiveTestDTO(ok=ok, latencyMs=latency_ms, mode=mode, message=message)
	except AsrActiveTestError as exc:
		return AsrActiveTestDTO(ok=False, latencyMs=0, mode="cloud", message=f"{exc.code}: {exc.message}")


@router.post("/settings/asr/providers/{provider_id}/models", response_model=OkDTO)
def add_custom_asr_model_api(
	provider_id: str,
	body: AddCustomAsrModelRequestDTO,
	request: Request,
	session: Session = Depends(get_db_session),
):
	if find_asr_provider(provider_id) is None:
		return JSONResponse(
			status_code=400,
			content=build_error_envelope(
				code=ErrorCode.VALIDATION_ERROR,
				message="Unknown ASR provider",
				details={"reason": "unknown_provider", "providerId": provider_id},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	model_id = (body.modelId or "").strip()
	display_name = (body.displayName or "").strip() or model_id
	if not model_id:
		return JSONResponse(
			status_code=400,
			content=build_error_envelope(
				code=ErrorCode.VALIDATION_ERROR,
				message="modelId is required",
				details={"reason": "missing_model_id"},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	pid = provider_id.strip().lower()
	custom_existing = list_custom_asr_models(session, provider_id=pid)
	if any(c["modelId"] == model_id for c in custom_existing):
		return JSONResponse(
			status_code=400,
			content=build_error_envelope(
				code=ErrorCode.VALIDATION_ERROR,
				message="Model already exists",
				details={"reason": "model_already_exists", "modelId": model_id},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	add_custom_asr_model(
		session,
		provider_id=pid,
		model_id=model_id,
		display_name=display_name,
		now_ms=_now_ms(),
	)
	session.commit()
	return OkDTO(ok=True)


@router.delete("/settings/asr/providers/{provider_id}/models/{model_id:path}", response_model=OkDTO)
def delete_custom_asr_model_api(
	provider_id: str,
	model_id: str,
	request: Request,
	session: Session = Depends(get_db_session),
):
	deleted = delete_custom_asr_model(session, provider_id=provider_id.strip().lower(), model_id=model_id.strip())
	if not deleted:
		return JSONResponse(
			status_code=404,
			content=build_error_envelope(
				code=ErrorCode.VALIDATION_ERROR,
				message="Custom model not found",
				details={"reason": "model_not_found", "providerId": provider_id, "modelId": model_id},
				request_id=getattr(request.state, "request_id", None),
			),
		)
	session.commit()
	return OkDTO(ok=True)


# ─── ASR Model Prefetch ─────────────────────────────────────────────────────


@router.post("/settings/asr/prefetch", response_model=OkDTO)
def prefetch_asr_model(request: Request, body: AsrPrefetchRequestDTO):
	"""Pre-download faster-whisper model into DATA_DIR for offline/packaged runs."""
	model_size = (body.modelSize or "base").strip() or "base"
	try:
		prefetch_faster_whisper_model(model_size=model_size)
		return OkDTO(ok=True)
	except AsrError as e:
		return JSONResponse(
			status_code=400,
			content=build_error_envelope(
				code=ErrorCode.VALIDATION_ERROR,
				message=str(e),
				details=getattr(e, "details", None) or {"reason": getattr(e, "kind", None) or "model_missing"},
				request_id=getattr(request.state, "request_id", None),
			),
		)
