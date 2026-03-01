from tempfile import TemporaryDirectory
import os
import sys
from pathlib import Path
project_root = Path(__file__).resolve().parents[1]
src_dir = project_root / "src"
sys.path.insert(0, str(src_dir))
from core.main import create_app
from fastapi.testclient import TestClient

with TemporaryDirectory() as tmp:
    os.environ["DATA_DIR"] = tmp
    os.environ["WORKER_ENABLE"] = "0"
    # Do not set ANALYZE_PROVIDER
    from core.db.session import reset_db_for_tests
    reset_db_for_tests()

    url1 = "https://www.bilibili.com/video/BV1xx411c7mD/?spm_id_from=333.1007.tianma.1-1-1"
    with TestClient(create_app()) as client:
        r = client.post("/api/v1/jobs", json={"sourceType": "bilibili", "sourceUrl": url1, "title": "t"})
        print('status', r.status_code)
        try:
            print('json', r.json())
        except Exception:
            print('text', r.text)
