from __future__ import annotations

from pathlib import Path

import pytest

from core.db.models.project import Project
from core.db.models.result import Result
from core.db.session import get_sessionmaker, init_db, reset_db_for_tests
from core.pipeline.stages.assemble_result import assemble_result


def test_assemble_result_prefers_explicit_content_blocks(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
	monkeypatch.setenv("DATA_DIR", str(tmp_path))
	reset_db_for_tests()
	init_db()

	SessionLocal = get_sessionmaker()
	with SessionLocal() as session:
		project = Project(
			project_id="p1",
			title="p",
			source_type="upload",
			source_url=None,
			source_path="p1/source.mp4",
			duration_ms=120000,
			format=None,
			latest_result_id=None,
			created_at_ms=1,
			updated_at_ms=1,
		)
		session.add(project)
		session.commit()

		content_blocks = [
			{
				"blockId": "b0",
				"idx": 0,
				"type": "chapter",
				"title": "T",
				"summary": "S",
				"timeRange": {"startMs": 0, "endMs": 1000},
				"highlights": [
					{
						"highlightId": "h0",
						"idx": 0,
						"quote": "q",
						"analysis": "a",
						"tags": ["t"],
						"keyframe": {"timeMs": 500, "assetId": "asset-1", "contentUrl": "/api/v1/assets/asset-1/content"},
					}
				],
			}
		]

		assemble_result(
			session,
			project_id=project.project_id,
			content_blocks=content_blocks,
			mindmap={"nodes": [], "edges": []},
			asset_refs=[{"assetId": "asset-1", "kind": "image"}],
			schema_version="2026-02-06",
			pipeline_version="test",
		)

		result = session.query(Result).filter(Result.project_id == project.project_id).order_by(Result.created_at_ms.desc()).first()
		assert result is not None
		assert isinstance(result.content_blocks, list)
		assert result.content_blocks[0]["blockId"] == "b0"
		assert result.schema_version == "2026-02-06"



