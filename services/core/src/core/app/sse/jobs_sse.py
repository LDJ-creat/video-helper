from __future__ import annotations

import asyncio
import os
import uuid

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from starlette.responses import StreamingResponse

from core.contracts.error_codes import ErrorCode
from core.contracts.error_envelope import build_error_envelope
from core.contracts.sse_events import SseEventType, build_payload, format_sse_event
from core.app.sse.event_bus import GLOBAL_JOB_EVENT_BUS
from core.db.repositories.jobs import get_job_by_id
from core.db.session import get_sessionmaker


router = APIRouter(tags=["jobs"])


@router.get("/jobs/{jobId}/events")
async def job_events(
	jobId: str,
	request: Request,
	once: bool = False,
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

	# Use a short-lived session to fetch job details and then release the connection immediately.
	# This prevents the SSE stream from holding a DB connection for its entire duration.
	with get_sessionmaker()() as session:
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
		# Extract needed data to avoid DetachedInstanceError or holding refs to the session
		job_data = {
			"job_id": job.job_id,
			"project_id": job.project_id,
			"stage": job.stage,
			"status": job.status,
			"progress": job.progress,
		}

	# Best-effort: accept Last-Event-ID header and replay buffered events.
	last_event_id = request.headers.get("Last-Event-ID")

	async def event_stream():
		try:
			cursor_event_id = last_event_id
			# Best-effort replay if we still have buffered events for this job.
			replay = GLOBAL_JOB_EVENT_BUS.replay_after(job_data["job_id"], cursor_event_id)
			for event_type, event_id, payload in replay:
				yield format_sse_event(event_type=event_type, event_id=event_id, payload=payload)
				cursor_event_id = event_id

			# If replay isn't possible, start from current state snapshot.
			if not replay:
				event_type, event_id, payload = GLOBAL_JOB_EVENT_BUS.emit_state(
					job_id=job_data["job_id"],
					project_id=job_data["project_id"],
					stage=job_data["stage"],
					message=f"status={job_data['status']}",
				)
				yield format_sse_event(event_type=event_type, event_id=event_id, payload=payload)
				cursor_event_id = event_id

			# Test helper: emit a single frame and close.
			if once:
				return

			# Realtime-ish push: wait for new events and stream them immediately.
			# Keep-alive: if no new events arrive within timeout, emit a lightweight
			# heartbeat frame (not persisted to the bus) to prevent proxies from
			# buffering/closing idle connections.
			#
			# NOTE: A very small timeout (e.g. 1s) causes unnecessary wakeups and can
			# amplify reconnect storms when an upstream proxy is flaky. Keep it modest.
			raw_wait = (os.environ.get("SSE_WAIT_TIMEOUT_S") or "").strip()
			try:
				wait_timeout_s = float(max(1, int(raw_wait))) if raw_wait else 15.0
			except ValueError:
				wait_timeout_s = 15.0
			while True:
				if await request.is_disconnected():
					return

				try:
					new_events = await asyncio.to_thread(
						GLOBAL_JOB_EVENT_BUS.wait_for_events_after,
						job_data["job_id"],
						cursor_event_id,
						timeout_s=wait_timeout_s,
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
					job_id=job_data["job_id"],
					project_id=job_data["project_id"],
					stage=job_data["stage"],
					progress=job_data["progress"],
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
