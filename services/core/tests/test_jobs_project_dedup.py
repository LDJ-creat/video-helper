import os
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


class TestJobsProjectDedup(unittest.TestCase):
    def _import_app(self):
        project_root = Path(__file__).resolve().parents[1]  # services/core
        src_dir = project_root / "src"
        if str(src_dir) not in sys.path:
            sys.path.insert(0, str(src_dir))

        from core.db.session import reset_db_for_tests  # noqa: WPS433
        from core.main import create_app  # noqa: WPS433

        return create_app, reset_db_for_tests

    def test_create_job_reuses_project_for_same_video_url(self):
        create_app, reset_db_for_tests = self._import_app()

        with TemporaryDirectory() as tmp:
            os.environ["DATA_DIR"] = tmp
            os.environ["WORKER_ENABLE"] = "0"
            reset_db_for_tests()

            # Do not modify DB here; init happens when app is created below.

            from fastapi.testclient import TestClient  # noqa: WPS433
            from core.db.session import get_sessionmaker  # noqa: WPS433
            from core.db.models.job import Job  # noqa: WPS433
            from core.db.models.project import Project  # noqa: WPS433

            url1 = "https://www.bilibili.com/video/BV1xx411c7mD/?spm_id_from=333.1007.tianma.1-1-1"
            url2 = "https://www.bilibili.com/video/BV1xx411c7mD/?foo=bar"

            with TestClient(create_app()) as client:
                # Insert active LLM selection and encrypted secret into the app DB
                # so preflight uses DB-backed credentials (avoids network calls).
                from core.db.session import get_sessionmaker  # noqa: WPS433
                from core.db.repositories.llm_settings import set_llm_active, upsert_llm_provider_secret_ciphertext  # noqa: WPS433
                from core.llm.secrets_crypto import encrypt_api_key  # noqa: WPS433
                import time

                SessionLocal = get_sessionmaker()
                now_ms = int(time.time() * 1000)
                with SessionLocal() as session:
                    set_llm_active(session, provider_id="nvidia", model_id="minimaxai/minimax-m2.1", now_ms=now_ms)
                    token = encrypt_api_key("test-api-key")
                    upsert_llm_provider_secret_ciphertext(session, provider_id="nvidia", ciphertext_b64=token, now_ms=now_ms)
                    session.commit()
                # Avoid real network calls during tests by stubbing preflight.
                import core.app.api.jobs as jobs_api
                jobs_api.run_llm_connectivity_test = lambda *_, **__: 1
                r1 = client.post(
                    "/api/v1/jobs",
                    json={"sourceType": "bilibili", "sourceUrl": url1, "title": "t"},
                )
                self.assertEqual(r1.status_code, 200)
                body1 = r1.json()

                r2 = client.post(
                    "/api/v1/jobs",
                    json={"sourceType": "bilibili", "sourceUrl": url2, "title": "t"},
                )
                self.assertEqual(r2.status_code, 200)
                body2 = r2.json()

            # Same project, different jobs.
            self.assertEqual(body1["projectId"], body2["projectId"])
            self.assertNotEqual(body1["jobId"], body2["jobId"])

            SessionLocal = get_sessionmaker()
            with SessionLocal() as session:
                projects = session.query(Project).all()
                self.assertEqual(len(projects), 1)
                self.assertEqual(projects[0].project_id, body1["projectId"])
                self.assertEqual(projects[0].source_type, "bilibili")
                self.assertEqual(projects[0].source_url, "https://www.bilibili.com/video/BV1xx411c7mD")

                jobs = session.query(Job).order_by(Job.created_at_ms.asc()).all()
                self.assertEqual(len(jobs), 2)
                self.assertEqual({j.project_id for j in jobs}, {body1["projectId"]})

    def test_create_job_accepts_url_without_source_type(self):
        create_app, reset_db_for_tests = self._import_app()

        with TemporaryDirectory() as tmp:
            os.environ["DATA_DIR"] = tmp
            os.environ["WORKER_ENABLE"] = "0"
            # Satisfy env-backed LLM preflight path.
            os.environ["LLM_API_BASE"] = "http://example.test"
            os.environ["LLM_API_KEY"] = "test"
            reset_db_for_tests()

            from fastapi.testclient import TestClient  # noqa: WPS433

            url = "https://example.com/video/123"

            with TestClient(create_app()) as client:
                # Stub out LLM preflight.
                import core.app.api.jobs as jobs_api

                jobs_api.run_llm_connectivity_test = lambda *_, **__: 1
                # New flow probes yt-dlp; keep it deterministic in tests.
                jobs_api.probe_url_support = lambda *_, **__: (True, {"extractor": "generic"})

                r = client.post(
                    "/api/v1/jobs",
                    json={"sourceUrl": url, "title": "t"},
                )
                self.assertEqual(r.status_code, 200, r.text)
                body = r.json()
                self.assertIn("jobId", body)
                self.assertIn("projectId", body)

            from core.db.session import get_sessionmaker  # noqa: WPS433
            from core.db.models.project import Project  # noqa: WPS433

            SessionLocal = get_sessionmaker()
            with SessionLocal() as session:
                projects = session.query(Project).all()
                self.assertEqual(len(projects), 1)
                self.assertEqual(projects[0].project_id, body["projectId"])
                self.assertEqual(projects[0].source_type, "url")
                self.assertEqual(projects[0].source_url, url)

    def test_create_job_youtube_watch_url_keeps_v_param(self):
        create_app, reset_db_for_tests = self._import_app()

        with TemporaryDirectory() as tmp:
            os.environ["DATA_DIR"] = tmp
            os.environ["WORKER_ENABLE"] = "0"
            # Satisfy env-backed LLM preflight path.
            os.environ["LLM_API_BASE"] = "http://example.test"
            os.environ["LLM_API_KEY"] = "test"
            reset_db_for_tests()

            from fastapi.testclient import TestClient  # noqa: WPS433
            from core.db.session import get_sessionmaker  # noqa: WPS433
            from core.db.models.project import Project  # noqa: WPS433

            url1 = "https://www.youtube.com/watch?v=ScMzIvxBSi4&t=10s"
            url2 = "https://www.youtube.com/watch?v=ScMzIvxBSi4&feature=youtu.be"

            with TestClient(create_app()) as client:
                import core.app.api.jobs as jobs_api

                jobs_api.run_llm_connectivity_test = lambda *_, **__: 1
                r1 = client.post(
                    "/api/v1/jobs",
                    json={"sourceType": "youtube", "sourceUrl": url1, "title": "t"},
                )
                self.assertEqual(r1.status_code, 200, r1.text)
                body1 = r1.json()

                r2 = client.post(
                    "/api/v1/jobs",
                    json={"sourceType": "youtube", "sourceUrl": url2, "title": "t"},
                )
                self.assertEqual(r2.status_code, 200, r2.text)
                body2 = r2.json()

            self.assertEqual(body1["projectId"], body2["projectId"])

            SessionLocal = get_sessionmaker()
            with SessionLocal() as session:
                projects = session.query(Project).all()
                self.assertEqual(len(projects), 1)
                self.assertEqual(projects[0].source_type, "youtube")
                self.assertEqual(projects[0].source_url, "https://www.youtube.com/watch?v=ScMzIvxBSi4")

    def test_create_job_rejects_youtube_watch_url_without_v(self):
        create_app, reset_db_for_tests = self._import_app()

        with TemporaryDirectory() as tmp:
            os.environ["DATA_DIR"] = tmp
            os.environ["WORKER_ENABLE"] = "0"
            os.environ["LLM_API_BASE"] = "http://example.test"
            os.environ["LLM_API_KEY"] = "test"
            reset_db_for_tests()

            from fastapi.testclient import TestClient  # noqa: WPS433

            with TestClient(create_app()) as client:
                import core.app.api.jobs as jobs_api

                jobs_api.run_llm_connectivity_test = lambda *_, **__: 1
                r = client.post(
                    "/api/v1/jobs",
                    json={"sourceType": "youtube", "sourceUrl": "https://www.youtube.com/watch", "title": "t"},
                )
                self.assertEqual(r.status_code, 400)
                body = r.json()
                self.assertEqual(body.get("error", {}).get("code"), "INVALID_SOURCE_URL")
