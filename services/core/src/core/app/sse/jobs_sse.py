from __future__ import annotations

import asyncio
import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from starlette.responses import StreamingResponse
from sqlalchemy.orm import Session

from core.contracts.error_codes import ErrorCode
from core.contracts.error_envelope import build_error_envelope
from core.contracts.sse_events import SseEventType, format_sse_event
from core.app.sse.event_bus import GLOBAL_JOB_EVENT_BUS
from core.db.repositories.jobs import get_job_by_id
from core.db.session import get_db_session


router = APIRouter(tags=["jobs"])


@router.get("/jobs/{jobId}/events")
async def job_events(
	jobId: str,
	request: Request,
	once: bool = False,
	session: Session = Depends(get_db_session),
):
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

	# Best-effort: accept Last-Event-ID header but we don't replay yet.
	last_event_id = request.headers.get("Last-Event-ID")

	async def event_stream():
		try:
			# Best-effort replay if we still have buffered events for this job.
			replay = GLOBAL_JOB_EVENT_BUS.replay_after(job.job_id, last_event_id)
			for event_type, event_id, payload in replay:
				yield format_sse_event(event_type=event_type, event_id=event_id, payload=payload)

			# If replay isn't possible, start from current state snapshot.
			if not replay:
				event_type, event_id, payload = GLOBAL_JOB_EVENT_BUS.emit_state(
					job_id=job.job_id,
					project_id=job.project_id,
					stage=job.stage,
					message=f"status={job.status}",
				)
				yield format_sse_event(event_type=event_type, event_id=event_id, payload=payload)

			# Test helper: emit a single frame and close.
			if once:
				return

			# Heartbeats keep the connection alive and allow FE timeout detection.
			while True:
				if await request.is_disconnected():
					return

				try:
					await asyncio.sleep(1)
				except asyncio.CancelledError:
					return

				event_type, event_id, payload = GLOBAL_JOB_EVENT_BUS.emit_heartbeat(
					job_id=job.job_id,
					project_id=job.project_id,
					stage=job.stage,
				)
				yield format_sse_event(event_type=event_type, event_id=event_id, payload=payload)
		except asyncio.CancelledError:
			return

	return StreamingResponse(
		event_stream(),
		media_type="text/event-stream",
		headers={
			"Cache-Control": "no-cache",
			"Connection": "keep-alive",
			"X-Accel-Buffering": "no",
		},
	)
