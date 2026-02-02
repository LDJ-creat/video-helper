from __future__ import annotations

import asyncio
import os
import time
import uuid
from dataclasses import dataclass
from typing import Protocol

from core.app.sse.event_bus import GLOBAL_JOB_EVENT_BUS
from core.db.session import get_sessionmaker
from core.db.repositories.job_queue import (
    claim_next_queued_job,
    count_running_jobs,
    mark_job_failed,
    mark_job_succeeded,
    requeue_running_jobs,
)


def _now_ms() -> int:
    return int(time.time() * 1000)


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_bool(name: str, default: bool = False) -> bool:
    raw = (os.environ.get(name) or "").strip().lower()
    if raw in {"1", "true", "yes", "y", "on"}:
        return True
    if raw in {"0", "false", "no", "n", "off"}:
        return False
    return default


class JobProcessor(Protocol):
    async def process(self, *, job_id: str, project_id: str) -> None: ...


@dataclass(frozen=True)
class WorkerConfig:
    enabled: bool = False
    max_concurrent_jobs: int = 2
    poll_interval_ms: int = 500
    lease_ms: int = 30_000
    noop_process_ms: int = 0

    @staticmethod
    def from_env() -> "WorkerConfig":
        return WorkerConfig(
            enabled=_env_bool("WORKER_ENABLE", False),
            max_concurrent_jobs=max(1, _env_int("MAX_CONCURRENT_JOBS", 2)),
            poll_interval_ms=max(50, _env_int("WORKER_POLL_INTERVAL_MS", 500)),
            lease_ms=max(1_000, _env_int("WORKER_LEASE_MS", 30_000)),
            noop_process_ms=max(0, _env_int("WORKER_NOOP_PROCESS_MS", 0)),
        )


class NoopJobProcessor:
    def __init__(self, *, sleep_ms: int = 0):
        self._sleep_ms = max(0, int(sleep_ms))

    async def process(self, *, job_id: str, project_id: str) -> None:
        if self._sleep_ms:
            await asyncio.sleep(self._sleep_ms / 1000)

        SessionLocal = get_sessionmaker()
        with SessionLocal() as session:
            now_ms = _now_ms()
            mark_job_succeeded(session, job_id=job_id, now_ms=now_ms)
            session.commit()

        GLOBAL_JOB_EVENT_BUS.emit_state(
            job_id=job_id,
            project_id=project_id,
            stage="ingest",
            message="status=succeeded",
        )


def worker_tick(*, worker_id: str, max_concurrent_jobs: int, lease_ms: int) -> list[tuple[str, str]]:
    """Claim up to available slots and return (job_id, project_id) pairs."""

    SessionLocal = get_sessionmaker()
    claimed: list[tuple[str, str]] = []

    with SessionLocal() as session:
        now_ms = _now_ms()
        running = count_running_jobs(session)
        slots = max(0, int(max_concurrent_jobs) - running)

        for _ in range(slots):
            job = claim_next_queued_job(session, worker_id=worker_id, now_ms=now_ms, lease_ms=lease_ms)
            if job is None:
                break
            claimed.append((job.job_id, job.project_id))

        session.commit()

    return claimed


class WorkerService:
    def __init__(self, *, config: WorkerConfig, processor: JobProcessor | None = None):
        self._config = config
        self._worker_id = f"worker-{uuid.uuid4()}"
        self._processor: JobProcessor = processor or NoopJobProcessor(sleep_ms=config.noop_process_ms)
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        if not self._config.enabled:
            return

        # Restart recovery: requeue running jobs (best-effort).
        SessionLocal = get_sessionmaker()
        with SessionLocal() as session:
            requeue_running_jobs(session, now_ms=_now_ms(), reason="startup")
            session.commit()

        self._task = asyncio.create_task(self._run_forever())

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _run_forever(self) -> None:
        while not self._stop_event.is_set():
            claimed = worker_tick(
                worker_id=self._worker_id,
                max_concurrent_jobs=self._config.max_concurrent_jobs,
                lease_ms=self._config.lease_ms,
            )

            # Fire-and-forget processors; DB status is already running.
            for job_id, project_id in claimed:
                asyncio.create_task(self._run_one(job_id=job_id, project_id=project_id))

            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=self._config.poll_interval_ms / 1000)
            except TimeoutError:
                continue

    async def _run_one(self, *, job_id: str, project_id: str) -> None:
        try:
            await self._processor.process(job_id=job_id, project_id=project_id)
        except Exception as e:  # pragma: no cover
            SessionLocal = get_sessionmaker()
            with SessionLocal() as session:
                mark_job_failed(
                    session,
                    job_id=job_id,
                    now_ms=_now_ms(),
                    error={"code": "JOB_STAGE_FAILED", "message": str(e)},
                )
                session.commit()

            GLOBAL_JOB_EVENT_BUS.emit_state(
                job_id=job_id,
                project_id=project_id,
                stage="ingest",
                message="status=failed",
            )
