from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import time
import uuid
import mimetypes
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from core.app.sse.event_bus import GLOBAL_JOB_EVENT_BUS
from core.app.logs.job_logs import append_job_log
from core.app.pipeline.analyze_provider import AnalyzeError
from core.app.pipeline.keyframes import extract_keyframes_at_times, map_keyframes_error
from core.app.pipeline.chunk_summaries import ensure_chunk_summaries, estimate_duration_ms, should_use_long_video_path
from core.app.pipeline.llm_plan import generate_plan, validate_plan
from core.app.pipeline.keyframe_verify import get_verify_budget, get_verify_mode, verify_and_maybe_adjust_plan_keyframes
from core.app.pipeline.transcribe_real import map_transcribe_error, run_real_transcribe
from core.contracts.error_codes import ErrorCode
from core.db.session import get_sessionmaker
from core.db.session import get_data_dir
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


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _abort_if_canceled(*, session: Session, job: Job, project_id: str, stage: str) -> bool:
    """Best-effort cancel check.

    Returns True when the job is canceled and processing should stop.
    """

    try:
        session.refresh(job)
    except Exception:
        # If refresh fails, keep going (best-effort).
        return False

    if job.status != "canceled":
        return False

    # Ensure we release the slot/lease.
    job.lease_expires_at_ms = None
    job.claimed_by = None
    job.claim_token = None
    job.updated_at_ms = _now_ms()
    session.add(job)
    session.commit()

    GLOBAL_JOB_EVENT_BUS.emit_state(
        job_id=job.job_id,
        project_id=project_id,
        stage=stage,
        message="status=canceled",
    )
    _log(job_id=job.job_id, project_id=project_id, stage=stage, level="info", message="job canceled; stopping pipeline")
    return True


