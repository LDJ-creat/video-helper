from __future__ import annotations

import time
import uuid
from pathlib import Path
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from starlette.datastructures import UploadFile
from sqlalchemy.orm import Session

from core.contracts.error_codes import ErrorCode
from core.contracts.error_envelope import build_error_envelope
from core.contracts.progress import normalize_progress
from core.contracts.stages import PublicStage, to_public_stage
from core.app.sse.event_bus import GLOBAL_JOB_EVENT_BUS
from core.app.metadata.video_metadata import MetadataError, extract_video_metadata
from core.db.repositories.jobs import get_job_by_id
from core.db.models.job import Job
from core.db.models.project import Project
from core.db.session import get_db_session
from core.schemas.jobs import CreateJobRequest, JobCreatedDTO, JobDTO
from core.schemas.logs import JobLogsPageDTO, LogItemDTO
from core.app.logs.job_logs import read_job_logs_page
from core.storage.layout import allocate_upload_path


router = APIRouter(tags=["jobs"])


_ALLOWED_URL_SOURCE_TYPES: set[str] = {"youtube", "bilibili"}
_UPLOAD_SOURCE_TYPE = "upload"


def _max_upload_bytes() -> int:
	import os

	raw = os.environ.get("MAX_UPLOAD_MB")
	mb = 500
	if raw:
		try:
			mb = int(raw)
		except ValueError:
			mb = 500
	if mb < 1:
		mb = 1
	return mb * 1024 * 1024


def _is_supported_source_type(value: str) -> bool:
	return value in _ALLOWED_URL_SOURCE_TYPES or value == _UPLOAD_SOURCE_TYPE


def _is_valid_source_url(source_type: str, source_url: str) -> bool:
	try:
		parsed = urlparse(source_url)
	except Exception:
		return False

	if parsed.scheme not in {"http", "https"}:
		return False

	host = (parsed.netloc or "").lower()
	if not host:
		return False

	if source_type == "youtube":
		return host.endswith("youtube.com") or host == "youtu.be" or host.endswith("youtu.be")

	if source_type == "bilibili":
		return host.endswith("bilibili.com") or host == "b23.tv" or host.endswith("b23.tv")

	return False


def _is_supported_upload_filename(name: str | None) -> bool:
	if not name:
		return False
	suffix = Path(name).suffix.lower()
	return suffix in {".mp4", ".mkv", ".webm", ".mov"}


