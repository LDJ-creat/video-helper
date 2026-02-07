from __future__ import annotations

import time
import uuid

from sqlalchemy.orm import Session

from core.db.models.project import Project
from core.db.models.result import Result


class AssembleResultError(RuntimeError):
	def __init__(self, kind: str, message: str):
		super().__init__(message)
		self.kind = kind


def assemble_result(
	session: Session,
	*,
	project_id: str,
	content_blocks: list[dict] | None = None,
	chapters: list[dict] | None = None,
	highlights: list[dict] | None = None,
	mindmap: dict,
	asset_refs: list[dict],
	schema_version: str = "2026-02-06",
	pipeline_version: str = "0",
) -> str:
	"""Persist a renderable Result and update project's latest_result_id.

	This is the recoverability anchor: the latest Result must be sufficient for FE
	to render without relying on in-memory pipeline state.
	"""

	project = session.get(Project, project_id)
	if project is None:
		raise AssembleResultError("project_not_found", "Project does not exist")

	# Basic sanity checks to attribute failures.
	if mindmap is None:
		raise AssembleResultError("missing_artifacts", "Pipeline artifacts are missing")
	if not isinstance(mindmap, dict):
		raise AssembleResultError("invalid_artifacts", "Pipeline artifacts are invalid")
	# vNext storage: prefer plan-provided content_blocks.
	if content_blocks is None:
		# Legacy path: derive minimal content_blocks from chapters/highlights (+ embedded chapter.keyframes).
		if chapters is None or highlights is None:
			raise AssembleResultError("missing_artifacts", "Pipeline artifacts are missing")
		if not isinstance(chapters, list) or not isinstance(highlights, list):
			raise AssembleResultError("invalid_artifacts", "Pipeline artifacts are invalid")

		content_blocks = []
		by_chapter: dict[str, list[dict]] = {}
		for hl in highlights:
			if not isinstance(hl, dict):
				continue
			cid = hl.get("chapterId")
			if isinstance(cid, str) and cid:
				by_chapter.setdefault(cid, []).append(hl)

		for ch in chapters:
			if not isinstance(ch, dict):
				continue
			cid = ch.get("chapterId")
			if not isinstance(cid, str) or not cid:
				continue
			start_ms = ch.get("startMs")
			end_ms = ch.get("endMs")
			if not isinstance(start_ms, int) or not isinstance(end_ms, int) or end_ms <= start_ms:
				continue

			keyframes = ch.get("keyframes") if isinstance(ch.get("keyframes"), list) else []
			chapter_hls = [h for h in by_chapter.get(cid, []) if isinstance(h, dict)]
			chapter_hls_sorted = sorted(
				chapter_hls,
				key=lambda h: int(h.get("idx") if isinstance(h.get("idx"), int) else 0),
			)

			out_hls: list[dict] = []
			for h in chapter_hls_sorted:
				hid = h.get("highlightId")
				if not isinstance(hid, str) or not hid:
					continue
				text = h.get("text")
				if not isinstance(text, str):
					text = ""
				tm = h.get("timeMs")
				tm_i = int(tm) if isinstance(tm, int) else None
				hl_start = max(start_ms, (tm_i - 5000) if tm_i is not None else start_ms)
				hl_end = min(end_ms, (tm_i + 5000) if tm_i is not None else end_ms)
				if hl_end <= hl_start:
					hl_start, hl_end = start_ms, end_ms

				# Attach the closest keyframe (legacy) to highlight.
				best_kf: dict | None = None
				best_dist: int | None = None
				if tm_i is not None:
					for kf in keyframes:
						if not isinstance(kf, dict):
							continue
						kf_tm = kf.get("timeMs")
						if not isinstance(kf_tm, int):
							continue
						dist = abs(int(kf_tm) - tm_i)
						if best_dist is None or dist < best_dist:
							best_dist = dist
							best_kf = kf

				hl_out: dict = {
					"highlightId": hid,
					"idx": int(h.get("idx") if isinstance(h.get("idx"), int) else 0),
					"text": text,
					"startMs": int(hl_start),
					"endMs": int(hl_end),
				}
				if best_kf is not None and isinstance(best_kf.get("assetId"), str) and best_kf.get("assetId"):
					asset_id = str(best_kf.get("assetId"))
					hl_out["keyframe"] = {
						"assetId": asset_id,
						"contentUrl": f"/api/v1/assets/{asset_id}/content",
						"timeMs": best_kf.get("timeMs"),
						"caption": best_kf.get("caption"),
					}
				out_hls.append(hl_out)

			content_blocks.append(
				{
					"blockId": f"b_{cid}",
					"idx": int(ch.get("idx") if isinstance(ch.get("idx"), int) else 0),
					"title": str(ch.get("title")) if isinstance(ch.get("title"), str) else "",
					"startMs": int(start_ms),
					"endMs": int(end_ms),
					"highlights": out_hls,
				}
			)
	else:
		if not isinstance(content_blocks, list):
			raise AssembleResultError("invalid_artifacts", "Pipeline artifacts are invalid")

	now_ms = int(time.time() * 1000)
	result_id = str(uuid.uuid4())

	note_json: dict = {}

	row = Result(
		result_id=result_id,
		project_id=project_id,
		schema_version=schema_version,
		pipeline_version=pipeline_version,
		created_at_ms=now_ms,
		updated_at_ms=now_ms,
		content_blocks=content_blocks,
		mindmap=mindmap,
		note_json=note_json,
		asset_refs=asset_refs or [],
	)

	try:
		session.add(row)
		project.latest_result_id = result_id
		project.updated_at_ms = now_ms
		session.commit()
	except Exception as e:
		session.rollback()
		raise AssembleResultError("db_write_failed", "Failed to persist result") from e

	return result_id
