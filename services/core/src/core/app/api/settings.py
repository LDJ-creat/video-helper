from __future__ import annotations

import time

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from core.contracts.error_codes import ErrorCode
from core.contracts.error_envelope import build_error_envelope
from core.llm.catalog import list_llm_catalog_providers
from core.llm.catalog import find_provider
from core.llm.catalog import model_exists
from core.llm.catalog import resolve_runtime_model_name
from core.db.repositories.llm_settings import get_llm_provider_secret_meta
from core.db.repositories.llm_settings import delete_llm_provider_secret, upsert_llm_provider_secret_ciphertext
from core.db.repositories.llm_settings import get_llm_active, set_llm_active
from core.db.repositories.llm_settings import get_llm_provider_secret_ciphertext
from core.db.session import get_db_session
from core.llm.active_test import LLMActiveTestError, run_llm_connectivity_test
from core.llm.secrets_crypto import decrypt_api_key, encrypt_api_key
from core.app.middleware.auth import ensure_llm_settings_write_authorized
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
)
from core.settings import get_effective_analyze_settings


router = APIRouter(tags=["settings"])


def _now_ms() -> int:
	return int(time.time() * 1000)


@router.get("/settings/analyze", response_model=AnalyzeSettingsDTO)
def get_analyze_settings(request: Request):
	settings = get_effective_analyze_settings()

	return AnalyzeSettingsDTO(**settings.to_public_payload())


@router.get("/settings/llm/catalog", response_model=LLMCatalogDTO)
def get_llm_catalog(_: Request, session: Session = Depends(get_db_session)):
	providers: list[LLMCatalogProviderDTO] = []
	for p in list_llm_catalog_providers():
		meta = get_llm_provider_secret_meta(session, provider_id=p.provider_id)
		has_key = bool(meta.get("hasKey")) if isinstance(meta, dict) else False
		secret_updated_at_ms = meta.get("secretUpdatedAtMs") if isinstance(meta, dict) else None
		if not isinstance(secret_updated_at_ms, int):
			secret_updated_at_ms = None

		providers.append(
			LLMCatalogProviderDTO(
				providerId=p.provider_id,
				displayName=p.display_name,
				hasKey=has_key,
				secretUpdatedAtMs=secret_updated_at_ms,
				models=[LLMCatalogModelDTO(modelId=m.model_id, displayName=m.display_name) for m in p.models],
			)
		)

	return LLMCatalogDTO(providers=providers, updatedAtMs=_now_ms())


@router.put("/settings/llm/providers/{provider_id}/secret", response_model=OkDTO)
def put_llm_provider_secret(
	provider_id: str,
	body: PutLLMProviderSecretRequestDTO,
	request: Request,
	session: Session = Depends(get_db_session),
):
	auth = ensure_llm_settings_write_authorized(request)
	if auth is not None:
		return auth

	provider = find_provider(provider_id)
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

	ciphertext = encrypt_api_key(api_key)
	upsert_llm_provider_secret_ciphertext(session, provider_id=provider.provider_id, ciphertext_b64=ciphertext, now_ms=_now_ms())
	session.commit()
	return OkDTO(ok=True)


@router.delete("/settings/llm/providers/{provider_id}/secret", response_model=OkDTO)
def delete_llm_provider_secret_api(
	provider_id: str,
	request: Request,
	session: Session = Depends(get_db_session),
):
	auth = ensure_llm_settings_write_authorized(request)
	if auth is not None:
		return auth

	provider = find_provider(provider_id)
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

	_ = delete_llm_provider_secret(session, provider_id=provider.provider_id)
	session.commit()
	return OkDTO(ok=True)


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
	auth = ensure_llm_settings_write_authorized(request)
	if auth is not None:
		return auth

	provider_id = (body.providerId or "").strip().lower()
	model_id = (body.modelId or "").strip()

	provider = find_provider(provider_id)
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

	if not model_exists(provider_id=provider.provider_id, model_id=model_id):
		return JSONResponse(
			status_code=400,
			content=build_error_envelope(
				code=ErrorCode.VALIDATION_ERROR,
				message="Model not found",
				details={"reason": "model_not_found", "providerId": provider.provider_id, "modelId": body.modelId},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	set_llm_active(session, provider_id=provider.provider_id, model_id=model_id, now_ms=_now_ms())
	session.commit()
	return OkDTO(ok=True)


@router.post("/settings/llm/active/test", response_model=LLMActiveTestDTO)
def post_llm_active_test(request: Request, session: Session = Depends(get_db_session)):
	auth = ensure_llm_settings_write_authorized(request)
	if auth is not None:
		return auth

	active = get_llm_active(session)
	if active is None:
		# Keep behavior consistent with GET /active.
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

	provider = find_provider(provider_id)
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

	if not model_exists(provider_id=provider.provider_id, model_id=model_id):
		return JSONResponse(
			status_code=400,
			content=build_error_envelope(
				code=ErrorCode.VALIDATION_ERROR,
				message="Model not found",
				details={"reason": "model_not_found", "providerId": provider.provider_id, "modelId": model_id},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	ciphertext = get_llm_provider_secret_ciphertext(session, provider_id=provider.provider_id)
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

	runtime_model = resolve_runtime_model_name(provider_id=provider.provider_id, model_id=model_id)
	if not runtime_model:
		return JSONResponse(
			status_code=400,
			content=build_error_envelope(
				code=ErrorCode.VALIDATION_ERROR,
				message="Model not found",
				details={"reason": "model_not_found", "providerId": provider.provider_id, "modelId": model_id},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	try:
		latency_ms = run_llm_connectivity_test(
			base_url=provider.base_url,
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
