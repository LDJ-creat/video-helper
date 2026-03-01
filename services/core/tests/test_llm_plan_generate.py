from __future__ import annotations

import os
from tempfile import TemporaryDirectory

import pytest

from core.app.pipeline.analyze_provider import AnalyzeError


class _StubProvider:
    def __init__(self, payload: dict):
        self._payload = payload

    def generate_json(self, task_name: str, input_dict: dict) -> dict:
        assert task_name == "plan"
        assert isinstance(input_dict, dict)
        return self._payload


def test_generate_plan_happy_path() -> None:
    from core.app.pipeline.llm_plan import generate_plan

    provider = _StubProvider(
        {
            "schemaVersion": "2026-02-06",
            "contentBlocks": [
                {
                    "blockId": "b01",
                    "idx": 0,
                    "title": "Intro",
                    "startMs": 0,
                    "endMs": 60000,
                    "highlights": [
                        {
                            "highlightId": "h01",
                            "idx": 0,
                            "text": "Hello",
                            "startMs": 1000,
                            "endMs": 5000,
                            "keyframe": {"timeMs": 2000},
                        }
                    ],
                }
            ],
            "mindmap": {"nodes": [{"id": "n0", "type": "root", "label": "Root", "level": 0, "data": {}}, {"id": "n1", "type": "topic", "label": "Intro", "level": 1, "data": {"targetBlockId": "b01"}}], "edges": [{"id": "e1", "source": "n0", "target": "n1"}]},
        }
    )

    plan = generate_plan(transcript={"segments": []}, provider=provider)
    assert plan["schemaVersion"] == "2026-02-06"


def test_generate_plan_invalid_output_is_attributed() -> None:
    from core.app.pipeline.llm_plan import generate_plan

    provider = _StubProvider({"not": "a plan"})
    with pytest.raises(AnalyzeError) as ei:
        generate_plan(transcript={"segments": []}, provider=provider)

    err = ei.value.to_error()
    assert err["details"]["reason"] == "invalid_llm_output"
    assert err["details"]["task"] == "plan"


def test_generate_plan_missing_provider_is_missing_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    from core.app.pipeline.llm_plan import generate_plan

    # Isolate sqlite DB so this test doesn't accidentally pick up a developer's
    # local `data/core.sqlite3` with an active LLM selection.
    from core.db.session import reset_db_for_tests

    with TemporaryDirectory() as tmp:
        monkeypatch.setenv("DATA_DIR", tmp)
        reset_db_for_tests()

        # Ensure llm_provider_for_jobs returns None (no DB active + no env creds).
        monkeypatch.delenv("LLM_API_BASE", raising=False)
        monkeypatch.delenv("LLM_API_KEY", raising=False)
        monkeypatch.delenv("LLM_MODEL", raising=False)
        monkeypatch.delenv("LLM_API_KIND", raising=False)
        monkeypatch.delenv("ANTHROPIC_VERSION", raising=False)

        with pytest.raises(AnalyzeError) as ei:
            generate_plan(transcript={"segments": []}, provider=None)

        err = ei.value.to_error()
        assert err["details"]["reason"] == "missing_credentials"
        assert err["details"]["task"] == "plan"
