from __future__ import annotations

import os
import time

from fastapi import APIRouter, Body, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from core.contracts.error_codes import ErrorCode
from core.contracts.error_envelope import build_error_envelope
from core.db.models.asset import Asset
from core.db.repositories.assets import get_asset_by_id
from core.db.repositories.projects import get_project_by_id
from core.db.repositories.results import get_result_by_id
from core.db.session import get_db_session
from core.schemas.editing import UpdatedAtResponseDTO


router = APIRouter(tags=["editing"])


def _now_ms() -> int:
	return int(time.time() * 1000)


def _etag_for_updated_at(updated_at_ms: int) -> str:
	return f'W/"{updated_at_ms}"'


def _get_latest_result_or_error(*, project_id: str, request: Request, session: Session):
	project = get_project_by_id(session, project_id)
	if project is None:
		return None, JSONResponse(
			status_code=404,
			content=build_error_envelope(
				code=ErrorCode.PROJECT_NOT_FOUND,
				message="Project does not exist",
				details={"projectId": project_id},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	if not project.latest_result_id:
		return None, JSONResponse(
			status_code=404,
			content=build_error_envelope(
				code=ErrorCode.RESULT_NOT_FOUND,
				message="Result does not exist",
				details={"projectId": project_id},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	result = get_result_by_id(session, project.latest_result_id)
	if result is None:
		return None, JSONResponse(
			status_code=404,
			content=build_error_envelope(
				code=ErrorCode.RESULT_NOT_FOUND,
				message="Result does not exist",
				details={"projectId": project_id},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	return result, None


def _validation_error(*, request: Request, message: str, details: dict | None = None) -> JSONResponse:
	return JSONResponse(
		status_code=400,
		content=build_error_envelope(
			code=ErrorCode.VALIDATION_ERROR,
			message=message,
			details=details,
			request_id=getattr(request.state, "request_id", None),
		),
	)


def _is_non_empty_str(v: object) -> bool:
	return isinstance(v, str) and bool(v.strip())


def _validate_note_payload(note: object) -> tuple[dict | None, str | None]:
	if not isinstance(note, dict):
		return None, "note must be an object"
	if not _is_non_empty_str(note.get("type")):
		return None, "note.type must be a non-empty string"
	content = note.get("content")
	if content is None:
		note["content"] = []
		return note, None
	if not isinstance(content, list):
		return None, "note.content must be an array"
	return note, None


def _validate_mindmap_payload(mindmap: object) -> tuple[dict | None, str | None, dict | None]:
	if not isinstance(mindmap, dict):
		return None, "mindmap must be an object", None
	nodes = mindmap.get("nodes")
	edges = mindmap.get("edges")
	if not isinstance(nodes, list):
		return None, "mindmap.nodes must be an array", {"field": "nodes"}
	if not isinstance(edges, list):
		return None, "mindmap.edges must be an array", {"field": "edges"}

	allowed_node_keys = {"id", "type", "label", "chapterId", "position", "data"}
	allowed_edge_keys = {"id", "source", "target", "label"}

	ids: list[str] = []
	for idx, n in enumerate(nodes):
		if not isinstance(n, dict):
			return None, "mindmap.nodes[*] must be objects", {"index": idx}
		nid = n.get("id")
		if not _is_non_empty_str(nid):
			return None, "mindmap.nodes[*].id must be a non-empty string", {"index": idx}
		if any((k not in allowed_node_keys) for k in n.keys()):
			bad = sorted([k for k in n.keys() if k not in allowed_node_keys])
			return None, "mindmap.nodes[*] contains unsupported fields", {"index": idx, "fields": bad}
		ids.append(str(nid))

	if len(ids) != len(set(ids)):
		return None, "mindmap.nodes[*].id must be unique", None

	ids_set = set(ids)
	for idx, e in enumerate(edges):
		if not isinstance(e, dict):
			return None, "mindmap.edges[*] must be objects", {"index": idx}
		eid = e.get("id")
		s = e.get("source")
		t = e.get("target")
		if not _is_non_empty_str(eid) or not _is_non_empty_str(s) or not _is_non_empty_str(t):
			return None, "mindmap.edges[*] must include id/source/target", {"index": idx}
		if any((k not in allowed_edge_keys) for k in e.keys()):
			bad = sorted([k for k in e.keys() if k not in allowed_edge_keys])
			return None, "mindmap.edges[*] contains unsupported fields", {"index": idx, "fields": bad}
		if str(s) not in ids_set or str(t) not in ids_set:
			return None, "mindmap.edges[*] must reference existing node ids", {"index": idx}

	return {"nodes": nodes, "edges": edges}, None, None


@router.put("/projects/{projectId}/results/latest/note", response_model=UpdatedAtResponseDTO)
def save_note(
	projectId: str,
	request: Request,
	payload: dict = Body(...),
	session: Session = Depends(get_db_session),
):
	result, err = _get_latest_result_or_error(project_id=projectId, request=request, session=session)
	if err is not None:
		return err

	note_raw = payload.get("note") if isinstance(payload, dict) else None
	if note_raw is None:
		note_raw = payload

	note, msg = _validate_note_payload(note_raw)
	if msg:
		return _validation_error(request=request, message=msg)

	updated_at_ms = _now_ms()
	result.note = note or {"type": "doc", "content": []}
	result.updated_at_ms = updated_at_ms
	try:
		session.commit()
	except Exception:
		session.rollback()
		return JSONResponse(
			status_code=500,
			content=build_error_envelope(
				code=ErrorCode.INTERNAL_ERROR,
				message="Failed to save note",
				details={"projectId": projectId},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	resp = UpdatedAtResponseDTO(updatedAtMs=updated_at_ms)
	return JSONResponse(status_code=200, content=resp.model_dump(), headers={"ETag": _etag_for_updated_at(updated_at_ms)})


@router.put("/projects/{projectId}/results/latest/mindmap", response_model=UpdatedAtResponseDTO)
def save_mindmap(
	projectId: str,
	request: Request,
	payload: dict = Body(...),
	session: Session = Depends(get_db_session),
):
	result, err = _get_latest_result_or_error(project_id=projectId, request=request, session=session)
	if err is not None:
		return err

	mindmap_raw = payload.get("mindmap") if isinstance(payload, dict) else None
	if mindmap_raw is None:
		mindmap_raw = payload

	mindmap, msg, details = _validate_mindmap_payload(mindmap_raw)
	if msg:
		return _validation_error(request=request, message=msg, details=details)

	updated_at_ms = _now_ms()
	result.mindmap = mindmap or {"nodes": [], "edges": []}
	result.updated_at_ms = updated_at_ms
	try:
		session.commit()
	except Exception:
		session.rollback()
		return JSONResponse(
			status_code=500,
			content=build_error_envelope(
				code=ErrorCode.INTERNAL_ERROR,
				message="Failed to save mindmap",
				details={"projectId": projectId},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	resp = UpdatedAtResponseDTO(updatedAtMs=updated_at_ms)
	return JSONResponse(status_code=200, content=resp.model_dump(), headers={"ETag": _etag_for_updated_at(updated_at_ms)})


def _find_chapter(chapters: list[dict], chapter_id: str) -> tuple[int, dict] | None:
	for idx, ch in enumerate(chapters or []):
		if isinstance(ch, dict) and ch.get("chapterId") == chapter_id:
			return idx, ch
	return None


def _env_bool(name: str, default: bool = False) -> bool:
	raw = (os.environ.get(name) or "").strip().lower()
	if raw in {"1", "true", "yes", "y", "on"}:
		return True
	if raw in {"0", "false", "no", "n", "off"}:
		return False
	return default


@router.patch("/projects/{projectId}/results/latest/chapters/{chapterId}", response_model=UpdatedAtResponseDTO)
def edit_chapter(
	projectId: str,
	chapterId: str,
	request: Request,
	payload: dict = Body(...),
	session: Session = Depends(get_db_session),
):
	result, err = _get_latest_result_or_error(project_id=projectId, request=request, session=session)
	if err is not None:
		return err

	chapters = result.chapters or []
	found = _find_chapter(chapters, chapterId)
	if found is None:
		return JSONResponse(
			status_code=404,
			content=build_error_envelope(
				code=ErrorCode.CHAPTER_NOT_FOUND,
				message="Chapter does not exist",
				details={"chapterId": chapterId},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	_, chapter = found

	if "title" in payload:
		title = payload.get("title")
		if not _is_non_empty_str(title):
			return _validation_error(request=request, message="title must be a non-empty string")
		chapter["title"] = str(title).strip()
		flag_modified(result, "chapters")

	if "idx" in payload:
		new_idx = payload.get("idx")
		if not isinstance(new_idx, int) or new_idx < 0:
			return _validation_error(request=request, message="idx must be a non-negative integer")
		chapter["idx"] = int(new_idx)
		sorted_ch = sorted(
			[(i, c) for i, c in enumerate(chapters) if isinstance(c, dict)],
			key=lambda t: (int(t[1].get("idx") if isinstance(t[1].get("idx"), int) else t[0]), t[0]),
		)
		chapters = [c for _, c in sorted_ch]
		for i, c in enumerate(chapters):
			c["idx"] = i
		result.chapters = chapters
		flag_modified(result, "chapters")

	if "startMs" in payload or "endMs" in payload:
		if not _env_bool("ALLOW_CHAPTER_TIME_EDIT", default=False):
			return JSONResponse(
				status_code=400,
				content=build_error_envelope(
					code=ErrorCode.CHAPTER_TIME_EDIT_DISABLED,
					message="Chapter time editing is disabled",
					details={"chapterId": chapterId},
					request_id=getattr(request.state, "request_id", None),
				),
			)

		start_ms = payload.get("startMs", chapter.get("startMs"))
		end_ms = payload.get("endMs", chapter.get("endMs"))
		if not isinstance(start_ms, int) or not isinstance(end_ms, int):
			return _validation_error(request=request, message="startMs/endMs must be integers")
		if start_ms < 0 or end_ms <= start_ms:
			return _validation_error(request=request, message="startMs must be < endMs")
		chapter["startMs"] = int(start_ms)
		chapter["endMs"] = int(end_ms)
		flag_modified(result, "chapters")

		ordered = sorted(
			[c for c in (result.chapters or []) if isinstance(c, dict)],
			key=lambda c: int(c.get("idx") if isinstance(c.get("idx"), int) else 0),
		)
		prev_end: int | None = None
		for c in ordered:
			s = c.get("startMs")
			e = c.get("endMs")
			if not isinstance(s, int) or not isinstance(e, int) or e <= s:
				return _validation_error(request=request, message="invalid chapter time ranges")
			if prev_end is not None and s < prev_end:
				return JSONResponse(
					status_code=400,
					content=build_error_envelope(
						code=ErrorCode.CHAPTER_OVERLAP,
						message="Chapters must not overlap",
						details={"chapterId": chapterId},
						request_id=getattr(request.state, "request_id", None),
					),
				)
			prev_end = e

	updated_at_ms = _now_ms()
	result.updated_at_ms = updated_at_ms
	try:
		session.commit()
	except Exception:
		session.rollback()
		return JSONResponse(
			status_code=500,
			content=build_error_envelope(
				code=ErrorCode.INTERNAL_ERROR,
				message="Failed to save chapter edits",
				details={"projectId": projectId, "chapterId": chapterId},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	resp = UpdatedAtResponseDTO(updatedAtMs=updated_at_ms)
	return JSONResponse(status_code=200, content=resp.model_dump(), headers={"ETag": _etag_for_updated_at(updated_at_ms)})


@router.put("/projects/{projectId}/results/latest/chapters/{chapterId}/keyframes", response_model=UpdatedAtResponseDTO)
def update_chapter_keyframes(
	projectId: str,
	chapterId: str,
	request: Request,
	payload: dict = Body(...),
	session: Session = Depends(get_db_session),
):
	result, err = _get_latest_result_or_error(project_id=projectId, request=request, session=session)
	if err is not None:
		return err

	chapters = result.chapters or []
	found = _find_chapter(chapters, chapterId)
	if found is None:
		return JSONResponse(
			status_code=404,
			content=build_error_envelope(
				code=ErrorCode.CHAPTER_NOT_FOUND,
				message="Chapter does not exist",
				details={"chapterId": chapterId},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	_, chapter = found
	items = payload.get("keyframes")
	if not isinstance(items, list):
		return _validation_error(request=request, message="keyframes must be an array")

	new_keyframes: list[dict] = []
	seen: set[str] = set()
	for i, it in enumerate(items):
		if isinstance(it, str):
			asset_id = it
			time_ms = None
			caption = None
		elif isinstance(it, dict):
			asset_id = it.get("assetId")
			time_ms = it.get("timeMs")
			caption = it.get("caption")
		else:
			return _validation_error(request=request, message="keyframes[*] must be string or object", details={"index": i})

		if not _is_non_empty_str(asset_id):
			return _validation_error(request=request, message="assetId must be a non-empty string", details={"index": i})
		asset_id = str(asset_id)
		if asset_id in seen:
			continue
		seen.add(asset_id)

		asset = get_asset_by_id(session, asset_id)
		if asset is None:
			return JSONResponse(
				status_code=404,
				content=build_error_envelope(
					code=ErrorCode.ASSET_NOT_FOUND,
					message="Asset does not exist",
					details={"assetId": asset_id},
					request_id=getattr(request.state, "request_id", None),
				),
			)
		if asset.project_id != projectId:
			return JSONResponse(
				status_code=400,
				content=build_error_envelope(
					code=ErrorCode.ASSET_NOT_IN_PROJECT,
					message="Asset does not belong to project",
					details={"assetId": asset_id, "projectId": projectId},
					request_id=getattr(request.state, "request_id", None),
				),
			)

		kf: dict = {"assetId": asset_id, "idx": len(new_keyframes)}
		if isinstance(time_ms, int):
			kf["timeMs"] = int(time_ms)
		if _is_non_empty_str(caption):
			kf["caption"] = str(caption).strip()
		new_keyframes.append(kf)

		asset.chapter_id = chapterId
		if isinstance(time_ms, int):
			asset.time_ms = int(time_ms)

	prev_asset_ids: set[str] = set()
	prev = chapter.get("keyframes")
	if isinstance(prev, list):
		for it in prev:
			if isinstance(it, dict) and _is_non_empty_str(it.get("assetId")):
				prev_asset_ids.add(str(it.get("assetId")))

	removed = prev_asset_ids - {kf["assetId"] for kf in new_keyframes}
	if removed:
		for aid in removed:
			asset = get_asset_by_id(session, aid)
			if asset is not None and asset.project_id == projectId and asset.chapter_id == chapterId:
				asset.chapter_id = None

	chapter["keyframes"] = new_keyframes
	flag_modified(result, "chapters")

	refs = result.asset_refs or []
	ref_ids = {r.get("assetId") for r in refs if isinstance(r, dict)}
	for kf in new_keyframes:
		aid = kf.get("assetId")
		if aid and aid not in ref_ids:
			asset = get_asset_by_id(session, str(aid))
			kind = asset.kind if isinstance(asset, Asset) else "screenshot"
			refs.append({"assetId": str(aid), "kind": str(kind)})
			ref_ids.add(aid)
	result.asset_refs = refs
	flag_modified(result, "asset_refs")

	updated_at_ms = _now_ms()
	result.updated_at_ms = updated_at_ms
	try:
		session.commit()
	except Exception:
		session.rollback()
		return JSONResponse(
			status_code=500,
			content=build_error_envelope(
				code=ErrorCode.INTERNAL_ERROR,
				message="Failed to update keyframes",
				details={"projectId": projectId, "chapterId": chapterId},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	resp = UpdatedAtResponseDTO(updatedAtMs=updated_at_ms)
	return JSONResponse(status_code=200, content=resp.model_dump(), headers={"ETag": _etag_for_updated_at(updated_at_ms)})
