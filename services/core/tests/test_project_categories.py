import os
import sys
import unittest
import uuid
from pathlib import Path
from tempfile import TemporaryDirectory


class TestProjectCategories(unittest.TestCase):
    def _import_app(self):
        project_root = Path(__file__).resolve().parents[1]
        src_dir = project_root / "src"
        if str(src_dir) not in sys.path:
            sys.path.insert(0, str(src_dir))

        from core.db.session import reset_db_for_tests  # noqa: WPS433
        from core.main import create_app  # noqa: WPS433

        return create_app, reset_db_for_tests

    def _setup_client(self):
        create_app, reset_db_for_tests = self._import_app()
        tmp = TemporaryDirectory()
        os.environ["DATA_DIR"] = tmp.name
        os.environ["WORKER_ENABLE"] = "0"
        reset_db_for_tests()

        from fastapi.testclient import TestClient  # noqa: WPS433
        from core.db.session import get_sessionmaker  # noqa: WPS433
        from core.db.repositories.llm_settings import (  # noqa: WPS433
            set_llm_active,
            upsert_llm_provider_secret_ciphertext,
        )
        from core.llm.secrets_crypto import encrypt_api_key  # noqa: WPS433
        import time
        import core.app.api.jobs as jobs_api

        client_ctx = TestClient(create_app())
        client = client_ctx.__enter__()

        now_ms = int(time.time() * 1000)
        SessionLocal = get_sessionmaker()
        with SessionLocal() as session:
            set_llm_active(session, provider_id="nvidia", model_id="minimaxai/minimax-m2.5", now_ms=now_ms)
            token = encrypt_api_key("test-api-key")
            upsert_llm_provider_secret_ciphertext(
                session, provider_id="nvidia", ciphertext_b64=token, now_ms=now_ms
            )
            session.commit()

        jobs_api.run_llm_connectivity_test = lambda *_, **__: 1

        return client, client_ctx, tmp

    def test_default_category_seeded(self):
        client, client_ctx, tmp = self._setup_client()
        try:
            r = client.get("/api/v1/categories")
            self.assertEqual(r.status_code, 200)
            items = r.json()["items"]
            self.assertTrue(any(i["slug"] == "default" for i in items))
        finally:
            client_ctx.__exit__(None, None, None)
            tmp.cleanup()

    def test_create_category_conflict(self):
        client, client_ctx, tmp = self._setup_client()
        try:
            r1 = client.post("/api/v1/categories", json={"name": "教程"})
            self.assertEqual(r1.status_code, 201)
            r2 = client.post("/api/v1/categories", json={"name": "教程"})
            self.assertEqual(r2.status_code, 409)
            self.assertEqual(r2.json()["error"]["code"], "CATEGORY_NAME_CONFLICT")
        finally:
            client_ctx.__exit__(None, None, None)
            tmp.cleanup()

    def test_delete_system_category_forbidden(self):
        client, client_ctx, tmp = self._setup_client()
        try:
            cats = client.get("/api/v1/categories").json()["items"]
            default_id = next(c["categoryId"] for c in cats if c["slug"] == "default")
            r = client.delete(f"/api/v1/categories/{default_id}")
            self.assertEqual(r.status_code, 403)
            self.assertEqual(r.json()["error"]["code"], "CATEGORY_NOT_DELETABLE")
        finally:
            client_ctx.__exit__(None, None, None)
            tmp.cleanup()

    def test_job_sets_category_on_new_project(self):
        client, client_ctx, tmp = self._setup_client()
        try:
            cats = client.get("/api/v1/categories").json()["items"]
            tutorial = client.post("/api/v1/categories", json={"name": "教程"}).json()
            cat_id = tutorial["categoryId"]

            url = f"https://www.youtube.com/watch?v={uuid.uuid4().hex[:11]}"
            r = client.post(
                "/api/v1/jobs",
                json={"sourceType": "youtube", "sourceUrl": url, "categoryId": cat_id},
            )
            self.assertEqual(r.status_code, 200)
            project_id = r.json()["projectId"]

            detail = client.get(f"/api/v1/projects/{project_id}").json()
            self.assertEqual(detail["categoryId"], cat_id)
            self.assertEqual(detail["categoryName"], "教程")
        finally:
            client_ctx.__exit__(None, None, None)
            tmp.cleanup()

    def test_job_reuse_does_not_change_category(self):
        client, client_ctx, tmp = self._setup_client()
        try:
            cat_a = client.post("/api/v1/categories", json={"name": "A类"}).json()["categoryId"]
            cat_b = client.post("/api/v1/categories", json={"name": "B类"}).json()["categoryId"]

            url = f"https://www.bilibili.com/video/BV{uuid.uuid4().hex[:10]}"
            r1 = client.post(
                "/api/v1/jobs",
                json={"sourceType": "bilibili", "sourceUrl": url, "categoryId": cat_a},
            )
            project_id = r1.json()["projectId"]

            r2 = client.post(
                "/api/v1/jobs",
                json={"sourceType": "bilibili", "sourceUrl": url + "?x=1", "categoryId": cat_b},
            )
            self.assertEqual(r2.json()["projectId"], project_id)

            detail = client.get(f"/api/v1/projects/{project_id}").json()
            self.assertEqual(detail["categoryId"], cat_a)
        finally:
            client_ctx.__exit__(None, None, None)
            tmp.cleanup()

    def test_list_projects_filter_by_category(self):
        client, client_ctx, tmp = self._setup_client()
        try:
            cat = client.post("/api/v1/categories", json={"name": "筛选测"}).json()
            cat_id = cat["categoryId"]

            url = f"https://www.youtube.com/watch?v={uuid.uuid4().hex[:11]}"
            client.post(
                "/api/v1/jobs",
                json={"sourceType": "youtube", "sourceUrl": url, "categoryId": cat_id},
            )

            listed = client.get("/api/v1/projects", params={"categoryId": cat_id}).json()
            self.assertGreaterEqual(len(listed["items"]), 1)
            self.assertTrue(all(i["categoryId"] == cat_id for i in listed["items"]))
        finally:
            client_ctx.__exit__(None, None, None)
            tmp.cleanup()

    def test_patch_and_batch_update_category(self):
        client, client_ctx, tmp = self._setup_client()
        try:
            cat1 = client.post("/api/v1/categories", json={"name": "批1"}).json()["categoryId"]
            cat2 = client.post("/api/v1/categories", json={"name": "批2"}).json()["categoryId"]

            url = f"https://www.youtube.com/watch?v={uuid.uuid4().hex[:11]}"
            pid = client.post(
                "/api/v1/jobs",
                json={"sourceType": "youtube", "sourceUrl": url, "categoryId": cat1},
            ).json()["projectId"]

            r = client.patch(f"/api/v1/projects/{pid}", json={"categoryId": cat2})
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()["categoryId"], cat2)

            r_batch = client.patch(
                "/api/v1/projects/category-batch",
                json={"projectIds": [pid], "categoryId": cat1},
            )
            self.assertEqual(r_batch.status_code, 200)
            self.assertEqual(r_batch.json()["updated"], 1)
        finally:
            client_ctx.__exit__(None, None, None)
            tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
