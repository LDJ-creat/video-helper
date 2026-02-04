from __future__ import annotations

import asyncio
import os
import time
import uuid
from dataclasses import dataclass
from typing import Protocol

from core.app.sse.event_bus import GLOBAL_JOB_EVENT_BUS
from core.app.logs.job_logs import append_job_log
from core.app.pipeline.analyze_provider import AnalyzeError
from core.app.pipeline.highlights import generate_highlights
from core.app.pipeline.keyframes import extract_keyframes, map_keyframes_error
from core.app.pipeline.mindmap import generate_mindmap
from core.app.pipeline.segment import build_chapter_error, build_chapters_from_transcript
from core.app.pipeline.transcribe_real import map_transcribe_error, run_real_transcribe
from core.contracts.error_codes import ErrorCode
from core.db.session import get_sessionmaker
from core.pipeline.stages.assemble_result import AssembleResultError, assemble_result
from core.db.repositories.job_queue import (
    claim_next_queued_job,
    count_running_jobs,
    mark_job_failed,
    mark_job_succeeded,
    requeue_running_jobs,
)
from core.db.models.job import Job
from core.db.models.project import Project


def _now_ms() -> int:
    return int(time.time() * 1000)


def _log(*, job_id: str, project_id: str, stage: str, level: str, message: str) -> None:
    ts = _now_ms()
    append_job_log(job_id=job_id, ts_ms=ts, level=level, message=message, stage=stage)  # type: ignore[arg-type]
    # Best-effort: also push to SSE stream
    try:
        GLOBAL_JOB_EVENT_BUS.emit_log(job_id=job_id, project_id=project_id, stage=stage, message=message)
    except Exception:
        return


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

        _log(job_id=job_id, project_id=project_id, stage="ingest", level="info", message="noop job succeeded")


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


