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
	# vNext storage: require plan-provided content_blocks.
	if content_blocks is None:
		raise AssembleResultError("missing_artifacts", "Pipeline artifacts are missing")
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
