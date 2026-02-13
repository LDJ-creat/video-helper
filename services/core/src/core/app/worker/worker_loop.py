from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
import mimetypes
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from core.app.sse.event_bus import GLOBAL_JOB_EVENT_BUS
from core.app.logs.job_logs import append_job_log
from core.app.pipeline.analyze_provider import AnalyzeError
from core.app.pipeline.keyframes import extract_keyframes_at_times, map_keyframes_error
from core.app.pipeline.llm_plan import generate_plan
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
from core.db.models.asset import Asset
from core.db.models.project import Project
from core.db.models.result import Result


logger = logging.getLogger(__name__)


def _now_ms() -> int:
    return int(time.time() * 1000)


def _log(*, job_id: str, project_id: str, stage: str, level: str, message: str) -> None:
    ts = _now_ms()
    append_job_log(job_id=job_id, ts_ms=ts, level=level, message=message, stage=stage)  # type: ignore[arg-type]
    # Also mirror to process logs for operator visibility.
    try:
        line = f"job_id={job_id} project_id={project_id} stage={stage} {message}"
        if level.lower() == "error":
            logger.error(line)
        elif level.lower() in {"warn", "warning"}:
            logger.warning(line)
        elif level.lower() == "debug":
            logger.debug(line)
        else:
            logger.info(line)
    except Exception:
        pass
    # Best-effort: also push to SSE stream
    try:
        GLOBAL_JOB_EVENT_BUS.emit_log(job_id=job_id, project_id=project_id, stage=stage, message=message)
    except Exception:
        return


def _compact_json(value: object, *, max_len: int = 2000) -> str:
    try:
        s = json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)
    except Exception:
        s = str(value)
    if len(s) > max_len:
        return s[:max_len] + "...(truncated)"
    return s


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


def _ensure_source_video_asset(*, session: Session, project: Project) -> str | None:
    """Best-effort: register the project's source media as an Asset.

    This enables the frontend video player to stream via /api/v1/assets/{assetId}/content.
    """

    rel = project.source_path
    if not isinstance(rel, str) or not rel:
        return None

    # Avoid duplicates: if we've already registered this file_path, reuse it.
    existing = (
        session.query(Asset)
        .filter(Asset.project_id == project.project_id, Asset.kind == "video", Asset.file_path == rel)
        .first()
    )
    if existing is not None:
        return existing.asset_id

    # Guess mime from extension; keep conservative fallback.
    mime, _ = mimetypes.guess_type(rel)
    if not mime:
        mime = "video/mp4"

    now_ms = _now_ms()
    asset_id = str(uuid.uuid4())
    session.add(
        Asset(
            asset_id=asset_id,
            project_id=project.project_id,
            kind="video",
            origin="generated",
            mime_type=mime,
            width=None,
            height=None,
            file_path=rel,
            chapter_id=None,
            time_ms=None,
            created_at_ms=now_ms,
        )
    )
    session.commit()
    return asset_id

