import os
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


class TestCors(unittest.TestCase):
    def _import_app(self):
        project_root = Path(__file__).resolve().parents[1]  # services/core
        src_dir = project_root / "src"
        if str(src_dir) not in sys.path:
            sys.path.insert(0, str(src_dir))

        from core.db.session import reset_db_for_tests  # noqa: WPS433
        from core.main import create_app  # noqa: WPS433

        return create_app, reset_db_for_tests

    def test_cors_allows_localhost_3000(self):
        create_app, reset_db_for_tests = self._import_app()

        with TemporaryDirectory() as tmp:
            os.environ["DATA_DIR"] = tmp
            os.environ["CORS_ALLOWED_ORIGINS"] = "http://localhost:3000"
            reset_db_for_tests()

            from fastapi.testclient import TestClient  # noqa: WPS433

            client = TestClient(create_app())
            resp = client.get("/api/v1/health", headers={"Origin": "http://localhost:3000"})
            self.assertEqual(200, resp.status_code)
            self.assertEqual("http://localhost:3000", resp.headers.get("access-control-allow-origin"))

    def test_cors_does_not_allow_other_origins(self):
        create_app, reset_db_for_tests = self._import_app()

        with TemporaryDirectory() as tmp:
            os.environ["DATA_DIR"] = tmp
            os.environ["CORS_ALLOWED_ORIGINS"] = "http://localhost:3000"
            reset_db_for_tests()

            from fastapi.testclient import TestClient  # noqa: WPS433

            client = TestClient(create_app())
            resp = client.get("/api/v1/health", headers={"Origin": "http://evil.example"})
            self.assertEqual(200, resp.status_code)
            self.assertIsNone(resp.headers.get("access-control-allow-origin"))

    def test_cors_allows_127_0_0_1_without_port_when_configured(self):
        create_app, reset_db_for_tests = self._import_app()

        with TemporaryDirectory() as tmp:
            os.environ["DATA_DIR"] = tmp
            os.environ["CORS_ALLOWED_ORIGINS"] = "http://localhost:3000,http://127.0.0.1"
            reset_db_for_tests()

            from fastapi.testclient import TestClient  # noqa: WPS433

            client = TestClient(create_app())
            resp = client.get("/api/v1/health", headers={"Origin": "http://127.0.0.1"})
            self.assertEqual(200, resp.status_code)
            self.assertEqual("http://127.0.0.1", resp.headers.get("access-control-allow-origin"))


if __name__ == "__main__":
    unittest.main()
