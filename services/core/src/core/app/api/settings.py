from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from core.contracts.error_codes import ErrorCode
from core.contracts.error_envelope import build_error_envelope
from core.schemas.settings import AnalyzeSettingsDTO
from core.settings import SettingsFileError, get_effective_analyze_settings


router = APIRouter(tags=["settings"])


@router.get("/settings/analyze", response_model=AnalyzeSettingsDTO)
def get_analyze_settings(request: Request):
	try:
		settings = get_effective_analyze_settings()
	except SettingsFileError:
		return JSONResponse(
			status_code=500,
			content=build_error_envelope(
				code=ErrorCode.VALIDATION_ERROR,
				message="Invalid persisted settings",
				details={"reason": "invalid_settings_file"},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	return AnalyzeSettingsDTO(**settings.to_public_payload())
