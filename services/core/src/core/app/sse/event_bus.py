from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import threading

from core.contracts.progress import ProgressTracker
from core.contracts.sse_events import SseEventPayload, SseEventType, build_payload
from core.contracts.stages import PublicStage


@dataclass
class _JobStream:
    next_id: int
    events: deque[tuple[SseEventType, str, SseEventPayload]]
    tracker: ProgressTracker
    cond: threading.Condition


class JobEventBus:
    """In-memory best-effort event buffer per job.

    This is an MVP implementation to satisfy observability stories before worker/queue
    persistence lands.
    """

    def __init__(self, max_events_per_job: int = 500) -> None:
        self._max_events = max_events_per_job
        self._streams: dict[str, _JobStream] = {}
        self._lock = threading.Lock()

    def _stream(self, job_id: str) -> _JobStream:
        stream = self._streams.get(job_id)
        if stream is None:
            # Condition shares the same underlying lock to avoid lock-order deadlocks.
            cond = threading.Condition(self._lock)
            stream = _JobStream(next_id=1, events=deque(maxlen=self._max_events), tracker=ProgressTracker(), cond=cond)
            self._streams[job_id] = stream
        return stream

    def _emit(
        self,
        *,
        job_id: str,
        project_id: str,
        stage: str | PublicStage,
        event_type: SseEventType,
        progress: float | int | None = None,
        message: str | None = None,
    ) -> tuple[SseEventType, str, SseEventPayload]:
        with self._lock:
            stream = self._stream(job_id)
            stage_progress = stream.tracker.update(stage, progress)
            event_id = str(stream.next_id)
            stream.next_id += 1

            payload = build_payload(
                event_id=event_id,
                job_id=job_id,
                project_id=project_id,
                stage=stage_progress.stage,
                progress=stage_progress.progress,
                message=message,
            )

            record = (event_type, event_id, payload)
            stream.events.append(record)
            # Wake any SSE listeners waiting for new events.
            try:
                stream.cond.notify_all()
            except RuntimeError:
                # Best-effort: ignore if condition isn't in a usable state.
                pass
            return record

    def _replay_after_locked(
        self,
        stream: _JobStream,
        last_event_id: str | None,
    ) -> list[tuple[SseEventType, str, SseEventPayload]]:
        if not last_event_id:
            return list(stream.events)

        try:
            last = int(last_event_id)
        except ValueError:
            return []

        out: list[tuple[SseEventType, str, SseEventPayload]] = []
        for event_type, event_id, payload in stream.events:
            try:
                if int(event_id) > last:
                    out.append((event_type, event_id, payload))
            except ValueError:
                continue
        return out

    def emit_heartbeat(self, *, job_id: str, project_id: str, stage: str | PublicStage) -> tuple[SseEventType, str, SseEventPayload]:
        return self._emit(job_id=job_id, project_id=project_id, stage=stage, event_type=SseEventType.HEARTBEAT)

    def emit_state(
        self, *, job_id: str, project_id: str, stage: str | PublicStage, message: str | None = None
    ) -> tuple[SseEventType, str, SseEventPayload]:
        return self._emit(job_id=job_id, project_id=project_id, stage=stage, event_type=SseEventType.STATE, message=message)

    def emit_progress(
        self,
        *,
        job_id: str,
        project_id: str,
        stage: str | PublicStage,
        progress: float | int | None,
        message: str | None = None,
    ) -> tuple[SseEventType, str, SseEventPayload]:
        return self._emit(
            job_id=job_id,
            project_id=project_id,
            stage=stage,
            event_type=SseEventType.PROGRESS,
            progress=progress,
            message=message,
        )

    def emit_log(self, *, job_id: str, project_id: str, stage: str | PublicStage, message: str) -> tuple[SseEventType, str, SseEventPayload]:
        return self._emit(job_id=job_id, project_id=project_id, stage=stage, event_type=SseEventType.LOG, message=message)

    def replay_after(self, job_id: str, last_event_id: str | None) -> list[tuple[SseEventType, str, SseEventPayload]]:
        with self._lock:
            stream = self._streams.get(job_id)
            if stream is None:
                return []

            return self._replay_after_locked(stream, last_event_id)


    def wait_for_events_after(
        self,
        job_id: str,
        last_event_id: str | None,
        *,
        timeout_s: float = 1.0,
    ) -> list[tuple[SseEventType, str, SseEventPayload]]:
        """Block until new events are available (or timeout), then return them.

        This is intended for SSE handlers to achieve realtime-ish push while
        keeping the event bus in-memory and thread-safe.
        """

        with self._lock:
            stream = self._streams.get(job_id)
            if stream is None:
                return []

            # Fast path: already have something after last_event_id.
            out = self._replay_after_locked(stream, last_event_id)
            if out:
                return out

            # Wait for new events.
            try:
                stream.cond.wait(timeout=timeout_s)
            except RuntimeError:
                return []

            return self._replay_after_locked(stream, last_event_id)


    def reset_for_tests(self) -> None:
        with self._lock:
            self._streams.clear()


GLOBAL_JOB_EVENT_BUS = JobEventBus()
