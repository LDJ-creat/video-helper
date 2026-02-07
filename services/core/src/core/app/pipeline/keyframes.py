from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from core.contracts.error_codes import ErrorCode
from core.db.models.asset import Asset
from core.db.models.project import Project
from core.external.ffmpeg import FfmpegError, extract_video_frame_jpeg
from core.storage.safe_paths import resolve_under_data_dir
from core.db.session import get_data_dir


@dataclass(frozen=True)
class KeyframeArtifacts:
	asset_refs: list[dict]
	keyframes_by_time: dict[int, dict]


def _now_ms() -> int:
	return int(time.time() * 1000)


def map_keyframes_error(exc: Exception) -> dict:
	# Dependency missing: must align with /health dependency probe behavior.
	if isinstance(exc, FfmpegError) and exc.kind == "dependency_missing":
		return {"code": ErrorCode.FFMPEG_MISSING, "message": str(exc), "details": {"reason": "dependency_missing", "step": "ffmpeg"}}

	if isinstance(exc, FfmpegError) and exc.kind == "resource_exhausted":
		details = {"reason": "resource_exhausted", "step": "ffmpeg"}
		if isinstance(getattr(exc, "details", None), dict):
			for k in ("exitCode", "ffmpegTail"):
				if k in exc.details:
					details[k] = exc.details.get(k)
		return {"code": ErrorCode.RESOURCE_EXHAUSTED, "message": "Resource exhausted", "details": details}

	if isinstance(exc, FfmpegError) and exc.kind == "timeout":
		return {"code": ErrorCode.JOB_STAGE_FAILED, "message": "Stage timed out", "details": {"reason": "timeout", "step": "ffmpeg"}}

	if isinstance(exc, FfmpegError) and exc.kind == "content_error":
		details = {"reason": "content_error", "step": "ffmpeg"}
		if isinstance(getattr(exc, "details", None), dict):
			for k in ("exitCode", "ffmpegTail"):
				if k in exc.details:
					details[k] = exc.details.get(k)
		return {"code": ErrorCode.JOB_STAGE_FAILED, "message": "Invalid media content", "details": details}

	return {"code": ErrorCode.JOB_STAGE_FAILED, "message": "Unexpected error", "details": {"reason": "unexpected"}}


def extract_keyframes_at_times(
	*,
	session: Session,
	project: Project,
	job_id: str,
	times_ms: list[int],
	allow_skip_if_placeholder: bool = True,	
	transcript_meta: dict | None = None,
) -> KeyframeArtifacts:
	"""Extract keyframes at explicit time points (ms) and persist them as Asset rows.

	Returns:
	- asset_refs for Result.asset_refs
	- keyframes_by_time for plan backfilling (timeMs -> keyframe dict)
	"""

	provider = None
	if isinstance(transcript_meta, dict):
		provider = transcript_meta.get("provider")

	# In placeholder mode we may not have a real media file; allow skipping to keep dev/smoke useful.
	if allow_skip_if_placeholder and provider == "placeholder":
		return KeyframeArtifacts(asset_refs=[], keyframes_by_time={})

	if not isinstance(times_ms, list):
		raise ValueError("times_ms must be a list")

	unique_times: list[int] = []
	seen: set[int] = set()
	for t in times_ms:
		if not isinstance(t, int):
			continue
		t_i = int(t)
		if t_i < 0:
			continue
		if t_i in seen:
			continue
		seen.add(t_i)
		unique_times.append(t_i)

	unique_times.sort()

	source_rel = project.source_path
	if not isinstance(source_rel, str) or not source_rel:
		raise ValueError("project.source_path missing for keyframes")

	source_abs = resolve_under_data_dir(source_rel)
	if not source_abs.exists() or not source_abs.is_file():
		raise ValueError("project source media not readable")

	now_ms = _now_ms()
	asset_refs: list[dict] = []
	by_time: dict[int, dict] = {}

	data_dir = get_data_dir().resolve()
	base_dir = (data_dir / project.project_id / "assets" / "keyframes" / job_id / "plan").resolve()
	base_dir.mkdir(parents=True, exist_ok=True)

	for idx, t_ms in enumerate(unique_times):
		asset_id = str(uuid.uuid4())
		filename = f"kf_{idx}_{t_ms}.jpg"
		out_abs = (base_dir / filename).resolve()

		# Enforce output under DATA_DIR.
		if not out_abs.is_relative_to(data_dir):
			raise ValueError("keyframe output escapes DATA_DIR")

		_, rel = extract_video_frame_jpeg(input_path=source_abs, output_path=out_abs, time_s=t_ms / 1000.0)

		asset = Asset(
			asset_id=asset_id,
			project_id=project.project_id,
			kind="screenshot",
			origin="generated",
			mime_type="image/jpeg",
			width=None,
			height=None,
			file_path=rel,
			chapter_id=None,
			time_ms=int(t_ms),
			created_at_ms=now_ms,
		)
		session.add(asset)

		asset_refs.append({"assetId": asset_id, "kind": "screenshot"})
		kf = {"assetId": asset_id, "idx": int(idx), "timeMs": int(t_ms), "caption": None}
		by_time[int(t_ms)] = kf

	session.commit()
	return KeyframeArtifacts(asset_refs=asset_refs, keyframes_by_time=by_time)