@router.post("/jobs", response_model=JobCreatedDTO)
async def create_job(request: Request, session: Session = Depends(get_db_session)):
	content_type = (request.headers.get("content-type") or "").lower()

	if content_type.startswith("application/json"):
		try:
			payload = await request.json()
		except Exception:
			return JSONResponse(
				status_code=400,
				content=build_error_envelope(
					code=ErrorCode.VALIDATION_ERROR,
					message="Invalid JSON body",
					request_id=getattr(request.state, "request_id", None),
				),
			)

		if isinstance(payload, dict):
			for forbidden_key in ("sourceFilePath", "source_file_path", "sourcePath", "source_path"):
				if forbidden_key in payload:
					return JSONResponse(
						status_code=400,
						content=build_error_envelope(
							code=ErrorCode.VALIDATION_ERROR,
							message="Local file path is not allowed",
							details={"field": forbidden_key},
							request_id=getattr(request.state, "request_id", None),
						),
					)

		try:
			req = CreateJobRequest.model_validate(payload)
		except Exception:
			return JSONResponse(
				status_code=400,
				content=build_error_envelope(
					code=ErrorCode.VALIDATION_ERROR,
					message="Invalid request",
					request_id=getattr(request.state, "request_id", None),
				),
			)

		source_type = (req.sourceType or "").strip().lower()
		if not _is_supported_source_type(source_type) or source_type == _UPLOAD_SOURCE_TYPE:
			return JSONResponse(
				status_code=400,
				content=build_error_envelope(
					code=ErrorCode.UNSUPPORTED_SOURCE_TYPE,
					message="Unsupported sourceType",
					details={"sourceType": req.sourceType},
					request_id=getattr(request.state, "request_id", None),
				),
			)

		if not _is_valid_source_url(source_type, req.sourceUrl):
			return JSONResponse(
				status_code=400,
				content=build_error_envelope(
					code=ErrorCode.INVALID_SOURCE_URL,
					message="Invalid sourceUrl",
					details={"sourceUrl": req.sourceUrl, "sourceType": source_type},
					request_id=getattr(request.state, "request_id", None),
				),
			)

		now_ms = _now_ms()
		project_id = str(uuid.uuid4())
		job_id = str(uuid.uuid4())

		project = Project(
			project_id=project_id,
			title=req.title,
			source_type=source_type,
			source_url=req.sourceUrl,
			source_path=None,
			duration_ms=None,
			format=None,
			latest_result_id=None,
			created_at_ms=now_ms,
			updated_at_ms=now_ms,
		)
		job = Job(
			job_id=job_id,
			project_id=project_id,
			type="analyze_video",
			status="queued",
			stage="ingest",
			progress=None,
			error=None,
			created_at_ms=now_ms,
			updated_at_ms=now_ms,
		)
		session.add(project)
		session.add(job)
		session.commit()

		GLOBAL_JOB_EVENT_BUS.emit_state(job_id=job_id, project_id=project_id, stage=job.stage, message="status=queued")

		return JobCreatedDTO(jobId=job_id, projectId=project_id, status="queued", createdAtMs=now_ms)

	if content_type.startswith("multipart/form-data"):
		form = await request.form()
		source_type = str(form.get("sourceType") or "").strip().lower()
		if source_type != _UPLOAD_SOURCE_TYPE:
			return JSONResponse(
				status_code=400,
				content=build_error_envelope(
					code=ErrorCode.UNSUPPORTED_SOURCE_TYPE,
					message="Unsupported sourceType",
					details={"sourceType": source_type},
					request_id=getattr(request.state, "request_id", None),
				),
			)

		file = form.get("file")
		if not isinstance(file, UploadFile):
			return JSONResponse(
				status_code=400,
				content=build_error_envelope(
					code=ErrorCode.VALIDATION_ERROR,
					message="Missing file",
					request_id=getattr(request.state, "request_id", None),
				),
			)

		if not _is_supported_upload_filename(file.filename):
			return JSONResponse(
				status_code=400,
				content=build_error_envelope(
					code=ErrorCode.VALIDATION_ERROR,
					message="Unsupported file type",
					details={"filename": file.filename},
					request_id=getattr(request.state, "request_id", None),
				),
			)

		now_ms = _now_ms()
		project_id = str(uuid.uuid4())
		job_id = str(uuid.uuid4())

		abs_path, rel_path = allocate_upload_path(project_id=project_id, job_id=job_id, original_filename=file.filename)
		max_bytes = _max_upload_bytes()
		size = 0
		try:
			with abs_path.open("wb") as out:
				while True:
					chunk = await file.read(1024 * 1024)
					if not chunk:
						break
					size += len(chunk)
					if size > max_bytes:
						raise MetadataError("file_unreadable", "File too large")
					out.write(chunk)
		finally:
			await file.close()

		try:
			meta = extract_video_metadata(abs_path)
		except MetadataError as e:
			try:
				abs_path.unlink(missing_ok=True)
			except Exception:
				pass

			code = ErrorCode.VALIDATION_ERROR
			if e.kind == "dependency_missing":
				code = ErrorCode.FFMPEG_MISSING
			return JSONResponse(
				status_code=400,
				content=build_error_envelope(
					code=code,
					message="Video metadata extraction failed",
					details={"reason": e.kind},
					request_id=getattr(request.state, "request_id", None),
				),
			)

		title_raw = form.get("title")
		title = str(title_raw) if title_raw not in (None, "") else None

		project = Project(
			project_id=project_id,
			title=title,
			source_type=_UPLOAD_SOURCE_TYPE,
			source_url=None,
			source_path=rel_path,
			duration_ms=meta.duration_ms,
			format=meta.format,
			latest_result_id=None,
			created_at_ms=now_ms,
			updated_at_ms=now_ms,
		)
		job = Job(
			job_id=job_id,
			project_id=project_id,
			type="analyze_video",
			status="queued",
			stage="ingest",
			progress=None,
			error=None,
			created_at_ms=now_ms,
			updated_at_ms=now_ms,
		)
		session.add(project)
		session.add(job)
		session.commit()

		GLOBAL_JOB_EVENT_BUS.emit_state(job_id=job_id, project_id=project_id, stage=job.stage, message="status=queued")
		return JobCreatedDTO(jobId=job_id, projectId=project_id, status="queued", createdAtMs=now_ms)

	return JSONResponse(
		status_code=415,
		content=build_error_envelope(
			code=ErrorCode.VALIDATION_ERROR,
			message="Unsupported Content-Type",
			details={"contentType": request.headers.get("content-type")},
			request_id=getattr(request.state, "request_id", None),
		),
	)


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
	now_ms = _now_ms()
	new_job = Job(
		job_id=new_job_id,
		project_id=job.project_id,
		type=job.type,
		status="queued",
		stage="ingest",
		progress=None,
		error=None,
		created_at_ms=now_ms,
		updated_at_ms=now_ms,
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
