from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from core.contracts.error_codes import ErrorCode
from core.contracts.error_envelope import build_error_envelope
from core.db.repositories.categories import get_category_names_by_ids
from core.db.repositories.search import search_projects_page
from core.db.session import get_db_session
from core.schemas.search import SearchItemDTO, SearchResponseDTO


router = APIRouter(tags=["search"])


@router.get("/search", response_model=SearchResponseDTO)
def search(
	request: Request,
	query: str,
	limit: int = 20,
	cursor: str | None = None,
	session: Session = Depends(get_db_session),
):
	q = (query or "").strip()
	if not q:
		return JSONResponse(
			status_code=400,
			content=build_error_envelope(
				code=ErrorCode.VALIDATION_ERROR,
				message="Query must be non-empty",
				details={"reason": "invalid_query"},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	if limit < 1:
		limit = 1
	if limit > 200:
		limit = 200

	rows, next_cursor = search_projects_page(session, query=q, limit=limit, cursor=cursor)
	category_ids = {p.category_id for p, _ in rows if p.category_id}
	category_meta = get_category_names_by_ids(session, category_ids)

	items: list[SearchItemDTO] = []
	for project, _result in rows:
		cat_name: str | None = None
		cat_slug: str | None = None
		if project.category_id and project.category_id in category_meta:
			cat_name, cat_slug = category_meta[project.category_id]
		items.append(
			SearchItemDTO(
				projectId=project.project_id,
				title=project.title,
				sourceType=project.source_type,
				updatedAtMs=project.updated_at_ms,
				categoryId=project.category_id,
				categoryName=cat_name,
				categorySlug=cat_slug,
			)
		)

	return SearchResponseDTO(items=items, nextCursor=next_cursor)
