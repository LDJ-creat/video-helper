from __future__ import annotations

from collections.abc import Iterator

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session

from core.contracts.error_codes import ErrorCode
from core.contracts.error_envelope import build_error_envelope
from core.db.repositories.assets import get_asset_by_id
from core.db.session import get_db_session
from core.schemas.assets import AssetDTO
from core.storage.safe_paths import PathTraversalBlockedError, resolve_under_data_dir


router = APIRouter(tags=["assets"])


def _parse_single_range_header(value: str, *, size: int) -> tuple[int, int] | None:
	"""Parse a single HTTP Range header (bytes=start-end).

	Returns (start, end) inclusive, or None if invalid/unsupported.
	"""

	value = (value or "").strip().lower()
	if not value.startswith("bytes="):
		return None

	# We only support a single range.
	if "," in value:
		return None

	spec = value[len("bytes=") :].strip()
	if not spec or "-" not in spec:
		return None

	start_s, end_s = spec.split("-", 1)
	start_s = start_s.strip()
	end_s = end_s.strip()

	# bytes=-N (suffix range)
	if start_s == "":
		try:
			suffix = int(end_s)
		except Exception:
			return None
		if suffix <= 0:
			return None
		if suffix >= size:
			return (0, max(0, size - 1))
		return (size - suffix, size - 1)

	try:
		start = int(start_s)
	except Exception:
		return None

	if start < 0 or start >= size:
		return None

	# bytes=start- (open ended)
	if end_s == "":
		return (start, size - 1)

	try:
		end = int(end_s)
	except Exception:
		return None

	if end < start:
		return None
	end = min(end, size - 1)
	return (start, end)


def _iter_file_range(*, abs_path, start: int, end: int, chunk_size: int = 1024 * 1024) -> Iterator[bytes]:
	remaining = end - start + 1
	with abs_path.open("rb") as f:
		f.seek(start)
		while remaining > 0:
			chunk = f.read(min(chunk_size, remaining))
			if not chunk:
				return
			remaining -= len(chunk)
			yield chunk


@router.get("/assets/{assetId}", response_model=AssetDTO)
def get_asset(assetId: str, request: Request, session: Session = Depends(get_db_session)):
	asset = get_asset_by_id(session, assetId)
	if asset is None:
		return JSONResponse(
			status_code=404,
			content=build_error_envelope(
				code=ErrorCode.ASSET_NOT_FOUND,
				message="Asset does not exist",
				details={"assetId": assetId},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	size_bytes: int | None = None
	if asset.file_path:
		try:
			abs_path = resolve_under_data_dir(asset.file_path)
			if abs_path.exists() and abs_path.is_file():
				size_bytes = abs_path.stat().st_size
		except PathTraversalBlockedError:
			# Keep metadata stable but do not leak path details.
			size_bytes = None

	return AssetDTO(
		assetId=asset.asset_id,
		projectId=asset.project_id,
		kind=asset.kind,
		origin=asset.origin,
		mimeType=asset.mime_type,
		sizeBytes=size_bytes,
		width=asset.width,
		height=asset.height,
		chapterId=asset.chapter_id,
		timeMs=asset.time_ms,
		createdAtMs=asset.created_at_ms,
		contentUrl=f"/api/v1/assets/{asset.asset_id}/content",
	)


@router.get("/assets/{assetId}/content")
def get_asset_content(assetId: str, request: Request, session: Session = Depends(get_db_session)):
	asset = get_asset_by_id(session, assetId)
	if asset is None:
		return JSONResponse(
			status_code=404,
			content=build_error_envelope(
				code=ErrorCode.ASSET_NOT_FOUND,
				message="Asset does not exist",
				details={"assetId": assetId},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	if not asset.file_path:
		return JSONResponse(
			status_code=404,
			content=build_error_envelope(
				code=ErrorCode.ASSET_NOT_FOUND,
				message="Asset content unavailable",
				details={"assetId": assetId},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	try:
		abs_path = resolve_under_data_dir(asset.file_path)
	except PathTraversalBlockedError:
		return JSONResponse(
			status_code=400,
			content=build_error_envelope(
				code=ErrorCode.PATH_TRAVERSAL_BLOCKED,
				message="Unsafe asset path",
				details={"assetId": assetId},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	if not abs_path.exists() or not abs_path.is_file():
		return JSONResponse(
			status_code=404,
			content=build_error_envelope(
				code=ErrorCode.ASSET_NOT_FOUND,
				message="Asset content unavailable",
				details={"assetId": assetId},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	size = abs_path.stat().st_size
	mime = asset.mime_type or "application/octet-stream"

	range_header = request.headers.get("range")
	byte_range = _parse_single_range_header(range_header or "", size=size) if range_header else None

	headers = {"Accept-Ranges": "bytes"}
	if byte_range is None:
		return StreamingResponse(
			_iter_file_range(abs_path=abs_path, start=0, end=max(0, size - 1)),
			media_type=mime,
			headers=headers,
		)

	start, end = byte_range
	headers.update(
		{
			"Content-Range": f"bytes {start}-{end}/{size}",
			"Content-Length": str(end - start + 1),
		}
	)
	return StreamingResponse(
		_iter_file_range(abs_path=abs_path, start=start, end=end),
		status_code=206,
		media_type=mime,
		headers=headers,
	)