class PipelineJobProcessor:
    """MVP pipeline runner for WT-BE-06.

    Executes:
            ingest → speech_to_text (public: transcribe) → chapters (public: segment)
                → highlights/mindmap (public: analyze) → keyframes (public: extract_keyframes)
                → assemble_result
    """

    def __init__(self, *, default_duration_ms: int = 60_000):
        self._default_duration_ms = max(1, int(default_duration_ms))

    async def process(self, *, job_id: str, project_id: str) -> None:
        # Pipeline steps are synchronous and can be long-running (yt-dlp/ffmpeg/ASR).
        # Run them in a thread so the FastAPI event loop stays responsive.
        await asyncio.to_thread(self._process_sync, job_id=job_id, project_id=project_id)

    def _process_sync(self, *, job_id: str, project_id: str) -> None:
        SessionLocal = get_sessionmaker()
        with SessionLocal() as session:
            job = session.get(Job, job_id)
            project = session.get(Project, project_id)
            if job is None or project is None:
                return

            # If canceled mid-flight, respect it.
            if job.status == "canceled":
                job.lease_expires_at_ms = None
                job.updated_at_ms = _now_ms()
                session.add(job)
                session.commit()
                return

            try:
                # ---- Transcribe ----
                if job.transcript is None:
                    job.stage = "speech_to_text"
                    job.progress = 0.0
                    job.updated_at_ms = _now_ms()
                    session.add(job)
                    session.commit()

                    _log(job_id=job.job_id, project_id=job.project_id, stage=job.stage, level="info", message="transcribe started")

                    GLOBAL_JOB_EVENT_BUS.emit_state(
                        job_id=job.job_id,
                        project_id=job.project_id,
                        stage=job.stage,
                        message="status=running",
                    )
                    GLOBAL_JOB_EVENT_BUS.emit_progress(
                        job_id=job.job_id,
                        project_id=job.project_id,
                        stage=job.stage,
                        progress=job.progress,
                        message="progress=0.0",
                    )

                    def _progress_cb(value: float, msg: str) -> None:
                        # Keep progress in [0.0, 0.5] for transcribe stage.
                        try:
                            value = float(value)
                        except Exception:
                            return
                        value = max(0.0, min(0.5, value))
                        job.progress = max(job.progress or 0.0, value)
                        job.updated_at_ms = _now_ms()
                        session.add(job)
                        session.commit()
                        GLOBAL_JOB_EVENT_BUS.emit_progress(
                            job_id=job.job_id,
                            project_id=job.project_id,
                            stage=job.stage,
                            progress=job.progress,
                            message=msg,
                        )

                    def _log_cb(msg: str) -> None:
                        _log(job_id=job.job_id, project_id=job.project_id, stage=job.stage, level="info", message=msg)

                    duration_ms = project.duration_ms if isinstance(project.duration_ms, int) and project.duration_ms else None
                    if duration_ms is None:
                        duration_ms = self._default_duration_ms

                    artifacts = run_real_transcribe(
                        project=project,
                        job_id=job.job_id,
                        default_duration_ms=duration_ms,
                        progress_cb=_progress_cb,
                        log_cb=_log_cb,
                    )

                    if artifacts.updated_project_source_path and not project.source_path:
                        project.source_path = artifacts.updated_project_source_path
                        project.updated_at_ms = _now_ms()
                        session.add(project)

                    job.transcript = artifacts.transcript
                    job.audio_ref = artifacts.audio_ref
                    job.transcript_ref = artifacts.transcript_ref
                    job.transcript_meta = artifacts.transcript_meta
                    job.progress = 0.5
                    job.updated_at_ms = _now_ms()
                    session.add(job)
                    session.commit()

                    _log(job_id=job.job_id, project_id=job.project_id, stage=job.stage, level="info", message="transcribe finished")

                    GLOBAL_JOB_EVENT_BUS.emit_state(
                        job_id=job.job_id,
                        project_id=job.project_id,
                        stage=job.stage,
                        message="transcript=ready",
                    )
                    GLOBAL_JOB_EVENT_BUS.emit_progress(
                        job_id=job.job_id,
                        project_id=job.project_id,
                        stage=job.stage,
                        progress=job.progress,
                        message="progress=0.5",
                    )

                # ---- Segment ----
                if job.chapters is None:
                    job.stage = "chapters"
                    job.progress = max(job.progress or 0.0, 0.6)
                    job.updated_at_ms = _now_ms()
                    session.add(job)
                    session.commit()

                    _log(job_id=job.job_id, project_id=job.project_id, stage=job.stage, level="info", message="segment started")

                    GLOBAL_JOB_EVENT_BUS.emit_state(
                        job_id=job.job_id,
                        project_id=job.project_id,
                        stage=job.stage,
                        message="segment=running",
                    )
                    GLOBAL_JOB_EVENT_BUS.emit_progress(
                        job_id=job.job_id,
                        project_id=job.project_id,
                        stage=job.stage,
                        progress=job.progress,
                        message="progress=0.6",
                    )

                    chapters = build_chapters_from_transcript(job.transcript or {})
                    job.chapters = chapters
                    job.progress = 0.9
                    job.updated_at_ms = _now_ms()
                    session.add(job)
                    session.commit()

                    _log(job_id=job.job_id, project_id=job.project_id, stage=job.stage, level="info", message="segment finished")

                    GLOBAL_JOB_EVENT_BUS.emit_state(
                        job_id=job.job_id,
                        project_id=job.project_id,
                        stage=job.stage,
                        message="chapters=ready",
                    )
                    GLOBAL_JOB_EVENT_BUS.emit_progress(
                        job_id=job.job_id,
                        project_id=job.project_id,
                        stage=job.stage,
                        progress=job.progress,
                        message="progress=0.9",
                    )

                # ---- Analyze (highlights + mindmap) ----
                # Persisted in Result; we generate artifacts here.
                if job.chapters is not None:
                    chapters_payload = job.chapters.get("chapters") if isinstance(job.chapters, dict) else None
                    if not isinstance(chapters_payload, list):
                        raise ValueError("job.chapters.chapters must be a list")

                    job.stage = "highlights"
                    job.progress = max(job.progress or 0.0, 0.92)
                    job.updated_at_ms = _now_ms()
                    session.add(job)
                    session.commit()

                    _log(job_id=job.job_id, project_id=job.project_id, stage=job.stage, level="info", message="analyze(highlights) started")
                    GLOBAL_JOB_EVENT_BUS.emit_state(job_id=job.job_id, project_id=job.project_id, stage=job.stage, message="status=running")
                    GLOBAL_JOB_EVENT_BUS.emit_progress(job_id=job.job_id, project_id=job.project_id, stage=job.stage, progress=job.progress, message="progress=0.92")

                    highlights = generate_highlights(transcript=job.transcript or {}, chapters=chapters_payload)

                    job.stage = "mindmap"
                    job.progress = max(job.progress or 0.0, 0.94)
                    job.updated_at_ms = _now_ms()
                    session.add(job)
                    session.commit()

                    _log(job_id=job.job_id, project_id=job.project_id, stage=job.stage, level="info", message="analyze(mindmap) started")
                    GLOBAL_JOB_EVENT_BUS.emit_state(job_id=job.job_id, project_id=job.project_id, stage=job.stage, message="status=running")
                    GLOBAL_JOB_EVENT_BUS.emit_progress(job_id=job.job_id, project_id=job.project_id, stage=job.stage, progress=job.progress, message="progress=0.94")

                    mindmap = generate_mindmap(chapters=chapters_payload, highlights=highlights)

                    _log(job_id=job.job_id, project_id=job.project_id, stage=job.stage, level="info", message="analyze finished")

                    # ---- Keyframes ----
                    job.stage = "keyframes"
                    job.progress = max(job.progress or 0.0, 0.96)
                    job.updated_at_ms = _now_ms()
                    session.add(job)
                    session.commit()

                    _log(job_id=job.job_id, project_id=job.project_id, stage=job.stage, level="info", message="extract_keyframes started")
                    GLOBAL_JOB_EVENT_BUS.emit_state(job_id=job.job_id, project_id=job.project_id, stage=job.stage, message="status=running")
                    GLOBAL_JOB_EVENT_BUS.emit_progress(job_id=job.job_id, project_id=job.project_id, stage=job.stage, progress=job.progress, message="progress=0.96")

                    keyframes_artifacts = extract_keyframes(
                        session=session,
                        project=project,
                        job_id=job.job_id,
                        chapters=chapters_payload,
                        frames_per_chapter=_env_int("KEYFRAMES_PER_CHAPTER", 3),
                        allow_skip_if_placeholder=True,
                        transcript_meta=job.transcript_meta,
                    )

                    # Attach keyframes to chapter objects for Result rendering.
                    for ch in chapters_payload:
                        if not isinstance(ch, dict):
                            continue
                        cid = ch.get("chapterId")
                        if isinstance(cid, str) and cid in keyframes_artifacts.keyframes_by_chapter:
                            ch["keyframes"] = keyframes_artifacts.keyframes_by_chapter[cid]

                    # ---- Assemble Result ----
                    job.stage = "assemble_result"
                    job.progress = max(job.progress or 0.0, 0.99)
                    job.updated_at_ms = _now_ms()
                    session.add(job)
                    session.commit()

                    _log(job_id=job.job_id, project_id=job.project_id, stage=job.stage, level="info", message="assemble_result started")
                    GLOBAL_JOB_EVENT_BUS.emit_state(job_id=job.job_id, project_id=job.project_id, stage=job.stage, message="status=running")
                    GLOBAL_JOB_EVENT_BUS.emit_progress(job_id=job.job_id, project_id=job.project_id, stage=job.stage, progress=job.progress, message="progress=0.99")

                    assemble_result(
                        session,
                        project_id=project.project_id,
                        chapters=chapters_payload,
                        highlights=highlights,
                        mindmap=mindmap,
                        asset_refs=keyframes_artifacts.asset_refs,
                        pipeline_version=os.environ.get("PIPELINE_VERSION") or "0",
                    )

                    _log(job_id=job.job_id, project_id=job.project_id, stage=job.stage, level="info", message="assemble_result finished")

            except ValueError as e:
                error = (
                    map_transcribe_error(e)
                    if job.stage == "speech_to_text"
                    else map_keyframes_error(e)
                    if job.stage == "keyframes"
                    else {
                        "code": ErrorCode.JOB_STAGE_FAILED,
                        "message": str(e),
                        "details": {"reason": "invalid_input"},
                    }
                )
                mark_job_failed(session, job_id=job.job_id, now_ms=_now_ms(), error=error)
                session.commit()

                GLOBAL_JOB_EVENT_BUS.emit_state(
                    job_id=job.job_id,
                    project_id=job.project_id,
                    stage=job.stage,
                    message="status=failed",
                )

                _log(job_id=job.job_id, project_id=job.project_id, stage=job.stage, level="error", message=f"job failed: {e}")
                return
            except Exception as e:
                if job.stage == "speech_to_text":
                    error = map_transcribe_error(e)
                elif job.stage == "keyframes":
                    error = map_keyframes_error(e)
                elif job.stage == "assemble_result" and isinstance(e, AssembleResultError):
                    error = {"code": ErrorCode.JOB_STAGE_FAILED, "message": str(e), "details": {"reason": e.kind}}
                elif job.stage in {"highlights", "mindmap"} and isinstance(e, AnalyzeError):
                    error = e.to_error()
                else:
                    error = build_chapter_error(message=str(e), details={"reason": "unexpected"})
                mark_job_failed(session, job_id=job.job_id, now_ms=_now_ms(), error=error)
                session.commit()

                GLOBAL_JOB_EVENT_BUS.emit_state(
                    job_id=job.job_id,
                    project_id=job.project_id,
                    stage=job.stage,
                    message="status=failed",
                )

                _log(job_id=job.job_id, project_id=job.project_id, stage=job.stage, level="error", message="job failed")
                return

        # Mark succeeded after pipeline steps.
        SessionLocal = get_sessionmaker()
        with SessionLocal() as session:
            mark_job_succeeded(session, job_id=job_id, now_ms=_now_ms())
            session.commit()

        GLOBAL_JOB_EVENT_BUS.emit_state(
            job_id=job_id,
            project_id=project_id,
            stage="chapters",
            message="status=succeeded",
        )

        GLOBAL_JOB_EVENT_BUS.emit_progress(
            job_id=job_id,
            project_id=project_id,
            stage="chapters",
            progress=1.0,
            message="progress=1.0",
        )

        _log(job_id=job_id, project_id=project_id, stage="chapters", level="info", message="job succeeded")


class WorkerService:
    def __init__(self, *, config: WorkerConfig, processor: JobProcessor | None = None):
        self._config = config
        self._worker_id = f"worker-{uuid.uuid4()}"
        self._processor: JobProcessor = processor or PipelineJobProcessor()
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
