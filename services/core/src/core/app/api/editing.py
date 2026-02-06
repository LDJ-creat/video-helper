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
	result.note_json = note or {"type": "doc", "content": []}
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


def _find_block(content_blocks: list[dict], block_id: str) -> tuple[int, dict] | None:
	for idx, b in enumerate(content_blocks or []):
		if isinstance(b, dict) and b.get("blockId") == block_id:
			return idx, b
	return None


def _find_highlight(content_blocks: list[dict], highlight_id: str) -> tuple[dict, dict] | None:
	for b in content_blocks or []:
		if not isinstance(b, dict):
			continue
		hls = b.get("highlights")
		if not isinstance(hls, list):
			continue
		for h in hls:
			if isinstance(h, dict) and h.get("highlightId") == highlight_id:
				return b, h
	return None


def _env_bool(name: str, default: bool = False) -> bool:
	raw = (os.environ.get(name) or "").strip().lower()
	if raw in {"1", "true", "yes", "y", "on"}:
		return True
	if raw in {"0", "false", "no", "n", "off"}:
		return False
	return default


@router.patch("/projects/{projectId}/results/latest/blocks/{blockId}", response_model=UpdatedAtResponseDTO)
def edit_block(
	projectId: str,
	blockId: str,
	request: Request,
	payload: dict = Body(...),
	session: Session = Depends(get_db_session),
):
	result, err = _get_latest_result_or_error(project_id=projectId, request=request, session=session)
	if err is not None:
		return err

	content_blocks = result.content_blocks or []
	found = _find_block(content_blocks, blockId)
	if found is None:
		return JSONResponse(
			status_code=404,
			content=build_error_envelope(
				code=ErrorCode.CHAPTER_NOT_FOUND,
				message="Block does not exist",
				details={"blockId": blockId},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	_, block = found

	if "title" in payload:
		title = payload.get("title")
		if not _is_non_empty_str(title):
			return _validation_error(request=request, message="title must be a non-empty string")
		block["title"] = str(title).strip()
		flag_modified(result, "content_blocks")

	if "idx" in payload:
		new_idx = payload.get("idx")
		if not isinstance(new_idx, int) or new_idx < 0:
			return _validation_error(request=request, message="idx must be a non-negative integer")
		block["idx"] = int(new_idx)
		sorted_blocks = sorted(
			[(i, b) for i, b in enumerate(content_blocks) if isinstance(b, dict)],
			key=lambda t: (int(t[1].get("idx") if isinstance(t[1].get("idx"), int) else t[0]), t[0]),
		)
		content_blocks = [b for _, b in sorted_blocks]
		for i, b in enumerate(content_blocks):
			b["idx"] = i
		result.content_blocks = content_blocks
		flag_modified(result, "content_blocks")

	if "startMs" in payload or "endMs" in payload:
		if not _env_bool("ALLOW_CHAPTER_TIME_EDIT", default=False):
			return JSONResponse(
				status_code=400,
				content=build_error_envelope(
					code=ErrorCode.CHAPTER_TIME_EDIT_DISABLED,
					message="Block time editing is disabled",
					details={"blockId": blockId},
					request_id=getattr(request.state, "request_id", None),
				),
			)

		start_ms = payload.get("startMs", block.get("startMs"))
		end_ms = payload.get("endMs", block.get("endMs"))
		if not isinstance(start_ms, int) or not isinstance(end_ms, int):
			return _validation_error(request=request, message="startMs/endMs must be integers")
		if start_ms < 0 or end_ms <= start_ms:
			return _validation_error(request=request, message="startMs must be < endMs")
		block["startMs"] = int(start_ms)
		block["endMs"] = int(end_ms)
		flag_modified(result, "content_blocks")

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
				message="Failed to save block edits",
				details={"projectId": projectId, "blockId": blockId},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	resp = UpdatedAtResponseDTO(updatedAtMs=updated_at_ms)
	return JSONResponse(status_code=200, content=resp.model_dump(), headers={"ETag": _etag_for_updated_at(updated_at_ms)})


@router.put("/projects/{projectId}/results/latest/highlights/{highlightId}/keyframe", response_model=UpdatedAtResponseDTO)
def update_highlight_keyframe(
	projectId: str,
	highlightId: str,
	request: Request,
	payload: dict = Body(...),
	session: Session = Depends(get_db_session),
):
	result, err = _get_latest_result_or_error(project_id=projectId, request=request, session=session)
	if err is not None:
		return err

	content_blocks = result.content_blocks or []
	found = _find_highlight(content_blocks, highlightId)
	if found is None:
		return JSONResponse(
			status_code=404,
			content=build_error_envelope(
				code=ErrorCode.CHAPTER_NOT_FOUND,
				message="Highlight does not exist",
				details={"highlightId": highlightId},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	_, hl = found
	asset_id = payload.get("assetId")
	time_ms = payload.get("timeMs")
	caption = payload.get("caption")

	# Unbind keyframe when assetId is null.
	if asset_id is None:
		hl.pop("keyframe", None)
		flag_modified(result, "content_blocks")
	else:
		if not _is_non_empty_str(asset_id):
			return _validation_error(request=request, message="assetId must be a non-empty string")
		asset_id = str(asset_id)
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

		keyframe: dict = {"assetId": asset_id, "contentUrl": f"/api/v1/assets/{asset_id}/content"}
		if isinstance(time_ms, int):
			keyframe["timeMs"] = int(time_ms)
			asset.time_ms = int(time_ms)
		if _is_non_empty_str(caption):
			keyframe["caption"] = str(caption).strip()
		hl["keyframe"] = keyframe
		flag_modified(result, "content_blocks")

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
				message="Failed to update highlight keyframe",
				details={"projectId": projectId, "highlightId": highlightId},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	resp = UpdatedAtResponseDTO(updatedAtMs=updated_at_ms)
	return JSONResponse(status_code=200, content=resp.model_dump(), headers={"ETag": _etag_for_updated_at(updated_at_ms)})
