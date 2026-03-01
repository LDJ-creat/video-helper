import os
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


class TestSearchAPI(unittest.TestCase):
	def _import_app(self):
		project_root = Path(__file__).resolve().parents[1]  # services/core
		src_dir = project_root / "src"
		if str(src_dir) not in sys.path:
			sys.path.insert(0, str(src_dir))

		from core.db.session import reset_db_for_tests  # noqa: WPS433
		from core.main import create_app  # noqa: WPS433

		return create_app, reset_db_for_tests

	def _seed_project_with_result(self, *, project_id: str, result_id: str):
		from core.db.models.project import Project  # noqa: WPS433
		from core.db.models.result import Result  # noqa: WPS433
		from core.db.session import get_sessionmaker  # noqa: WPS433

		SessionLocal = get_sessionmaker()
		with SessionLocal() as session:
			project = Project(
				project_id=project_id,
				title="Demo",
				source_type="upload",
				source_url=None,
				source_path=None,
				duration_ms=None,
				format=None,
				latest_result_id=result_id,
				created_at_ms=1,
				updated_at_ms=2,
			)
			session.add(project)

			content_blocks = [
				{
					"blockId": "b1",
					"idx": 0,
					"title": "Intro",
					"startMs": 0,
					"endMs": 10_000,
					"highlights": [
						{
							"highlightId": "h1",
							"idx": 0,
							"text": "Point A about docker",
							"startMs": 1000,
							"endMs": 2000,
						}
					],
				},
			]

			row = Result(
				result_id=result_id,
				project_id=project_id,
				schema_version="2026-02-06",
				pipeline_version="0",
				created_at_ms=1,
				updated_at_ms=1,
				content_blocks=content_blocks,
				mindmap={"nodes": [], "edges": []},
				note_json={"type": "doc", "content": []},
				asset_refs=[],
			)
			session.add(row)
			session.commit()

	def test_search_returns_project_id_and_title(self):
		create_app, reset_db_for_tests = self._import_app()

		with TemporaryDirectory() as tmp:
			os.environ["DATA_DIR"] = tmp
			reset_db_for_tests()
			from fastapi.testclient import TestClient  # noqa: WPS433

			with TestClient(create_app()) as client:
				self._seed_project_with_result(project_id="p1", result_id="r1")
				resp = client.get("/api/v1/search", params={"query": "docker", "limit": 20})
				self.assertEqual(resp.status_code, 200, resp.text)
				data = resp.json()
				self.assertIn("items", data)
				self.assertGreaterEqual(len(data["items"]), 1)
				first = data["items"][0]
				self.assertEqual(first["projectId"], "p1")
				self.assertEqual(first["title"], "Demo")
				self.assertNotIn("blockId", first)
				self.assertNotIn("highlightId", first)
