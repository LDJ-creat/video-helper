import os
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


class TestEditingAPIs(unittest.TestCase):
    def _import_app(self):
        project_root = Path(__file__).resolve().parents[1]  # services/core
        src_dir = project_root / "src"
        if str(src_dir) not in sys.path:
            sys.path.insert(0, str(src_dir))

        from core.db.session import reset_db_for_tests  # noqa: WPS433
        from core.main import create_app  # noqa: WPS433

        return create_app, reset_db_for_tests

    def _seed_project_result_assets(self, *, project_id: str, result_id: str, asset_ids: list[str]):
        from core.db.models.asset import Asset  # noqa: WPS433
        from core.db.models.project import Project  # noqa: WPS433
        from core.db.models.result import Result  # noqa: WPS433
        from core.db.session import get_sessionmaker  # noqa: WPS433

        SessionLocal = get_sessionmaker()
        with SessionLocal() as session:
            project = Project(
                project_id=project_id,
                title="t",
                source_type="upload",
                source_url=None,
                source_path=None,
                duration_ms=None,
                format=None,
                latest_result_id=result_id,
                created_at_ms=1,
                updated_at_ms=1,
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
                            "text": "Point A",
                            "startMs": 1000,
                            "endMs": 2000,
                        }
                    ],
                },
                {
                    "blockId": "b2",
                    "idx": 1,
                    "title": "Part",
                    "startMs": 10_000,
                    "endMs": 20_000,
                    "highlights": [
                        {
                            "highlightId": "h2",
                            "idx": 0,
                            "text": "Point B",
                            "startMs": 12_000,
                            "endMs": 13_000,
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
                mindmap={"nodes": [{"id": "n1", "type": "root", "label": "Video"}], "edges": []},
                note_json={"type": "doc", "content": []},
                asset_refs=[{"assetId": "v1", "kind": "video", "contentUrl": "/api/v1/assets/v1/content"}],
            )
            session.add(row)

            for aid in asset_ids:
                session.add(
                    Asset(
                        asset_id=aid,
                        project_id=project_id,
                        kind="screenshot",
                        origin="generated",
                        mime_type="image/jpeg",
                        width=1,
                        height=1,
                        file_path=None,
                        chapter_id=None,
                        time_ms=None,
                        created_at_ms=1,
                    )
                )

            session.commit()

    def test_save_content_blocks_overwrites_and_returns_updated_at(self):
        create_app, reset_db_for_tests = self._import_app()

        with TemporaryDirectory() as tmp:
            os.environ["DATA_DIR"] = tmp
            reset_db_for_tests()

            from fastapi.testclient import TestClient  # noqa: WPS433
            from core.db.session import get_sessionmaker  # noqa: WPS433
            from core.db.models.result import Result  # noqa: WPS433

            with TestClient(create_app()) as client:
                self._seed_project_result_assets(project_id="p1", result_id="r1", asset_ids=["a1"]) 

                new_blocks = [
                    {
                        "blockId": "b_new_1",
                        "idx": 0,
                        "title": "New Intro",
                        "startMs": 0,
                        "endMs": 5000,
                        "highlights": [],
                    }
                ]

                resp = client.put(
                    "/api/v1/projects/p1/results/latest/content-blocks",
                    json={"contentBlocks": new_blocks},
                )
                self.assertEqual(200, resp.status_code)
                self.assertIn("updatedAtMs", resp.json())
                self.assertIn("etag", {k.lower() for k in resp.headers.keys()})

                SessionLocal = get_sessionmaker()
                with SessionLocal() as session:
                    row = session.get(Result, "r1")
                    self.assertIsNotNone(row)
                    self.assertEqual(1, len(row.content_blocks))
                    self.assertEqual("b_new_1", row.content_blocks[0].get("blockId"))
                    self.assertEqual("New Intro", row.content_blocks[0].get("title"))

                # Validation: missing blockId
                resp2 = client.put(
                    "/api/v1/projects/p1/results/latest/content-blocks",
                    json={"contentBlocks": [{"idx": 0, "title": "No ID"}]},
                )
                self.assertEqual(400, resp2.status_code)
                self.assertEqual("VALIDATION_ERROR", resp2.json().get("error", {}).get("code"))

                reset_db_for_tests()

    def test_save_mindmap_validates_and_overwrites(self):
        create_app, reset_db_for_tests = self._import_app()

        with TemporaryDirectory() as tmp:
            os.environ["DATA_DIR"] = tmp
            reset_db_for_tests()

            from fastapi.testclient import TestClient  # noqa: WPS433
            from core.db.session import get_sessionmaker  # noqa: WPS433
            from core.db.models.result import Result  # noqa: WPS433

            with TestClient(create_app()) as client:
                self._seed_project_result_assets(project_id="p1", result_id="r1", asset_ids=["a1"]) 

                ok_graph = {
                    "nodes": [
                        {"id": "node_root", "type": "root", "label": "Video"},
                        {"id": "node_a", "type": "topic", "label": "A"},
                    ],
                    "edges": [{"id": "e1", "source": "node_root", "target": "node_a"}],
                }
                resp = client.put("/api/v1/projects/p1/results/latest/mindmap", json=ok_graph)
                self.assertEqual(200, resp.status_code)

                SessionLocal = get_sessionmaker()
                with SessionLocal() as session:
                    row = session.get(Result, "r1")
                    self.assertEqual(2, len(row.mindmap.get("nodes")))

                bad_graph = {
                    "nodes": [{"id": "n1", "type": "root", "label": "x", "hack": 1}],
                    "edges": [],
                }
                resp2 = client.put("/api/v1/projects/p1/results/latest/mindmap", json=bad_graph)
                self.assertEqual(400, resp2.status_code)
                self.assertEqual("VALIDATION_ERROR", resp2.json().get("error", {}).get("code"))

            reset_db_for_tests()

    def test_edit_block_title_does_not_change_time(self):
        create_app, reset_db_for_tests = self._import_app()

        with TemporaryDirectory() as tmp:
            os.environ["DATA_DIR"] = tmp
            os.environ.pop("ALLOW_CHAPTER_TIME_EDIT", None)
            reset_db_for_tests()

            from fastapi.testclient import TestClient  # noqa: WPS433
            from core.db.session import get_sessionmaker  # noqa: WPS433
            from core.db.models.result import Result  # noqa: WPS433

            with TestClient(create_app()) as client:
                self._seed_project_result_assets(project_id="p1", result_id="r1", asset_ids=["a1"]) 

                resp = client.patch("/api/v1/projects/p1/results/latest/blocks/b1", json={"title": "New"})
                self.assertEqual(200, resp.status_code)

                SessionLocal = get_sessionmaker()
                with SessionLocal() as session:
                    row = session.get(Result, "r1")
                    b = [b for b in row.content_blocks if b.get("blockId") == "b1"][0]
                    self.assertEqual("New", b.get("title"))
                    self.assertEqual(0, b.get("startMs"))
                    self.assertEqual(10_000, b.get("endMs"))

                resp2 = client.patch(
                    "/api/v1/projects/p1/results/latest/blocks/b1",
                    json={"startMs": 1, "endMs": 2},
                )
                self.assertEqual(400, resp2.status_code)
                self.assertEqual("CHAPTER_TIME_EDIT_DISABLED", resp2.json().get("error", {}).get("code"))

            reset_db_for_tests()

    def test_update_highlight_keyframe_validates_project_scope_and_persists(self):
        create_app, reset_db_for_tests = self._import_app()

        with TemporaryDirectory() as tmp:
            os.environ["DATA_DIR"] = tmp
            reset_db_for_tests()

            from fastapi.testclient import TestClient  # noqa: WPS433
            from core.db.models.asset import Asset  # noqa: WPS433
            from core.db.models.result import Result  # noqa: WPS433
            from core.db.session import get_sessionmaker  # noqa: WPS433

            with TestClient(create_app()) as client:
                self._seed_project_result_assets(project_id="p1", result_id="r1", asset_ids=["a1", "a2"]) 

                # Asset from another project
                SessionLocal = get_sessionmaker()
                with SessionLocal() as session:
                    session.add(
                        Asset(
                            asset_id="ax",
                            project_id="p2",
                            kind="screenshot",
                            origin="generated",
                            mime_type="image/jpeg",
                            width=1,
                            height=1,
                            file_path=None,
                            chapter_id=None,
                            time_ms=None,
                            created_at_ms=1,
                        )
                    )
                    session.commit()

                resp = client.put(
                    "/api/v1/projects/p1/results/latest/highlights/h1/keyframe",
                    json={"assetId": "a1", "timeMs": 123},
                )
                self.assertEqual(200, resp.status_code)

                with SessionLocal() as session:
                    row = session.get(Result, "r1")
                    b = [b for b in row.content_blocks if b.get("blockId") == "b1"][0]
                    hl = [h for h in b.get("highlights", []) if h.get("highlightId") == "h1"][0]
                    self.assertEqual("a1", hl.get("keyframe", {}).get("assetId"))
                    self.assertEqual(123, hl.get("keyframe", {}).get("timeMs"))
                    self.assertTrue(str(hl.get("keyframe", {}).get("contentUrl", "")).endswith("/content"))

                    a1 = session.get(Asset, "a1")
                    self.assertEqual(123, a1.time_ms)

                resp2 = client.put(
                    "/api/v1/projects/p1/results/latest/highlights/h1/keyframe",
                    json={"assetId": "ax"},
                )
                self.assertEqual(400, resp2.status_code)
                self.assertEqual("ASSET_NOT_IN_PROJECT", resp2.json().get("error", {}).get("code"))

                resp3 = client.put(
                    "/api/v1/projects/p1/results/latest/highlights/h1/keyframe",
                    json={"assetId": None},
                )
                self.assertEqual(200, resp3.status_code)
                with SessionLocal() as session:
                    row = session.get(Result, "r1")
                    b = [b for b in row.content_blocks if b.get("blockId") == "b1"][0]
                    hl = [h for h in b.get("highlights", []) if h.get("highlightId") == "h1"][0]
                    self.assertFalse("keyframe" in hl)

            reset_db_for_tests()


if __name__ == "__main__":
    unittest.main()
