from __future__ import annotations

import base64
import json

from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.expression import cast
from sqlalchemy.types import String

from core.db.models.project import Project
from core.db.models.result import Result


def encode_search_cursor(*, updated_at_ms: int, project_id: str) -> str:
	payload = {"updatedAtMs": int(updated_at_ms), "projectId": str(project_id)}
	raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
	return base64.urlsafe_b64encode(raw).decode("ascii")


def decode_search_cursor(cursor: str) -> tuple[int, str] | None:
	try:
		raw = base64.urlsafe_b64decode(cursor.encode("ascii"))
		obj = json.loads(raw.decode("utf-8"))
		updated_at_ms = int(obj["updatedAtMs"])
		project_id = str(obj["projectId"])
		return updated_at_ms, project_id
	except Exception:
		return None


def search_projects_page(
	session: Session,
	*,
	query: str,
	limit: int,
	cursor: str | None,
) -> tuple[list[tuple[Project, Result | None]], str | None]:
	"""Search projects by title and latest result text.

	MVP behavior:
	- Search scope: project.title + latest result chapters/highlights/note JSON text.
	- Stable order: (projects.updated_at_ms desc, projects.project_id desc)
	- Cursor encodes last (updated_at_ms, project_id)
	"""

	q = (query or "").strip().lower()
	if not q:
		return [], None

	like = f"%{q}%"

	# Latest result only (join via projects.latest_result_id)
	stmt = (
		select(Project, Result)
		.outerjoin(Result, Result.result_id == Project.latest_result_id)
		.order_by(desc(Project.updated_at_ms), desc(Project.project_id))
	)

	# Coarse SQL filter; we refine in Python when mapping chapterId.
	stmt = stmt.where(
		or_(
			func.lower(func.coalesce(Project.title, "")).like(like),
			func.lower(func.coalesce(cast(Result.chapters, String), "")).like(like),
			func.lower(func.coalesce(cast(Result.highlights, String), "")).like(like),
			func.lower(func.coalesce(cast(Result.note, String), "")).like(like),
		)
	)

	if cursor:
		decoded = decode_search_cursor(cursor)
		if decoded is not None:
			updated_at_ms, project_id = decoded
			stmt = stmt.where(
				or_(
					Project.updated_at_ms < updated_at_ms,
					and_(Project.updated_at_ms == updated_at_ms, Project.project_id < project_id),
				)
			)

	rows = list(session.execute(stmt.limit(limit + 1)).all())
	if len(rows) <= limit:
		return [(p, r) for (p, r) in rows], None

	page = rows[:limit]
	last_project: Project = page[-1][0]
	next_cursor = encode_search_cursor(updated_at_ms=last_project.updated_at_ms, project_id=last_project.project_id)
	return [(p, r) for (p, r) in page], next_cursor
