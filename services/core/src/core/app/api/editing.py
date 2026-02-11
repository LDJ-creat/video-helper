from __future__ import annotations

import os
import time
import uuid
from pathlib import Path

from fastapi import APIRouter, Body, Depends, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from core.contracts.error_codes import ErrorCode
from core.contracts.error_envelope import build_error_envelope
from core.db.models.asset import Asset
from core.db.repositories.assets import get_asset_by_id
from core.db.repositories.projects import get_project_by_id
from core.db.repositories.results import get_result_by_id
from core.db.session import get_data_dir, get_db_session
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



def _validate_mindmap_payload(mindmap: object) -> tuple[dict | None, str | None, dict | None]:
	if not isinstance(mindmap, dict):
		return None, "mindmap must be an object", None
	nodes = mindmap.get("nodes")
	edges = mindmap.get("edges")
	if not isinstance(nodes, list):
		return None, "mindmap.nodes must be an array", {"field": "nodes"}
	if not isinstance(edges, list):
		return None, "mindmap.edges must be an array", {"field": "edges"}

	allowed_node_keys = {"id", "type", "label", "level", "position", "data"}
	allowed_edge_keys = {"id", "source", "target", "label"}
	valid_node_types = {"root", "topic", "detail"}
	valid_levels = {0, 1, 2}

	ids: list[str] = []
	for idx, n in enumerate(nodes):
		if not isinstance(n, dict):
			return None, "mindmap.nodes[*] must be objects", {"index": idx}
		nid = n.get("id")
		if not _is_non_empty_str(nid):
			return None, "mindmap.nodes[*].id must be a non-empty string", {"index": idx}
		ntype = n.get("type")
		if ntype is not None and ntype not in valid_node_types:
			return None, f"mindmap.nodes[*].type must be one of {sorted(valid_node_types)}", {"index": idx}
		nlevel = n.get("level")
		if nlevel is not None and nlevel not in valid_levels:
			return None, "mindmap.nodes[*].level must be 0, 1, or 2", {"index": idx}
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