class PipelineJobProcessor:
    """MVP pipeline runner for WT-BE-06.

    Executes:
            ingest → speech_to_text (public: transcribe) → plan (public: analyze)
                → keyframes (public: extract_keyframes) → assemble_result
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

            result_id: str | None = None

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

                # ---- Plan (LLM) ----
                job.stage = "plan"
                job.progress = max(job.progress or 0.0, 0.6)
                job.updated_at_ms = _now_ms()
                session.add(job)
                session.commit()

                _log(job_id=job.job_id, project_id=job.project_id, stage=job.stage, level="info", message="plan started")
                GLOBAL_JOB_EVENT_BUS.emit_state(job_id=job.job_id, project_id=job.project_id, stage=job.stage, message="status=running")
                GLOBAL_JOB_EVENT_BUS.emit_progress(job_id=job.job_id, project_id=job.project_id, stage=job.stage, progress=job.progress, message="progress=0.6")

                plan = generate_plan(transcript=job.transcript or {})
                content_blocks = plan.get("contentBlocks") if isinstance(plan, dict) else None
                mindmap = plan.get("mindmap") if isinstance(plan, dict) else None
                if not isinstance(content_blocks, list) or not isinstance(mindmap, dict):
                    raise ValueError("plan output invalid")

                # Recoverability anchor: persist a renderable Result snapshot right after plan.
                # This allows users to inspect LLM output even if later stages fail (e.g., ffmpeg keyframes).
                try:
                    snapshot_asset_refs: list[dict] = []
                    video_asset_id = _ensure_source_video_asset(session=session, project=project)
                    if video_asset_id:
                        snapshot_asset_refs.append({"assetId": video_asset_id, "kind": "video"})

                    result_id = assemble_result(
                        session,
                        project_id=project.project_id,
                        content_blocks=content_blocks,
                        mindmap=mindmap,
                        asset_refs=snapshot_asset_refs,
                        schema_version=plan.get("schemaVersion") if isinstance(plan.get("schemaVersion"), str) else "2026-02-06",
                        pipeline_version=os.environ.get("PIPELINE_VERSION") or "0",
                    )
                    _log(
                        job_id=job.job_id,
                        project_id=job.project_id,
                        stage=job.stage,
                        level="info",
                        message=f"result snapshot persisted result_id={result_id}",
                    )
                except Exception as e:
                    # Non-fatal for the pipeline: if snapshot persistence fails, continue;
                    # final assemble_result will still attempt to persist.
                    _log(
                        job_id=job.job_id,
                        project_id=job.project_id,
                        stage=job.stage,
                        level="warning",
                        message=f"result snapshot persist failed: {e}",
                    )

                job.progress = max(job.progress or 0.0, 0.9)
                job.updated_at_ms = _now_ms()
                session.add(job)
                session.commit()

                _log(job_id=job.job_id, project_id=job.project_id, stage=job.stage, level="info", message="plan finished")
                GLOBAL_JOB_EVENT_BUS.emit_state(job_id=job.job_id, project_id=job.project_id, stage=job.stage, message="plan=ready")
                GLOBAL_JOB_EVENT_BUS.emit_progress(job_id=job.job_id, project_id=job.project_id, stage=job.stage, progress=job.progress, message="progress=0.9")

                # ---- Keyframes (plan-driven) ----
                job.stage = "keyframes"
                job.progress = max(job.progress or 0.0, 0.96)
                job.updated_at_ms = _now_ms()
                session.add(job)
                session.commit()

                _log(job_id=job.job_id, project_id=job.project_id, stage=job.stage, level="info", message="extract_keyframes started")
                GLOBAL_JOB_EVENT_BUS.emit_state(job_id=job.job_id, project_id=job.project_id, stage=job.stage, message="status=running")
                GLOBAL_JOB_EVENT_BUS.emit_progress(job_id=job.job_id, project_id=job.project_id, stage=job.stage, progress=job.progress, message="progress=0.96")

                times_ms: list[int] = []
                for b in content_blocks:
                    if not isinstance(b, dict):
                        continue
                    hls = b.get("highlights")
                    if not isinstance(hls, list):
                        continue
                    for h in hls:
                        if not isinstance(h, dict):
                            continue
                        kfs = h.get("keyframes")
                        if not isinstance(kfs, list):
                            continue
                        for kf in kfs:
                            if not isinstance(kf, dict):
                                continue
                            tm = kf.get("timeMs")
                            if isinstance(tm, int):
                                times_ms.append(int(tm))

                keyframes_artifacts = extract_keyframes_at_times(
                    session=session,
                    project=project,
                    job_id=job.job_id,
                    times_ms=times_ms,
                    allow_skip_if_placeholder=True,
                    transcript_meta=job.transcript_meta,
                )

                # Backfill asset references into plan keyframes.
                for b in content_blocks:
                    if not isinstance(b, dict):
                        continue
                    hls = b.get("highlights")
                    if not isinstance(hls, list):
                        continue
                    for h in hls:
                        if not isinstance(h, dict):
                            continue
                        kfs = h.get("keyframes")
                        if not isinstance(kfs, list):
                            continue
                        for kf in kfs:
                            if not isinstance(kf, dict):
                                continue
                            tm = kf.get("timeMs")
                            if not isinstance(tm, int):
                                continue
                            info = keyframes_artifacts.keyframes_by_time.get(int(tm))
                            if not isinstance(info, dict):
                                continue
                            asset_id = info.get("assetId")
                            if isinstance(asset_id, str) and asset_id:
                                kf["assetId"] = asset_id
                                kf["contentUrl"] = f"/api/v1/assets/{asset_id}/content"

                # ---- Assemble Result ----
                job.stage = "assemble_result"
                job.progress = max(job.progress or 0.0, 0.99)
                job.updated_at_ms = _now_ms()
                session.add(job)
                session.commit()

                _log(job_id=job.job_id, project_id=job.project_id, stage=job.stage, level="info", message="assemble_result started")
                GLOBAL_JOB_EVENT_BUS.emit_state(job_id=job.job_id, project_id=job.project_id, stage=job.stage, message="status=running")
                GLOBAL_JOB_EVENT_BUS.emit_progress(job_id=job.job_id, project_id=job.project_id, stage=job.stage, progress=job.progress, message="progress=0.99")

                # Provide a playable source video asset to the frontend.
                # This is derived from project.source_path (downloaded via yt-dlp for URL sources).
                asset_refs = list(keyframes_artifacts.asset_refs or [])
                video_asset_id = _ensure_source_video_asset(session=session, project=project)
                if video_asset_id:
                    asset_refs.insert(0, {"assetId": video_asset_id, "kind": "video"})

                # Finalize: update the existing snapshot Result (if present), else create a new one.
                if result_id:
                    row = session.get(Result, result_id)
                    if row is None:
                        result_id = None

                if result_id:
                    row = session.get(Result, result_id)
                    if row is None:
                        raise AssembleResultError("result_not_found", "Result does not exist")

                    now_ms = _now_ms()
                    row.content_blocks = content_blocks
                    row.mindmap = mindmap
                    row.asset_refs = asset_refs or []
                    row.updated_at_ms = now_ms
                    flag_modified(row, "content_blocks")
                    flag_modified(row, "mindmap")
                    flag_modified(row, "asset_refs")
                    project.latest_result_id = result_id
                    project.updated_at_ms = now_ms
                    session.add(project)
                    session.commit()
                else:
                    assemble_result(
                        session,
                        project_id=project.project_id,
                        content_blocks=content_blocks,
                        mindmap=mindmap,
                        asset_refs=asset_refs,
                        schema_version=plan.get("schemaVersion") if isinstance(plan.get("schemaVersion"), str) else "2026-02-06",
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

                _log(
                    job_id=job.job_id,
                    project_id=job.project_id,
                    stage=job.stage,
                    level="error",
                    message=(
                        f"job failed code={error.get('code')} message={error.get('message')} "
                        f"details={_compact_json(error.get('details'))}"
                    ),
                )
                return
            except Exception as e:
                if job.stage == "speech_to_text":
                    error = map_transcribe_error(e)
                elif job.stage == "keyframes":
                    error = map_keyframes_error(e)
                elif job.stage == "assemble_result" and isinstance(e, AssembleResultError):
                    error = {"code": ErrorCode.JOB_STAGE_FAILED, "message": str(e), "details": {"reason": e.kind}}
                elif job.stage in {"plan", "highlights", "mindmap"} and isinstance(e, AnalyzeError):
                    error = e.to_error()
                else:
                    error = {"code": ErrorCode.JOB_STAGE_FAILED, "message": str(e), "details": {"reason": "unexpected"}}
                mark_job_failed(session, job_id=job.job_id, now_ms=_now_ms(), error=error)
                session.commit()

                GLOBAL_JOB_EVENT_BUS.emit_state(
                    job_id=job.job_id,
                    project_id=job.project_id,
                    stage=job.stage,
                    message="status=failed",
                )

                _log(
                    job_id=job.job_id,
                    project_id=job.project_id,
                    stage=job.stage,
                    level="error",
                    message=(
                        f"job failed code={error.get('code')} message={error.get('message')} "
                        f"details={_compact_json(error.get('details'))}"
                    ),
                )
                return

        # Mark succeeded after pipeline steps.
        SessionLocal = get_sessionmaker()
        with SessionLocal() as session:
            mark_job_succeeded(session, job_id=job_id, now_ms=_now_ms())
            session.commit()

        GLOBAL_JOB_EVENT_BUS.emit_state(
            job_id=job_id,
            project_id=project_id,
            stage="assemble_result",
            message="status=succeeded",
        )

        GLOBAL_JOB_EVENT_BUS.emit_progress(
            job_id=job_id,
            project_id=project_id,
            stage="assemble_result",
            progress=1.0,
            message="progress=1.0",
        )

        _log(job_id=job_id, project_id=project_id, stage="assemble_result", level="info", message="job succeeded")


class WorkerService:
    def __init__(self, *, config: WorkerConfig, processor: JobProcessor | None = None):
        self._config = config
        self._worker_id = f"worker-{uuid.uuid4()}"
        self._processor: JobProcessor = processor or PipelineJobProcessor()
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        if not self._config.enabled:
            logger.warning("Worker disabled (WORKER_ENABLE=0) - jobs will remain queued")
            return

        logger.info(
            "Worker starting: worker_id=%s max_concurrent_jobs=%s poll_interval_ms=%s lease_ms=%s",
            self._worker_id,
            self._config.max_concurrent_jobs,
            self._config.poll_interval_ms,
            self._config.lease_ms,
        )

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
