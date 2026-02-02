from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from core.contracts.error_codes import ErrorCode
from core.contracts.error_envelope import build_error_envelope
from core.db.repositories.projects import get_project_by_id
from core.db.repositories.results import get_result_by_id
from core.db.session import get_db_session
from core.schemas.results import ResultDTO


router = APIRouter(tags=["results"])


@router.get("/projects/{projectId}/results/latest", response_model=ResultDTO)
def get_latest_result(projectId: str, request: Request, session: Session = Depends(get_db_session)):
	project = get_project_by_id(session, projectId)
	if project is None:
		return JSONResponse(
			status_code=404,
			content=build_error_envelope(
				code=ErrorCode.PROJECT_NOT_FOUND,
				message="Project does not exist",
				details={"projectId": projectId},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	if not project.latest_result_id:
		return JSONResponse(
			status_code=404,
			content=build_error_envelope(
				code=ErrorCode.RESULT_NOT_FOUND,
				message="Result does not exist",
				details={"projectId": projectId},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	result = get_result_by_id(session, project.latest_result_id)
	if result is None:
		return JSONResponse(
			status_code=404,
			content=build_error_envelope(
				code=ErrorCode.RESULT_NOT_FOUND,
				message="Result does not exist",
				details={"projectId": projectId},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	return ResultDTO(
		resultId=result.result_id,
		projectId=result.project_id,
		schemaVersion=result.schema_version,
		pipelineVersion=result.pipeline_version,
		createdAtMs=result.created_at_ms,
		chapters=result.chapters,
		highlights=result.highlights,
		mindmap=result.mindmap,
		note=result.note,
		assetRefs=result.asset_refs,
	)
