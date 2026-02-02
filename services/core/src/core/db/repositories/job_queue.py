from __future__ import annotations

import uuid

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from core.db.models.job import Job


def count_running_jobs(session: Session) -> int:
    return int(session.scalar(select(func.count()).select_from(Job).where(Job.status == "running")) or 0)


def requeue_running_jobs(session: Session, *, now_ms: int, reason: str = "restart") -> int:
    """Best-effort restart recovery.

    Strategy: mark all running jobs back to queued and clear claim/lease.

    We intentionally keep stage/progress/error as-is so clients can still
    display last-known state, and the pipeline can decide whether to resume
    or recompute.
    """

    res = session.execute(
        update(Job)
        .where(Job.status == "running")
        .values(
            status="queued",
            claimed_by=None,
            claim_token=None,
            lease_expires_at_ms=None,
            updated_at_ms=now_ms,
        )
    )
    # SQLAlchemy rowcount is best-effort for sqlite but good enough.
    return int(res.rowcount or 0)


def claim_next_queued_job(
    session: Session,
    *,
    worker_id: str,
    now_ms: int,
    lease_ms: int = 30_000,
    max_select_attempts: int = 10,
) -> Job | None:
    """Atomically claim a single queued job (best-effort).

    Implementation uses a SELECT candidate job_id then UPDATE with a status
    guard to avoid double-claiming.
    """

    for _ in range(max_select_attempts):
        job_id = session.scalar(
            select(Job.job_id)
            .where(Job.status == "queued")
            .order_by(Job.created_at_ms.asc(), Job.job_id.asc())
            .limit(1)
        )
        if job_id is None:
            return None

        token = str(uuid.uuid4())
        lease_expires_at_ms = now_ms + max(1, int(lease_ms))

        res = session.execute(
            update(Job)
            .where(Job.job_id == job_id)
            .where(Job.status == "queued")
            .values(
                status="running",
                claimed_by=worker_id,
                claim_token=token,
                lease_expires_at_ms=lease_expires_at_ms,
                started_at_ms=func.coalesce(Job.started_at_ms, now_ms),
                updated_at_ms=now_ms,
                attempt=Job.attempt + 1,
            )
        )
        if (res.rowcount or 0) == 1:
            session.flush()
            claimed = session.get(Job, job_id)
            return claimed

    return None


def mark_job_succeeded(session: Session, *, job_id: str, now_ms: int) -> None:
    job = session.get(Job, job_id)
    if job is None:
        return
    job.status = "succeeded"
    job.finished_at_ms = now_ms
    job.lease_expires_at_ms = None
    job.updated_at_ms = now_ms
    session.add(job)


def mark_job_failed(session: Session, *, job_id: str, now_ms: int, error: dict) -> None:
    job = session.get(Job, job_id)
    if job is None:
        return
    job.status = "failed"
    job.error = error
    job.finished_at_ms = now_ms
    job.lease_expires_at_ms = None
    job.updated_at_ms = now_ms
    session.add(job)
