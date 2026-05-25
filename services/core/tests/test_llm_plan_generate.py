from __future__ import annotations

import os
from tempfile import TemporaryDirectory

import pytest

from core.app.pipeline.analyze_provider import AnalyzeError


class _StubProvider:
    def __init__(self, payload: dict):
        self._payload = payload

    def generate_json(self, task_name: str, input_dict: dict, *, max_tokens: int | None = None) -> dict:
        assert task_name in {"plan_content_blocks", "plan_mindmap", "plan_content_blocks_repair", "plan_mindmap_repair"}
        assert isinstance(input_dict, dict)
        if task_name.startswith("plan_content_blocks"):
            return {
                "schemaVersion": self._payload.get("schemaVersion", "2026-02-06"),
                "contentBlocks": self._payload.get("contentBlocks", []),
            }
        if task_name.startswith("plan_mindmap"):
            return {
                "schemaVersion": self._payload.get("schemaVersion", "2026-02-06"),
                "mindmap": self._payload.get("mindmap", {"nodes": [], "edges": []}),
            }
        return self._payload


class _CountingProvider:
    def __init__(self, *, mindmap: dict):
        self.calls: list[str] = []
        self._mindmap = mindmap

    def generate_json(self, task_name: str, input_dict: dict, *, max_tokens: int | None = None) -> dict:
        self.calls.append(task_name)
        if task_name == "plan_mindmap":
            return {"schemaVersion": "2026-02-06", "mindmap": self._mindmap}
        raise AssertionError(f"unexpected task: {task_name}")


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
    assert err["details"]["task"] == "plan_content_blocks"


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


def test_build_plan_request_omits_transcript_when_summaries_present(monkeypatch: pytest.MonkeyPatch) -> None:
    from core.app.pipeline.llm_plan import build_plan_request

    transcript = {
        "segments": [
            {"startMs": 0, "endMs": 1000, "text": "hello world"},
            {"startMs": 1000, "endMs": 2000, "text": "more text"},
        ]
    }
    summaries = [
        {"chunkId": "c0", "startMs": 0, "endMs": 2000, "summary": "s", "points": [], "terms": [], "keyMoments": []}
    ]

    monkeypatch.delenv("LLM_PLAN_INCLUDE_TRANSCRIPT_WITH_SUMMARIES", raising=False)
    monkeypatch.delenv("LLM_PLAN_INCLUDE_TRANSCRIPT_TEXT_WITH_SUMMARIES", raising=False)
    req = build_plan_request(transcript=transcript, summaries=summaries)
    payload = req.get("userPayload")
    assert isinstance(payload, dict)
    segs = payload.get("transcript", {}).get("segments")
    assert isinstance(segs, list)
    assert segs == [], "expected transcript to be omitted for reduce when summaries exist"


def test_build_plan_request_can_include_timing_anchors_with_summaries_when_opted_in(monkeypatch: pytest.MonkeyPatch) -> None:
    from core.app.pipeline.llm_plan import build_plan_request

    transcript = {
        "segments": [
            {"startMs": 0, "endMs": 1000, "text": "hello world"},
            {"startMs": 1000, "endMs": 2000, "text": "more text"},
        ]
    }
    summaries = [
        {"chunkId": "c0", "startMs": 0, "endMs": 2000, "summary": "s", "points": [], "terms": [], "keyMoments": []}
    ]

    monkeypatch.setenv("LLM_PLAN_INCLUDE_TRANSCRIPT_WITH_SUMMARIES", "1")
    monkeypatch.delenv("LLM_PLAN_INCLUDE_TRANSCRIPT_TEXT_WITH_SUMMARIES", raising=False)
    req = build_plan_request(transcript=transcript, summaries=summaries)
    payload = req.get("userPayload")
    assert isinstance(payload, dict)
    segs = payload.get("transcript", {}).get("segments")
    assert isinstance(segs, list)
    assert segs, "expected some timing anchors"
    assert all(isinstance(s, dict) and "text" not in s for s in segs)


def test_build_plan_request_can_include_transcript_text_with_summaries_when_opted_in(monkeypatch: pytest.MonkeyPatch) -> None:
    from core.app.pipeline.llm_plan import build_plan_request

    transcript = {
        "segments": [
            {"startMs": 0, "endMs": 1000, "text": "hello world"},
            {"startMs": 1000, "endMs": 2000, "text": "more text"},
        ]
    }
    summaries = [
        {"chunkId": "c0", "startMs": 0, "endMs": 2000, "summary": "s", "points": [], "terms": [], "keyMoments": []}
    ]

    monkeypatch.setenv("LLM_PLAN_INCLUDE_TRANSCRIPT_WITH_SUMMARIES", "1")
    monkeypatch.setenv("LLM_PLAN_INCLUDE_TRANSCRIPT_TEXT_WITH_SUMMARIES", "1")
    req = build_plan_request(transcript=transcript, summaries=summaries)
    payload = req.get("userPayload")
    assert isinstance(payload, dict)
    segs = payload.get("transcript", {}).get("segments")
    assert isinstance(segs, list)
    assert any(isinstance(s, dict) and isinstance(s.get("text"), str) and s.get("text") for s in segs)


