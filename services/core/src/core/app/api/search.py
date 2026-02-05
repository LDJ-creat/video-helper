from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from core.contracts.error_codes import ErrorCode
from core.contracts.error_envelope import build_error_envelope
from core.db.repositories.search import search_projects_page
from core.db.session import get_db_session
from core.schemas.search import SearchItemDTO, SearchResponseDTO


router = APIRouter(tags=["search"])


def _find_chapter_id_for_match(*, query_lc: str, result: object) -> str | None:
	if not query_lc:
		return None

	# Prefer a chapter hit from chapters[].title/summary.
	if isinstance(result, dict):
		chapters = result.get("chapters")
		if isinstance(chapters, list):
			for ch in chapters:
				if not isinstance(ch, dict):
					continue
				cid = ch.get("chapterId")
				if not isinstance(cid, str) or not cid:
					continue
				title = ch.get("title")
				summary = ch.get("summary")
				text = " ".join(
					[
						str(title) if isinstance(title, str) else "",
						str(summary) if isinstance(summary, str) else "",
					]
				).lower()
				if query_lc in text:
					return cid

		# Next, try highlights[].text and reuse highlight.chapterId.
		highlights = result.get("highlights")
		if isinstance(highlights, list):
			for hl in highlights:
				if not isinstance(hl, dict):
					continue
				cid = hl.get("chapterId")
				text = hl.get("text")
				if isinstance(cid, str) and cid and isinstance(text, str) and query_lc in text.lower():
					return cid

	return None


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
	items: list[SearchItemDTO] = []
	q_lc = q.lower()
	for project, result in rows:
		chapter_id = None
		if result is not None:
			chapter_id = _find_chapter_id_for_match(query_lc=q_lc, result={
				"chapters": getattr(result, "chapters", None),
				"highlights": getattr(result, "highlights", None),
			})
		items.append(SearchItemDTO(projectId=project.project_id, chapterId=chapter_id))

	return SearchResponseDTO(items=items, nextCursor=next_cursor)