def _recover_artifacts(*, session: Session, job: Job, project: Project) -> None:
    """Best-effort recovery of artifacts from DATA_DIR for resumability.

    This is used when a job failed or the app was interrupted mid-stage.
    It must be safe and idempotent.
    """

    data_dir = get_data_dir().resolve()

    # Recover downloaded media path for URL projects when project.source_path is missing.
    if (not isinstance(getattr(project, "source_path", None), str)) or not project.source_path:
        try:
            dl_dir = (data_dir / project.project_id / "downloads" / job.job_id).resolve()
            if dl_dir.is_relative_to(data_dir) and dl_dir.exists() and dl_dir.is_dir():
                candidates = [
                    p
                    for p in dl_dir.glob("source.*")
                    if p.is_file() and not p.name.endswith(".part") and p.stat().st_size > 0
                ]
                if candidates:
                    media_abs = sorted(candidates, key=lambda p: p.name)[0].resolve()
                    if media_abs.is_relative_to(data_dir):
                        project.source_path = media_abs.relative_to(data_dir).as_posix()
                        project.updated_at_ms = _now_ms()
                        session.add(project)
                        session.commit()
        except Exception:
            pass

    # Recover audio_ref/transcript from artifacts if DB fields are missing.
    try:
        artifacts_dir = (data_dir / project.project_id / "artifacts" / job.job_id).resolve()
        if artifacts_dir.is_relative_to(data_dir) and artifacts_dir.exists() and artifacts_dir.is_dir():
            # audio.wav
            if (not isinstance(getattr(job, "audio_ref", None), str)) or not job.audio_ref:
                audio_abs = (artifacts_dir / "audio.wav").resolve()
                if audio_abs.is_relative_to(data_dir) and audio_abs.exists() and audio_abs.is_file() and audio_abs.stat().st_size > 0:
                    job.audio_ref = audio_abs.relative_to(data_dir).as_posix()

            # transcript.json
            if job.transcript is None:
                tr_abs = (artifacts_dir / "transcript.json").resolve()
                if tr_abs.is_relative_to(data_dir) and tr_abs.exists() and tr_abs.is_file() and tr_abs.stat().st_size > 0:
                    raw = tr_abs.read_bytes()
                    obj = json.loads(raw.decode("utf-8"))
                    if isinstance(obj, dict):
                        job.transcript = obj
                        job.transcript_ref = tr_abs.relative_to(data_dir).as_posix()

                        meta = job.transcript_meta if isinstance(job.transcript_meta, dict) else {}
                        # Preserve existing meta where possible.
                        meta = dict(meta)
                        if "sha256" not in meta:
                            meta["sha256"] = _sha256_bytes(raw)
                        if "provider" not in meta:
                            meta["provider"] = obj.get("provider") or "unknown"
                        if "language" not in meta and obj.get("language"):
                            meta["language"] = obj.get("language")
                        if "audioRef" not in meta and isinstance(job.audio_ref, str) and job.audio_ref:
                            meta["audioRef"] = job.audio_ref
                        job.transcript_meta = meta

                        session.add(job)
                        session.commit()
    except Exception:
        pass


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
    # Common operator expectation: any non-zero integer means true.
    # This makes values like "2" behave as enabled.
    try:
        if raw.isdigit() and int(raw) != 0:
            return True
    except Exception:
        pass
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
        # Default behavior:
        # - Runtime (manual dev run): enable worker unless explicitly disabled.
        # - Pytest: disable by default to avoid background tasks affecting tests.
        default_enabled = not bool(os.environ.get("PYTEST_CURRENT_TEST"))
        return WorkerConfig(
            enabled=_env_bool("WORKER_ENABLE", default_enabled),
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

            # Best-effort recovery for resumability (e.g., failed/canceled->resume).
            _recover_artifacts(session=session, job=job, project=project)

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

                    # If user canceled while transcribe was running, stop before persisting/continuing.
                    if _abort_if_canceled(session=session, job=job, project_id=job.project_id, stage="speech_to_text"):
                        return

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
                if _abort_if_canceled(session=session, job=job, project_id=job.project_id, stage=job.stage):
                    return
                job.stage = "plan"
                job.progress = max(job.progress or 0.0, 0.6)
                job.updated_at_ms = _now_ms()
                session.add(job)
                session.commit()

                _log(job_id=job.job_id, project_id=job.project_id, stage=job.stage, level="info", message="plan started")
                GLOBAL_JOB_EVENT_BUS.emit_state(job_id=job.job_id, project_id=job.project_id, stage=job.stage, message="status=running")
                GLOBAL_JOB_EVENT_BUS.emit_progress(job_id=job.job_id, project_id=job.project_id, stage=job.stage, progress=job.progress, message="progress=0.6")

                llm_mode = (getattr(job, "llm_mode", None) or "backend").strip().lower()
                if llm_mode == "external":
                    external = getattr(job, "external_plan", None)
                    if not isinstance(external, dict):
                        # Release the worker slot and wait for an external plan submission.
                        now_ms = _now_ms()
                        job.status = "blocked"
                        job.stage = "plan"
                        job.progress = max(job.progress or 0.0, 0.6)
                        job.claimed_by = None
                        job.claim_token = None
                        job.lease_expires_at_ms = None
                        job.updated_at_ms = now_ms
                        session.add(job)
                        session.commit()

                        _log(
                            job_id=job.job_id,
                            project_id=job.project_id,
                            stage=job.stage,
                            level="info",
                            message="external plan required; job moved to blocked",
                        )
                        GLOBAL_JOB_EVENT_BUS.emit_state(
                            job_id=job.job_id,
                            project_id=job.project_id,
                            stage=job.stage,
                            message="status=blocked",
                        )
                        return

                    plan = validate_plan(external)
                    # Persist normalized plan for consistency.
                    job.external_plan = plan
                    job.updated_at_ms = _now_ms()
                    session.add(job)
                    session.commit()
                else:
                    transcript = job.transcript or {}
                    # Long-video routing: generate chunk summaries first, then let plan stage consume summaries (reduce).
                    segments_raw = transcript.get("segments") if isinstance(transcript, dict) else None
                    seg_dicts = [s for s in segments_raw if isinstance(s, dict)] if isinstance(segments_raw, list) else []
                    total_chars = 0
                    for s in seg_dicts:
                        t = s.get("text")
                        if isinstance(t, str):
                            total_chars += len(t)

                    # Prefer project.duration_ms / transcript_meta.durationMs; fall back to segment endMs.
                    duration_ms = project.duration_ms if isinstance(getattr(project, "duration_ms", None), int) and project.duration_ms else None
                    if duration_ms is None:
                        duration_ms = estimate_duration_ms(transcript=transcript, transcript_meta=job.transcript_meta)

                    use_long = should_use_long_video_path(duration_ms=duration_ms, segments=seg_dicts, total_chars=int(total_chars))

                    summaries: list[dict] | None = None
                    if use_long:
                        job.stage = "chunk_summaries"
                        job.progress = max(job.progress or 0.0, 0.55)
                        job.updated_at_ms = _now_ms()
                        session.add(job)
                        session.commit()

                        _log(job_id=job.job_id, project_id=job.project_id, stage=job.stage, level="info", message="chunk_summaries started")
                        GLOBAL_JOB_EVENT_BUS.emit_state(job_id=job.job_id, project_id=job.project_id, stage=job.stage, message="status=running")
                        GLOBAL_JOB_EVENT_BUS.emit_progress(job_id=job.job_id, project_id=job.project_id, stage=job.stage, progress=job.progress, message="progress=0.55")

                        summaries = ensure_chunk_summaries(
                            project_id=project.project_id,
                            job_id=job.job_id,
                            transcript=transcript,
                            transcript_meta=job.transcript_meta,
                            output_language=getattr(job, "output_language", None),
                            duration_ms=duration_ms,
                        )

                        job.progress = max(job.progress or 0.0, 0.6)
                        job.updated_at_ms = _now_ms()
                        session.add(job)
                        session.commit()
                        _log(job_id=job.job_id, project_id=job.project_id, stage=job.stage, level="info", message=f"chunk_summaries finished count={len(summaries or [])}")
                        GLOBAL_JOB_EVENT_BUS.emit_state(job_id=job.job_id, project_id=job.project_id, stage=job.stage, message="chunk_summaries=ready")
                        GLOBAL_JOB_EVENT_BUS.emit_progress(job_id=job.job_id, project_id=job.project_id, stage=job.stage, progress=job.progress, message="progress=0.6")

                        # Switch back to plan stage for reduce.
                        job.stage = "plan"
                        job.updated_at_ms = _now_ms()
                        session.add(job)
                        session.commit()

                        # IMPORTANT: When SSE is connected, the UI may rely on stage events rather than polling.
                        # Emit a stage update so the progress page can reflect that we're now in plan.
                        _log(job_id=job.job_id, project_id=job.project_id, stage=job.stage, level="info", message="plan started")
                        GLOBAL_JOB_EVENT_BUS.emit_state(job_id=job.job_id, project_id=job.project_id, stage=job.stage, message="status=running")
                        GLOBAL_JOB_EVENT_BUS.emit_progress(job_id=job.job_id, project_id=job.project_id, stage=job.stage, progress=job.progress, message="progress=0.6")

                    plan = generate_plan(
                        transcript=transcript,
                        summaries=summaries,
                        output_language=getattr(job, "output_language", None),
                    )

                    # Cache the validated plan for resumability (avoid re-calling LLM if later stages fail).
                    try:
                        job.external_plan = plan
                        job.updated_at_ms = _now_ms()
                        session.add(job)
                        session.commit()
                    except Exception:
                        pass
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
                if _abort_if_canceled(session=session, job=job, project_id=job.project_id, stage=job.stage):
                    return
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
                        kf_single = h.get("keyframe")
                        if isinstance(kf_single, dict):
                            tm = kf_single.get("timeMs")
                            if isinstance(tm, int):
                                times_ms.append(int(tm))

                        kfs = h.get("keyframes")
                        if isinstance(kfs, list):
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

                if _abort_if_canceled(session=session, job=job, project_id=job.project_id, stage="keyframes"):
                    return

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
                        # Backfill the legacy single keyframe too (keep in sync with keyframes list).
                        kf_single = h.get("keyframe")
                        if isinstance(kf_single, dict):
                            tm = kf_single.get("timeMs")
                            if isinstance(tm, int):
                                info = keyframes_artifacts.keyframes_by_time.get(int(tm))
                                if isinstance(info, dict):
                                    asset_id = info.get("assetId")
                                    if isinstance(asset_id, str) and asset_id:
                                        kf_single["assetId"] = asset_id
                                        kf_single["contentUrl"] = f"/api/v1/assets/{asset_id}/content"

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

                        # Keep legacy `keyframe` aligned with first keyframes[] item if present.
                        if isinstance(h.get("keyframes"), list) and h.get("keyframes"):
                            first = h.get("keyframes")[0]
                            if isinstance(first, dict):
                                h["keyframe"] = dict(first)

                # ---- Optional: keyframe verify / fallback ----
                verify_mode = get_verify_mode()
                if verify_mode != "off":
                    if _abort_if_canceled(session=session, job=job, project_id=job.project_id, stage=job.stage):
                        return
                    job.stage = "keyframe_verify"
                    job.progress = max(job.progress or 0.0, 0.975)
                    job.updated_at_ms = _now_ms()
                    session.add(job)
                    session.commit()

                    _log(job_id=job.job_id, project_id=job.project_id, stage=job.stage, level="info", message=f"keyframe_verify started mode={verify_mode}")
                    GLOBAL_JOB_EVENT_BUS.emit_state(job_id=job.job_id, project_id=job.project_id, stage=job.stage, message="status=running")
                    GLOBAL_JOB_EVENT_BUS.emit_progress(job_id=job.job_id, project_id=job.project_id, stage=job.stage, progress=job.progress, message="progress=0.975")

                    budget = get_verify_budget()
                    new_times, verified_count, dropped_count = verify_and_maybe_adjust_plan_keyframes(
                        session=session,
                        content_blocks=content_blocks,
                        output_language=getattr(job, "output_language", None),
                        mode=verify_mode,
                        budget=budget,
                    )

                    if new_times:
                        more = extract_keyframes_at_times(
                            session=session,
                            project=project,
                            job_id=job.job_id,
                            times_ms=new_times,
                            allow_skip_if_placeholder=True,
                            transcript_meta=job.transcript_meta,
                        )

                        # Merge artifacts
                        keyframes_artifacts.asset_refs.extend(list(more.asset_refs or []))
                        keyframes_artifacts.keyframes_by_time.update(dict(more.keyframes_by_time or {}))

                        # Backfill newly extracted asset refs.
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
                                if isinstance(h.get("keyframes"), list) and h.get("keyframes"):
                                    first = h.get("keyframes")[0]
                                    if isinstance(first, dict):
                                        h["keyframe"] = dict(first)

                    job.progress = max(job.progress or 0.0, 0.98)
                    job.updated_at_ms = _now_ms()
                    session.add(job)
                    session.commit()

                    _log(
                        job_id=job.job_id,
                        project_id=job.project_id,
                        stage=job.stage,
                        level="info",
                        message=f"keyframe_verify finished verified={verified_count} dropped={dropped_count} retried={len(new_times)}",
                    )
                    GLOBAL_JOB_EVENT_BUS.emit_state(job_id=job.job_id, project_id=job.project_id, stage=job.stage, message="keyframe_verify=done")
                    GLOBAL_JOB_EVENT_BUS.emit_progress(job_id=job.job_id, project_id=job.project_id, stage=job.stage, progress=job.progress, message="progress=0.98")

                # ---- Assemble Result ----
                if _abort_if_canceled(session=session, job=job, project_id=job.project_id, stage=job.stage):
                    return
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
                elif job.stage in {"plan", "highlights", "mindmap", "chunk_summaries", "keyframe_verify"} and isinstance(e, AnalyzeError):
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
            j = session.get(Job, job_id)
            if j is None:
                return
            # Do NOT overwrite user-initiated cancellation.
            if j.status == "canceled":
                j.lease_expires_at_ms = None
                j.claimed_by = None
                j.claim_token = None
                j.updated_at_ms = _now_ms()
                session.add(j)
                session.commit()
                return

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
