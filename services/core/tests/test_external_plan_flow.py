from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("WORKER_ENABLE", "0")

    # Ensure LLM env is absent so we prove llmMode=external bypasses preflight.
    monkeypatch.delenv("LLM_API_BASE", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)

    from core.db.session import reset_db_engine_for_tests

    reset_db_engine_for_tests()

    from core.main import create_app

    app = create_app()
    with TestClient(app) as c:
        yield c


def test_create_job_external_llm_skips_preflight(client: TestClient):
    res = client.post(
        "/api/v1/jobs",
        json={
            "sourceType": "url",
            "sourceUrl": "https://example.com/video",
            "title": "Example",
            "llmMode": "external",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert uuid.UUID(data["jobId"])  # valid uuid
    assert data["status"] == "queued"


def test_plan_request_and_submit_flow(client: TestClient):
    # Create job
    res = client.post(
        "/api/v1/jobs",
        json={
            "sourceType": "url",
            "sourceUrl": "https://example.com/video",
            "title": "Example",
            "llmMode": "external",
        },
    )
    assert res.status_code == 200
    job_id = res.json()["jobId"]

    # Pretend transcript is ready and job is blocked awaiting external plan.
    from core.db.session import get_sessionmaker
    from core.db.models.job import Job

    SessionLocal = get_sessionmaker()
    with SessionLocal() as session:
        job = session.get(Job, job_id)
        assert job is not None
        job.transcript = {
            "segments": [
                {"startMs": 0, "endMs": 1000, "text": "Hello world"},
            ]
        }
        job.status = "blocked"
        job.stage = "plan"
        job.progress = 0.6
        session.add(job)
        session.commit()

    # Fetch prompt payload
    res = client.get(f"/api/v1/jobs/{job_id}/plan-request")
    assert res.status_code == 200
    payload = res.json()
    assert payload["jobId"] == job_id
    assert payload["llmMode"] == "external"
    assert isinstance(payload.get("planRequest"), dict)
    msgs = payload["planRequest"].get("messages")
    assert isinstance(msgs, list) and len(msgs) >= 2
    assert msgs[0]["role"] == "system"
    assert msgs[1]["role"] == "user"

    # Submit a minimal valid plan
    plan = {
        "schemaVersion": "2026-02-06",
        "contentBlocks": [
            {
                "blockId": "b0",
                "idx": 0,
                "title": "Intro",
                "startMs": 0,
                "endMs": 1000,
                "highlights": [
                    {
                        "highlightId": "h0",
                        "idx": 0,
                        "text": "Hello world",
                        "startMs": 0,
                        "endMs": 1000,
                        "keyframes": [],
                    }
                ],
            }
        ],
        "mindmap": {
            "nodes": [
                {"id": "root", "type": "root", "label": "Root", "level": 0, "data": {}},
                {"id": "t0", "type": "topic", "label": "Intro", "level": 1, "data": {"targetBlockId": "b0"}},
                {
                    "id": "d0",
                    "type": "detail",
                    "label": "Hello world",
                    "level": 2,
                    "data": {"targetBlockId": "b0", "targetHighlightId": "h0"},
                },
            ],
            "edges": [
                {"id": "e0", "source": "root", "target": "t0"},
                {"id": "e1", "source": "t0", "target": "d0"},
            ],
        },
    }

    res = client.post(f"/api/v1/jobs/{job_id}/plan", json=plan)
    assert res.status_code == 200
    out = res.json()
    assert out["jobId"] == job_id
    assert out["status"] == "queued"

    # Verify persisted
    from core.db.session import get_sessionmaker
    from core.db.models.job import Job

    SessionLocal = get_sessionmaker()
    with SessionLocal() as session:
        job = session.get(Job, job_id)
        assert job is not None
        assert job.status == "queued"
        assert isinstance(job.external_plan, dict)
        assert job.external_plan.get("schemaVersion") == "2026-02-06"
