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
from core.llm.catalog import list_llm_catalog_providers, LLMCatalogProvider, LLMCatalogModel
from core.llm.catalog import find_provider
from core.llm.catalog import model_exists
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
	delete_custom_provider,
)
from core.db.session import get_db_session
from core.llm.active_test import LLMActiveTestError, run_llm_connectivity_test
from core.llm.secrets_crypto import decrypt_api_key, encrypt_api_key
from core.schemas.settings import (
	AnalyzeSettingsDTO,
	LLMCatalogDTO,
	LLMCatalogModelDTO,
	LLMCatalogProviderDTO,
	LLMActiveDTO,
	LLMActiveTestDTO,
	OkDTO,
	PutLLMActiveRequestDTO,
	PutLLMProviderSecretRequestDTO,
	AddCustomModelRequestDTO,
	AddCustomProviderRequestDTO,
	YtdlpCookiesStatusDTO,
)
from core.settings import get_effective_analyze_settings
from core.db.session import get_data_dir


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

		# Static models + any custom models added to this provider.
		models: list[LLMCatalogModelDTO] = [
			LLMCatalogModelDTO(modelId=m.model_id, displayName=m.display_name)
			for m in p.models
		]
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
				displayName=p.display_name,
				hasKey=has_key,
				secretUpdatedAtMs=secret_updated_at_ms,
				models=models,
				isCustom=False,
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
	"""Check if a model exists in static catalog OR as a custom model in DB."""
	if model_exists(provider_id=provider_id, model_id=model_id):
		return True
	custom = list_custom_models(session, provider_id=provider_id)
	mid = (model_id or "").strip()
	return any(c["modelId"] == mid for c in custom)


def _resolve_runtime_model_merged(*, provider_id: str, model_id: str, session: Session) -> str | None:
	"""Resolve the runtime model name for static or custom models."""
	static_result = resolve_runtime_model_name(provider_id=provider_id, model_id=model_id)
	if static_result is not None:
		return static_result

	# For custom models, use model_id as-is (no prefix stripping needed).
	if _model_exists_merged(provider_id=provider_id, model_id=model_id, session=session):
		mid = (model_id or "").strip()
		return mid or None
	return None


def _get_provider_base_url(provider_id: str, session: Session) -> str | None:
	"""Get base_url from static catalog or custom providers."""
	static = find_provider(provider_id)
	if static is not None:
		return static.base_url
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
		providers = list_llm_catalog_providers()
		if not providers or not providers[0].models:
			return JSONResponse(
				status_code=500,
				content=build_error_envelope(
					code=ErrorCode.VALIDATION_ERROR,
					message="LLM catalog is empty",
					details={"reason": "catalog_empty"},
					request_id=getattr(request.state, "request_id", None),
				),
			)

		default_provider = providers[0]
		default_model = default_provider.models[0]
		set_llm_active(session, provider_id=default_provider.provider_id, model_id=default_model.model_id, now_ms=_now_ms())
		session.commit()
		active = get_llm_active(session)

	if active is None:
		return JSONResponse(
			status_code=500,
			content=build_error_envelope(
				code=ErrorCode.VALIDATION_ERROR,
				message="Active selection unavailable",
				details={"reason": "active_unavailable"},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	provider_id = str(active.get("providerId") or "")
	model_id = str(active.get("modelId") or "")
	updated_at_ms = int(active.get("updatedAtMs") or 0)

	meta = get_llm_provider_secret_meta(session, provider_id=provider_id)
	has_key = bool(meta.get("hasKey")) if isinstance(meta, dict) else False

	return LLMActiveDTO(providerId=provider_id, modelId=model_id, hasKey=has_key, updatedAtMs=updated_at_ms)


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


# ─── Active test ──────────────────────────────────────────────────────────────


@router.post("/settings/llm/active/test", response_model=LLMActiveTestDTO)
def post_llm_active_test(request: Request, session: Session = Depends(get_db_session)):
	active = get_llm_active(session)
	if active is None:
		providers = list_llm_catalog_providers()
		if not providers or not providers[0].models:
			return JSONResponse(
				status_code=500,
				content=build_error_envelope(
					code=ErrorCode.VALIDATION_ERROR,
					message="LLM catalog is empty",
					details={"reason": "catalog_empty"},
					request_id=getattr(request.state, "request_id", None),
				),
			)
		default_provider = providers[0]
		default_model = default_provider.models[0]
		set_llm_active(session, provider_id=default_provider.provider_id, model_id=default_model.model_id, now_ms=_now_ms())
		session.commit()
		active = get_llm_active(session)

	if active is None:
		return JSONResponse(
			status_code=500,
			content=build_error_envelope(
				code=ErrorCode.VALIDATION_ERROR,
				message="Active selection unavailable",
				details={"reason": "active_unavailable"},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	provider_id = str(active.get("providerId") or "").strip().lower()
	model_id = str(active.get("modelId") or "").strip()

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

	try:
		latency_ms = run_llm_connectivity_test(
			base_url=base_url,
			api_key=api_key,
			model=runtime_model,
		)
	except LLMActiveTestError as e:
		status = 400 if e.reason in {"invalid_credentials", "model_not_found"} else 503
		msg = {
			"invalid_credentials": "Invalid credentials",
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

	return LLMActiveTestDTO(ok=True, latencyMs=int(latency_ms))


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

	# Disallow adding a model_id that already exists in the static catalog.
	if model_exists(provider_id=provider_id, model_id=model_id):
		return JSONResponse(
			status_code=400,
			content=build_error_envelope(
				code=ErrorCode.VALIDATION_ERROR,
				message="Model already exists in catalog",
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
	"""Add a fully custom provider (provider_id, display_name, base_url) plus an initial model."""
	provider_id = (body.providerId or "").strip().lower()
	display_name = (body.displayName or "").strip()
	base_url = (body.baseUrl or "").strip()
	model_id = (body.modelId or "").strip()
	model_display_name = (body.modelDisplayName or "").strip() or model_id

	# Validate fields.
	if not provider_id:
		return JSONResponse(
			status_code=400,
			content=build_error_envelope(
				code=ErrorCode.VALIDATION_ERROR,
				message="providerId is required",
				details={"reason": "missing_provider_id"},
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

	add_custom_provider(
		session,
		provider_id=provider_id,
		display_name=display_name,
		base_url=base_url,
		now_ms=_now_ms(),
	)
	# Add the initial model.
	add_custom_model(
		session,
		provider_id=provider_id,
		model_id=model_id,
		display_name=model_display_name,
		now_ms=_now_ms(),
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
