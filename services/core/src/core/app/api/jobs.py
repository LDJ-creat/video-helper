from __future__ import annotations

import time
import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from core.contracts.error_codes import ErrorCode
from core.contracts.error_envelope import build_error_envelope
from core.contracts.progress import normalize_progress
from core.contracts.stages import PublicStage, to_public_stage
from core.app.sse.event_bus import GLOBAL_JOB_EVENT_BUS
from core.db.repositories.jobs import get_job_by_id
from core.db.session import get_db_session
from core.schemas.jobs import JobDTO
from core.schemas.logs import JobLogsPageDTO, LogItemDTO
from core.app.logs.job_logs import read_job_logs_page


router = APIRouter(tags=["jobs"])


def _safe_public_stage(value: str | None) -> PublicStage:
	if not value:
		return PublicStage.INGEST
	try:
		return to_public_stage(value)
	except ValueError:
		return PublicStage.INGEST


def _safe_progress(value: float | int | None) -> float | None:
	try:
		return normalize_progress(value)
	except (TypeError, ValueError):
		return None


def _now_ms() -> int:
	return int(time.time() * 1000)


@router.get("/jobs/{jobId}", response_model=JobDTO)
def get_job(jobId: str, request: Request, session: Session = Depends(get_db_session)):
	try:
		uuid.UUID(jobId)
	except ValueError:
		return JSONResponse(
			status_code=400,
			content=build_error_envelope(
				code=ErrorCode.VALIDATION_ERROR,
				message="Invalid jobId",
				details={"jobId": jobId},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	job = get_job_by_id(session, jobId)
	if job is None:
		return JSONResponse(
			status_code=404,
			content=build_error_envelope(
				code=ErrorCode.JOB_NOT_FOUND,
				message="Job does not exist",
				details={"jobId": jobId},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	return JobDTO(
		jobId=job.job_id,
		projectId=job.project_id,
		type=job.type,
		status=job.status,
		stage=_safe_public_stage(job.stage),
		progress=_safe_progress(job.progress),
		error=job.error,
		updatedAtMs=job.updated_at_ms,
	)


@router.get("/jobs/{jobId}/logs", response_model=JobLogsPageDTO)
def get_job_logs(
	jobId: str,
	request: Request,
	limit: int = 200,
	cursor: str | None = None,
	session: Session = Depends(get_db_session),
):
	if limit < 1 or limit > 500:
		return JSONResponse(
			status_code=400,
			content=build_error_envelope(
				code=ErrorCode.VALIDATION_ERROR,
				message="Invalid limit",
				details={"limit": limit},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	try:
		uuid.UUID(jobId)
	except ValueError:
		return JSONResponse(
			status_code=400,
			content=build_error_envelope(
				code=ErrorCode.VALIDATION_ERROR,
				message="Invalid jobId",
				details={"jobId": jobId},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	job = get_job_by_id(session, jobId)
	if job is None:
		return JSONResponse(
			status_code=404,
			content=build_error_envelope(
				code=ErrorCode.JOB_NOT_FOUND,
				message="Job does not exist",
				details={"jobId": jobId},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	try:
		page = read_job_logs_page(
			job_id=job.job_id,
			limit=limit,
			cursor=cursor,
			default_stage=job.stage,
		)
	except ValueError:
		return JSONResponse(
			status_code=400,
			content=build_error_envelope(
				code=ErrorCode.VALIDATION_ERROR,
				message="Invalid cursor",
				details={"cursor": cursor},
				request_id=getattr(request.state, "request_id", None),
			),
		)
	except RuntimeError:
		return JSONResponse(
			status_code=500,
			content=build_error_envelope(
				code=ErrorCode.JOB_LOGS_UNAVAILABLE,
				message="Job logs unavailable",
				details={"jobId": jobId},
				request_id=getattr(request.state, "request_id", None),
			),
		)
	return JobLogsPageDTO(
		items=[
			LogItemDTO(
				tsMs=item.ts_ms,
				level=item.level,
				message=item.message,
				stage=_safe_public_stage(item.stage),
			)
			for item in page.items
		],
		nextCursor=page.next_cursor,
	)


@router.post("/jobs/{jobId}/cancel")
def cancel_job(jobId: str, request: Request, session: Session = Depends(get_db_session)):
	try:
		uuid.UUID(jobId)
	except ValueError:
		return JSONResponse(
			status_code=400,
			content=build_error_envelope(
				code=ErrorCode.VALIDATION_ERROR,
				message="Invalid jobId",
				details={"jobId": jobId},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	job = get_job_by_id(session, jobId)
	if job is None:
		return JSONResponse(
			status_code=404,
			content=build_error_envelope(
				code=ErrorCode.JOB_NOT_FOUND,
				message="Job does not exist",
				details={"jobId": jobId},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	if job.status != "running":
		return JSONResponse(
			status_code=409,
			content=build_error_envelope(
				code=ErrorCode.JOB_NOT_CANCELLABLE,
				message="Job is not cancellable in its current status",
				details={"jobId": jobId, "status": job.status},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	job.status = "canceled"
	job.updated_at_ms = _now_ms()
	session.add(job)
	session.commit()

	GLOBAL_JOB_EVENT_BUS.emit_state(
		job_id=job.job_id,
		project_id=job.project_id,
		stage=job.stage,
		message="status=canceled",
	)

	return {"ok": True}


@router.post("/jobs/{jobId}/retry", response_model=JobDTO)
def retry_job(jobId: str, request: Request, session: Session = Depends(get_db_session)):
	try:
		uuid.UUID(jobId)
	except ValueError:
		return JSONResponse(
			status_code=400,
			content=build_error_envelope(
				code=ErrorCode.VALIDATION_ERROR,
				message="Invalid jobId",
				details={"jobId": jobId},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	job = get_job_by_id(session, jobId)
	if job is None:
		return JSONResponse(
			status_code=404,
			content=build_error_envelope(
				code=ErrorCode.JOB_NOT_FOUND,
				message="Job does not exist",
				details={"jobId": jobId},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	if job.status not in {"failed", "canceled"}:
		return JSONResponse(
			status_code=409,
			content=build_error_envelope(
				code=ErrorCode.JOB_NOT_RETRIABLE,
				message="Job is not retriable in its current status",
				details={"jobId": jobId, "status": job.status},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	from core.db.models.job import Job

	new_job_id = str(uuid.uuid4())
	new_job = Job(
		job_id=new_job_id,
		project_id=job.project_id,
		type=job.type,
		status="queued",
		stage="ingest",
		progress=None,
		error=None,
		updated_at_ms=_now_ms(),
	)
	session.add(new_job)
	session.commit()

	GLOBAL_JOB_EVENT_BUS.emit_state(
		job_id=new_job.job_id,
		project_id=new_job.project_id,
		stage=new_job.stage,
		message="status=queued",
	)

	return JobDTO(
		jobId=new_job.job_id,
		projectId=new_job.project_id,
		type=new_job.type,
		status=new_job.status,
		stage=_safe_public_stage(new_job.stage),
		progress=_safe_progress(new_job.progress),
		error=new_job.error,
		updatedAtMs=new_job.updated_at_ms,
	)
