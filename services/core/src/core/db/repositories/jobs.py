from __future__ import annotations

from sqlalchemy.orm import Session

from core.db.models.job import Job


def get_job_by_id(session: Session, job_id: str) -> Job | None:
    return session.get(Job, job_id)
