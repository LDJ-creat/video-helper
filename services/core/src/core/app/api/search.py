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


def _find_anchor_for_match(*, query_lc: str, result: object) -> tuple[str | None, str | None]:
	if not query_lc:
		return None, None

	if not isinstance(result, dict):
		return None, None

	content_blocks = result.get("contentBlocks")
	if not isinstance(content_blocks, list):
		return None, None

	# Prefer highlight text hit (more precise anchor).
	for b in content_blocks:
		if not isinstance(b, dict):
			continue
		bid = b.get("blockId")
		if not isinstance(bid, str) or not bid:
			continue
		hls = b.get("highlights")
		if not isinstance(hls, list):
			continue
		for hl in hls:
			if not isinstance(hl, dict):
				continue
			hid = hl.get("highlightId")
			text = hl.get("text")
			if isinstance(hid, str) and hid and isinstance(text, str) and query_lc in text.lower():
				return bid, hid

	# Fallback: block title hit.
	for b in content_blocks:
		if not isinstance(b, dict):
			continue
		bid = b.get("blockId")
		if not isinstance(bid, str) or not bid:
			continue
		title = b.get("title")
		if isinstance(title, str) and query_lc in title.lower():
			return bid, None

	return None, None


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
		block_id = None
		highlight_id = None
		if result is not None:
			block_id, highlight_id = _find_anchor_for_match(
				query_lc=q_lc,
				result={
					"contentBlocks": getattr(result, "content_blocks", None),
				},
			)
		items.append(SearchItemDTO(projectId=project.project_id, blockId=block_id, highlightId=highlight_id))

	return SearchResponseDTO(items=items, nextCursor=next_cursor)
