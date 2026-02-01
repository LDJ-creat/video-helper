from __future__ import annotations

from sqlalchemy.orm import Session

from core.db.models.project import Project


def get_project_by_id(session: Session, project_id: str) -> Project | None:
    return session.get(Project, project_id)
