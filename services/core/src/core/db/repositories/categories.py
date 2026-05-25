from __future__ import annotations

import re
import time
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core.db.constants.categories import (
    CATEGORY_NAME_MAX_LEN,
    CATEGORY_NAME_MIN_LEN,
    DEFAULT_CATEGORY_ID,
    DEFAULT_CATEGORY_NAME,
    DEFAULT_CATEGORY_SLUG,
)
from core.db.models.project import Project
from core.db.models.project_category import ProjectCategory


class CategoryNameValidationError(ValueError):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


def _now_ms() -> int:
    return int(time.time() * 1000)


def normalize_category_name(name: str) -> str:
    normalized = (name or "").strip()
    if len(normalized) < CATEGORY_NAME_MIN_LEN:
        raise CategoryNameValidationError("empty")
    if len(normalized) > CATEGORY_NAME_MAX_LEN:
        raise CategoryNameValidationError("too_long")
    return normalized


def _user_slug(name: str) -> str:
    base = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "-", name.strip().lower()).strip("-")
    if not base:
        base = "category"
    return f"user-{base}-{uuid.uuid4().hex[:8]}"


def ensure_default_category(session: Session) -> ProjectCategory:
    existing = session.get(ProjectCategory, DEFAULT_CATEGORY_ID)
    now_ms = _now_ms()
    if existing is not None:
        return existing

    row = ProjectCategory(
        category_id=DEFAULT_CATEGORY_ID,
        name=DEFAULT_CATEGORY_NAME,
        slug=DEFAULT_CATEGORY_SLUG,
        is_system=True,
        created_at_ms=now_ms,
        updated_at_ms=now_ms,
    )
    session.add(row)
    session.flush()
    return row


def backfill_projects_default_category(session: Session) -> int:
    default_id = DEFAULT_CATEGORY_ID
    result = session.execute(
        select(Project).where(Project.category_id.is_(None))
    )
    projects = list(result.scalars().all())
    for project in projects:
        project.category_id = default_id
        session.add(project)
    return len(projects)


def resolve_category_id(session: Session, requested: str | None) -> str:
    ensure_default_category(session)
    if not requested or not str(requested).strip():
        return DEFAULT_CATEGORY_ID
    category = get_category_by_id(session, str(requested).strip())
    if category is None:
        raise CategoryNameValidationError("not_found")
    return category.category_id


def get_category_by_id(session: Session, category_id: str) -> ProjectCategory | None:
    return session.get(ProjectCategory, category_id)


def get_category_by_name(session: Session, name: str) -> ProjectCategory | None:
    normalized = normalize_category_name(name)
    return session.execute(
        select(ProjectCategory).where(ProjectCategory.name == normalized)
    ).scalar_one_or_none()


def list_categories(session: Session) -> list[tuple[ProjectCategory, int]]:
    counts = dict(
        session.execute(
            select(Project.category_id, func.count())
            .where(Project.category_id.is_not(None))
            .group_by(Project.category_id)
        ).all()
    )
    rows = list(
        session.execute(
            select(ProjectCategory).order_by(
                ProjectCategory.is_system.desc(),
                ProjectCategory.name.asc(),
            )
        ).scalars().all()
    )
    return [(row, int(counts.get(row.category_id, 0))) for row in rows]


def create_category(session: Session, *, name: str) -> ProjectCategory:
    normalized = normalize_category_name(name)
    if get_category_by_name(session, normalized) is not None:
        raise CategoryNameValidationError("conflict")

    now_ms = _now_ms()
    row = ProjectCategory(
        category_id=str(uuid.uuid4()),
        name=normalized,
        slug=_user_slug(normalized),
        is_system=False,
        created_at_ms=now_ms,
        updated_at_ms=now_ms,
    )
    session.add(row)
    session.flush()
    return row


def update_category_name(session: Session, category: ProjectCategory, *, name: str) -> ProjectCategory:
    normalized = normalize_category_name(name)
    existing = get_category_by_name(session, normalized)
    if existing is not None and existing.category_id != category.category_id:
        raise CategoryNameValidationError("conflict")

    category.name = normalized
    category.updated_at_ms = _now_ms()
    session.add(category)
    session.flush()
    return category


def count_projects_in_category(session: Session, category_id: str) -> int:
    return int(
        session.execute(
            select(func.count()).select_from(Project).where(Project.category_id == category_id)
        ).scalar_one()
    )


def delete_category(session: Session, category: ProjectCategory) -> None:
    session.delete(category)


def get_category_names_by_ids(session: Session, category_ids: set[str]) -> dict[str, tuple[str, str]]:
    if not category_ids:
        return {}
    rows = session.execute(
        select(ProjectCategory.category_id, ProjectCategory.name, ProjectCategory.slug).where(
            ProjectCategory.category_id.in_(category_ids)
        )
    ).all()
    return {row[0]: (row[1], row[2]) for row in rows}
