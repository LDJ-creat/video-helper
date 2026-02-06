from __future__ import annotations

import asyncio
import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from starlette.responses import StreamingResponse
from sqlalchemy.orm import Session

from core.contracts.error_codes import ErrorCode
from core.contracts.error_envelope import build_error_envelope
from core.contracts.sse_events import SseEventType, build_payload, format_sse_event
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

	# Best-effort: accept Last-Event-ID header and replay buffered events.
	last_event_id = request.headers.get("Last-Event-ID")

	async def event_stream():
		try:
			cursor_event_id = last_event_id
			# Best-effort replay if we still have buffered events for this job.
			replay = GLOBAL_JOB_EVENT_BUS.replay_after(job.job_id, cursor_event_id)
			for event_type, event_id, payload in replay:
				yield format_sse_event(event_type=event_type, event_id=event_id, payload=payload)
				cursor_event_id = event_id

			# If replay isn't possible, start from current state snapshot.
			if not replay:
				event_type, event_id, payload = GLOBAL_JOB_EVENT_BUS.emit_state(
					job_id=job.job_id,
					project_id=job.project_id,
					stage=job.stage,
					message=f"status={job.status}",
				)
				yield format_sse_event(event_type=event_type, event_id=event_id, payload=payload)
				cursor_event_id = event_id

			# Test helper: emit a single frame and close.
			if once:
				return

			# Realtime push: wait for new events and stream them immediately.
			# Keep-alive: if no new events arrive within timeout, emit a lightweight
			# heartbeat frame (not persisted to the bus) to prevent proxies from
			# buffering/closing idle connections.
			while True:
				if await request.is_disconnected():
					return

				try:
					new_events = await asyncio.to_thread(
						GLOBAL_JOB_EVENT_BUS.wait_for_events_after,
						job.job_id,
						cursor_event_id,
						timeout_s=1.0,
					)
				except asyncio.CancelledError:
					return

				if new_events:
					for event_type, event_id, payload in new_events:
						yield format_sse_event(event_type=event_type, event_id=event_id, payload=payload)
						cursor_event_id = event_id
					continue

				# Keep-alive heartbeat (do not advance last_event_id)
				hb_id = cursor_event_id or "0"
				payload = build_payload(
					event_id=hb_id,
					job_id=job.job_id,
					project_id=job.project_id,
					stage=job.stage,
					progress=job.progress,
					message=None,
				)
				yield format_sse_event(event_type=SseEventType.HEARTBEAT, event_id=hb_id, payload=payload)
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
