# import json
# import os
# import sys
# import threading
# import time
# import unittest
# from pathlib import Path
# from tempfile import TemporaryDirectory

# from fastapi.testclient import TestClient


# class TestSseRealtime(unittest.TestCase):
#     def _import_app(self):
#         project_root = Path(__file__).resolve().parents[1]  # services/core
#         src_dir = project_root / "src"
#         if str(src_dir) not in sys.path:
#             sys.path.insert(0, str(src_dir))

#         from core.db.session import init_db, reset_db_for_tests  # noqa: WPS433
#         from core.main import create_app  # noqa: WPS433

#         return create_app, init_db, reset_db_for_tests

#     def test_sse_streams_new_events_realtime(self):
#         create_app, init_db, reset_db_for_tests = self._import_app()

#         with TemporaryDirectory() as tmp:
#             os.environ["DATA_DIR"] = tmp
#             reset_db_for_tests()
#             init_db()

#             from core.app.sse.event_bus import GLOBAL_JOB_EVENT_BUS  # noqa: WPS433
#             from core.db.models.job import Job  # noqa: WPS433
#             from core.db.session import get_sessionmaker  # noqa: WPS433

#             GLOBAL_JOB_EVENT_BUS.reset_for_tests()

#             job_id = "00000000-0000-0000-0000-000000000001"
#             project_id = "00000000-0000-0000-0000-000000000002"

#             SessionLocal = get_sessionmaker()
#             with SessionLocal() as session:
#                 session.add(
#                     Job(
#                         job_id=job_id,
#                         project_id=project_id,
#                         type="ingest_url",
#                         status="queued",
#                         stage="ingest",
#                         progress=None,
#                         error=None,
#                         transcript=None,
#                         chapters=None,
#                         audio_ref=None,
#                         transcript_ref=None,
#                         transcript_meta=None,
#                         claimed_by=None,
#                         claim_token=None,
#                         lease_expires_at_ms=None,
#                         started_at_ms=None,
#                         finished_at_ms=None,
#                         attempt=0,
#                         created_at_ms=1,
#                         updated_at_ms=1,
#                     )
#                 )
#                 session.commit()

#             def emit_later():
#                 time.sleep(0.2)
#                 GLOBAL_JOB_EVENT_BUS.emit_progress(
#                     job_id=job_id,
#                     project_id=project_id,
#                     stage="analyze",
#                     progress=0.5,
#                     message="half",
#                 )

#             t = threading.Thread(target=emit_later, daemon=True)
#             t.start()

#             with TestClient(create_app()) as client:
#                 with client.stream("GET", f"/api/v1/jobs/{job_id}/events") as resp:
#                     assert resp.status_code == 200

#                     event_type = None
#                     data_json = None
#                     deadline = time.time() + 5

#                     for raw_line in resp.iter_lines():
#                         if time.time() > deadline:
#                             break

#                         line = raw_line.decode("utf-8") if isinstance(raw_line, (bytes, bytearray)) else str(raw_line)
#                         line = line.strip("\r\n")

#                         if line == "":
#                             if event_type == "progress" and data_json:
#                                 payload = json.loads(data_json)
#                                 self.assertEqual(payload["jobId"], job_id)
#                                 self.assertEqual(payload["projectId"], project_id)
#                                 self.assertEqual(payload["stage"], "analyze")
#                                 self.assertAlmostEqual(payload["progress"], 0.5)
#                                 return
#                             event_type = None
#                             data_json = None
#                             continue

#                         if line.startswith("event:"):
#                             event_type = line.split(":", 1)[1].strip()
#                         elif line.startswith("data:"):
#                             data_json = line.split(":", 1)[1].strip()

#             self.fail("did not receive a realtime progress event")