@router.put("/projects/{projectId}/results/latest/content-blocks", response_model=UpdatedAtResponseDTO)
def save_content_blocks(
	projectId: str,
	request: Request,
	payload: dict = Body(...),
	session: Session = Depends(get_db_session),
):
	"""Full-array overwrite of contentBlocks (used by NoteEditor autosave)."""
	result, err = _get_latest_result_or_error(project_id=projectId, request=request, session=session)
	if err is not None:
		return err

	blocks = payload.get("contentBlocks") if isinstance(payload, dict) else None
	if blocks is None:
		blocks = payload if isinstance(payload, list) else None
	if not isinstance(blocks, list):
		return _validation_error(request=request, message="contentBlocks must be an array")

	# Minimal validation: each block must be a dict with blockId
	for idx, b in enumerate(blocks):
		if not isinstance(b, dict):
			return _validation_error(request=request, message=f"contentBlocks[{idx}] must be an object")
		if not _is_non_empty_str(b.get("blockId")):
			return _validation_error(request=request, message=f"contentBlocks[{idx}].blockId must be a non-empty string")

	updated_at_ms = _now_ms()
	result.content_blocks = blocks
	result.updated_at_ms = updated_at_ms
	flag_modified(result, "content_blocks")
	try:
		session.commit()
	except Exception:
		session.rollback()
		return JSONResponse(
			status_code=500,
			content=build_error_envelope(
				code=ErrorCode.INTERNAL_ERROR,
				message="Failed to save content blocks",
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


@router.put("/projects/{projectId}/results/latest/highlights/{highlightId}/keyframes", response_model=UpdatedAtResponseDTO)
def update_highlight_keyframes(
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
	keyframes_raw = payload.get("keyframes")

	if keyframes_raw is None:
		# If keyframes is explicitly null/missing, we might clear it?
		# Or if it's an empty list.
		# Let's assume partial update? No, PUT usually replaces.
		# If keyframes is None, we clear.
		hl["keyframes"] = []
		hl.pop("keyframe", None) # Clear legacy
		flag_modified(result, "content_blocks")
	else:
		if not isinstance(keyframes_raw, list):
			return _validation_error(request=request, message="keyframes must be a list")
		
		valid_keyframes = []
		for idx, kf in enumerate(keyframes_raw):
			if not isinstance(kf, dict):
				return _validation_error(request=request, message=f"keyframes[{idx}] must be an object")
			
			asset_id = kf.get("assetId")
			if not _is_non_empty_str(asset_id):
				return _validation_error(request=request, message=f"keyframes[{idx}].assetId must be a non-empty string")
			
			asset_id = str(asset_id)
			asset = get_asset_by_id(session, asset_id)
			if asset is None:
				return JSONResponse(
					status_code=404,
					content=build_error_envelope(
						code=ErrorCode.ASSET_NOT_FOUND,
						message="Asset does not exist",
						details={"assetId": asset_id, "index": idx},
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
			
			time_ms = kf.get("timeMs")
			caption = kf.get("caption")
			
			new_kf = {"assetId": asset_id, "contentUrl": f"/api/v1/assets/{asset_id}/content"}
			if isinstance(time_ms, int):
				new_kf["timeMs"] = int(time_ms)
			if _is_non_empty_str(caption):
				new_kf["caption"] = str(caption).strip()
			
			valid_keyframes.append(new_kf)

		hl["keyframes"] = valid_keyframes
		hl.pop("keyframe", None) # Cleanup legacy
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
				message="Failed to update highlight keyframes",
				details={"projectId": projectId, "highlightId": highlightId},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	resp = UpdatedAtResponseDTO(updatedAtMs=updated_at_ms)
	return JSONResponse(status_code=200, content=resp.model_dump(), headers={"ETag": _etag_for_updated_at(updated_at_ms)})


_ALLOWED_IMAGE_MIMES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
_ALLOWED_UPLOAD_KINDS = {"user_image", "screenshot", "cover"}


@router.post("/projects/{projectId}/assets")
async def upload_asset(
	projectId: str,
	request: Request,
	file: UploadFile = File(...),
	kind: str = Form("user_image"),
	session: Session = Depends(get_db_session),
):
	"""Upload an image and create an Asset record. Used for keyframe replacement."""
	# Validate project
	project = get_project_by_id(session, projectId)
	if project is None:
		return JSONResponse(
			status_code=404,
			content=build_error_envelope(
				code=ErrorCode.PROJECT_NOT_FOUND,
				message="Project does not exist",
				details={"projectId": projectId},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	if kind not in _ALLOWED_UPLOAD_KINDS:
		return _validation_error(request=request, message=f"kind must be one of {sorted(_ALLOWED_UPLOAD_KINDS)}")

	mime = file.content_type or "application/octet-stream"
	if mime not in _ALLOWED_IMAGE_MIMES:
		return _validation_error(request=request, message=f"Unsupported image type: {mime}")

	# Generate asset ID and relative path
	asset_id = str(uuid.uuid4())
	ext = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/gif": ".gif"}.get(mime, ".bin")
	rel_path = str(Path("assets") / projectId / f"{asset_id}{ext}")

	# Write file to DATA_DIR
	data_dir = get_data_dir()
	abs_path = data_dir / rel_path
	abs_path.parent.mkdir(parents=True, exist_ok=True)

	try:
		content = await file.read()
		abs_path.write_bytes(content)
	except Exception:
		return JSONResponse(
			status_code=500,
			content=build_error_envelope(
				code=ErrorCode.INTERNAL_ERROR,
				message="Failed to save uploaded file",
				details={"projectId": projectId},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	# Create asset record
	created_at_ms = _now_ms()
	asset = Asset(
		asset_id=asset_id,
		project_id=projectId,
		kind=kind,
		origin="uploaded",
		mime_type=mime,
		width=None,
		height=None,
		file_path=rel_path,
		chapter_id=None,
		time_ms=None,
		created_at_ms=created_at_ms,
	)
	session.add(asset)
	try:
		session.commit()
	except Exception:
		session.rollback()
		return JSONResponse(
			status_code=500,
			content=build_error_envelope(
				code=ErrorCode.INTERNAL_ERROR,
				message="Failed to create asset record",
				details={"projectId": projectId},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	return JSONResponse(
		status_code=201,
		content={
			"assetId": asset_id,
			"contentUrl": f"/api/v1/assets/{asset_id}/content",
			"kind": kind,
			"createdAtMs": created_at_ms,
		},
	)