def test_generate_plan_reuses_cached_content_blocks() -> None:
    from core.app.pipeline.llm_plan import generate_plan

    cached_blocks = [
        {
            "blockId": "b0",
            "idx": 0,
            "title": "Intro",
            "startMs": 0,
            "endMs": 10_000,
            "highlights": [
                {
                    "highlightId": "h0",
                    "idx": 0,
                    "text": "hello",
                    "startMs": 100,
                    "endMs": 2000,
                    "keyframes": [{"timeMs": 300}],
                }
            ],
        }
    ]
    provider = _CountingProvider(
        mindmap={
            "nodes": [
                {"id": "n0", "type": "root", "label": "Root", "level": 0, "data": {}},
                {"id": "n1", "type": "topic", "label": "Intro", "level": 1, "data": {"targetBlockId": "b0"}},
            ],
            "edges": [{"id": "e0", "source": "n0", "target": "n1"}],
        }
    )

    plan = generate_plan(
        transcript={"segments": []},
        provider=provider,
        cached_content_blocks=cached_blocks,
    )

    assert [c for c in provider.calls if c == "plan_content_blocks"] == []
    assert provider.calls == ["plan_mindmap"]
    assert isinstance(plan.get("contentBlocks"), list) and len(plan["contentBlocks"]) == 1


def test_build_plan_mindmap_request_keeps_full_input_by_default_and_concise_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    from core.app.pipeline.llm_plan import build_plan_mindmap_request

    monkeypatch.setenv("LLM_PLAN_MINDMAP_MAX_TOPICS", "2")
    monkeypatch.setenv("LLM_PLAN_MINDMAP_MAX_DETAILS_PER_TOPIC", "1")
    monkeypatch.setenv("LLM_PLAN_MINDMAP_MAX_LABEL_CHARS", "12")

    content_blocks = [
        {
            "blockId": "b0",
            "idx": 0,
            "title": "This is a very long block title that should be compacted",
            "startMs": 0,
            "endMs": 1000,
            "highlights": [
                {
                    "highlightId": "h0",
                    "idx": 0,
                    "text": "This is a very long highlight text that should be truncated",
                    "startMs": 0,
                    "endMs": 500,
                },
                {
                    "highlightId": "h1",
                    "idx": 1,
                    "text": "second",
                    "startMs": 500,
                    "endMs": 800,
                },
            ],
        },
        {
            "blockId": "b1",
            "idx": 1,
            "title": "another title",
            "startMs": 1000,
            "endMs": 2000,
            "highlights": [],
        },
        {
            "blockId": "b2",
            "idx": 2,
            "title": "ignored by max topics",
            "startMs": 2000,
            "endMs": 3000,
            "highlights": [],
        },
    ]

    req = build_plan_mindmap_request(
        content_blocks=content_blocks,
        transcript={"segments": []},
        summaries=None,
        output_language="zh-Hans",
    )

    system = req.get("system")
    assert isinstance(system, str)
    assert "Keep the graph concise" in system
    assert "at most 2 topic nodes" in system

    payload = req.get("userPayload")
    assert isinstance(payload, dict)
    blocks = payload.get("contentBlocks")
    assert isinstance(blocks, list)
    assert len(blocks) == 3
    assert isinstance(blocks[0].get("title"), str)
    assert "should be compacted" in blocks[0]["title"]
    assert isinstance(blocks[0].get("highlights"), list)
    assert len(blocks[0]["highlights"]) == 2
    assert "should be truncated" in blocks[0]["highlights"][0].get("text", "")


def test_build_plan_mindmap_request_uses_adaptive_limits_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    from core.app.pipeline.llm_plan import build_plan_mindmap_request

    monkeypatch.delenv("LLM_PLAN_MINDMAP_MAX_TOPICS_MIN", raising=False)
    monkeypatch.delenv("LLM_PLAN_MINDMAP_MAX_TOPICS", raising=False)
    monkeypatch.delenv("LLM_PLAN_MINDMAP_MAX_DETAILS_PER_TOPIC_MIN", raising=False)
    monkeypatch.delenv("LLM_PLAN_MINDMAP_MAX_DETAILS_PER_TOPIC", raising=False)

    content_blocks = [
        {"blockId": "b0", "idx": 0, "title": "T0", "startMs": 0, "endMs": 1000, "highlights": [{"highlightId": "h0", "idx": 0, "text": "a", "startMs": 0, "endMs": 100}]},
        {"blockId": "b1", "idx": 1, "title": "T1", "startMs": 1000, "endMs": 2000, "highlights": [{"highlightId": "h1", "idx": 0, "text": "b", "startMs": 1000, "endMs": 1100}]},
        {"blockId": "b2", "idx": 2, "title": "T2", "startMs": 2000, "endMs": 3000, "highlights": []},
    ]

    req = build_plan_mindmap_request(
        content_blocks=content_blocks,
        transcript={"segments": []},
        summaries=None,
        output_language="zh-Hans",
    )

    system = req.get("system")
    assert isinstance(system, str)
    assert "at most 3 topic nodes" in system
    assert "at most 2 detail nodes per topic" in system
