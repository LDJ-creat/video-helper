from __future__ import annotations

import base64
import json

from sqlalchemy import and_, desc, or_, select
from sqlalchemy.orm import Session

from core.db.models.project import Project


def get_project_by_id(session: Session, project_id: str) -> Project | None:
    return session.get(Project, project_id)


def encode_projects_cursor(*, updated_at_ms: int, project_id: str) -> str:
    payload = {"updatedAtMs": int(updated_at_ms), "projectId": str(project_id)}
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii")


def decode_projects_cursor(cursor: str) -> tuple[int, str] | None:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode("ascii"))
        obj = json.loads(raw.decode("utf-8"))
        updated_at_ms = int(obj["updatedAtMs"])
        project_id = str(obj["projectId"])
        return updated_at_ms, project_id
    except Exception:
        return None


def list_projects_page(
    session: Session,
    *,
    limit: int,
    cursor: str | None,
) -> tuple[list[Project], str | None]:
    """List projects ordered by (updated_at_ms desc, project_id desc).

    Cursor is opaque and encodes last item's (updated_at_ms, project_id).
    """

    stmt = select(Project).order_by(desc(Project.updated_at_ms), desc(Project.project_id))

    if cursor:
        decoded = decode_projects_cursor(cursor)
        if decoded is not None:
            updated_at_ms, project_id = decoded
            stmt = stmt.where(
                or_(
                    Project.updated_at_ms < updated_at_ms,
                    and_(Project.updated_at_ms == updated_at_ms, Project.project_id < project_id),
                )
            )

    rows = list(session.execute(stmt.limit(limit + 1)).scalars().all())
    if len(rows) <= limit:
        return rows, None

    page = rows[:limit]
    last = page[-1]
    next_cursor = encode_projects_cursor(updated_at_ms=last.updated_at_ms, project_id=last.project_id)
    return page, next_cursor
