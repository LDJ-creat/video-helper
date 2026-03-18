from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.app.pipeline.chunk_summaries import (
    Chunk,
    ChunkSummary,
    _model_validate,
    _normalize_chunk_summary,
    chunk_transcript_segments,
    ensure_chunk_summaries,
    should_use_long_video_path,
)
from core.contracts.stages import PublicStage, to_public_stage
from core.app.pipeline.llm_plan import validate_plan


def _mk_transcript(*, minutes: int, step_s: int = 5) -> dict:
    segments = []
    t = 0
    end = minutes * 60 * 1000
    step_ms = step_s * 1000
    while t < end:
        segments.append({"startMs": t, "endMs": min(end, t + step_ms), "text": f"seg@{t}"})
        t += step_ms
    return {"segments": segments}


def test_stage_mapping_for_internal_substages() -> None:
    assert to_public_stage("chunk_summaries") == PublicStage.ANALYZE
    assert to_public_stage("keyframe_verify") == PublicStage.EXTRACT_KEYFRAMES


def test_should_use_long_video_path_env_thresholds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LONG_VIDEO_MIN_MS", "1000")
    monkeypatch.setenv("LONG_VIDEO_MIN_SEGMENTS", "999999")
    monkeypatch.setenv("LONG_VIDEO_MIN_CHARS", "999999")

    transcript = _mk_transcript(minutes=1)
    segs = [s for s in transcript["segments"] if isinstance(s, dict)]
    total_chars = sum(len(s.get("text", "")) for s in segs)

    assert should_use_long_video_path(duration_ms=2000, segments=segs, total_chars=total_chars) is True


def test_chunk_transcript_segments_deterministic(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CHUNK_TARGET_COUNT", "24")
    monkeypatch.setenv("CHUNK_MIN_WINDOW_MS", str(4 * 60 * 1000))
    monkeypatch.setenv("CHUNK_MAX_WINDOW_MS", str(8 * 60 * 1000))

    transcript = _mk_transcript(minutes=40, step_s=10)
    window_ms_1, chunks_1 = chunk_transcript_segments(transcript=transcript, duration_ms=40 * 60 * 1000)
    window_ms_2, chunks_2 = chunk_transcript_segments(transcript=transcript, duration_ms=40 * 60 * 1000)

    assert window_ms_1 == window_ms_2
    assert [(c.chunk_id, c.start_ms, c.end_ms, len(c.segments)) for c in chunks_1] == [
        (c.chunk_id, c.start_ms, c.end_ms, len(c.segments)) for c in chunks_2
    ]

    # Ensure each segment is assigned exactly once.
    all_ids = [id(s) for c in chunks_1 for s in c.segments]
    assert len(all_ids) == len(set(all_ids))


def test_ensure_chunk_summaries_reuse(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("CHUNK_SUMMARY_PROVIDER", "placeholder")
    monkeypatch.setenv("CHUNK_TARGET_COUNT", "12")
    monkeypatch.setenv("CHUNK_MIN_WINDOW_MS", str(3 * 60 * 1000))
    monkeypatch.setenv("CHUNK_MAX_WINDOW_MS", str(8 * 60 * 1000))

    transcript = _mk_transcript(minutes=30, step_s=10)
    meta = {"sha256": "abc123", "durationMs": 30 * 60 * 1000}

    out1 = ensure_chunk_summaries(
        project_id="p1",
        job_id="j1",
        transcript=transcript,
        transcript_meta=meta,
        output_language="zh",
        duration_ms=30 * 60 * 1000,
    )
    out2 = ensure_chunk_summaries(
        project_id="p1",
        job_id="j1",
        transcript=transcript,
        transcript_meta=meta,
        output_language="zh",
        duration_ms=30 * 60 * 1000,
    )

    assert out1 == out2

    manifest = tmp_path / "p1" / "artifacts" / "j1" / "chunk_summaries" / "manifest.json"
    assert manifest.exists()
    payload = json.loads(manifest.read_text("utf-8"))
    assert payload.get("transcriptSha256") == "abc123"
    assert payload.get("outputLanguage") == "zh"
    assert isinstance(payload.get("chunks"), list) and payload["chunks"]


def test_validate_plan_keeps_keyframe_confidence() -> None:
    plan = {
        "schemaVersion": "2026-02-06",
        "contentBlocks": [
            {
                "blockId": "b0",
                "idx": 0,
                "title": "T",
                "startMs": 0,
                "endMs": 1000,
                "highlights": [
                    {
                        "highlightId": "h0_0",
                        "idx": 0,
                        "text": "H",
                        "startMs": 0,
                        "endMs": 1000,
                        "keyframeConfidence": "low",
                        "keyframes": [{"timeMs": 100}],
                    }
                ],
            }
        ],
        "mindmap": {
            "nodes": [
                {"id": "n_root", "type": "root", "label": "R", "level": 0, "data": {}},
                {"id": "n_b0", "type": "topic", "label": "B", "level": 1, "data": {"targetBlockId": "b0"}},
            ],
            "edges": [{"id": "e0", "source": "n_root", "target": "n_b0"}],
        },
    }

    normalized = validate_plan(plan)
    kfc = normalized["contentBlocks"][0]["highlights"][0].get("keyframeConfidence")
    assert isinstance(kfc, (int, float))
    assert float(kfc) == pytest.approx(0.2)


def test_normalize_chunk_summary_is_robust(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CHUNK_SUMMARY_MAX_CHARS", "20")
    monkeypatch.setenv("CHUNK_MAX_POINTS", "2")
    monkeypatch.setenv("CHUNK_MAX_TERMS", "2")
    monkeypatch.setenv("CHUNK_MAX_KEY_MOMENTS", "2")

    chunk = Chunk(chunk_id="c_1000_2000", start_ms=1000, end_ms=2000, segments=[])
    raw = {
        "summary": None,
        "points": ["p1", {"text": "p2", "importance": "3"}, {"text": "p3", "importance": 99}],
        "terms": ["ASR", {"term": "NLP", "definition": 123}],
        "keyMoments": [
            {"timeMs": "1500", "label": "slide"},
            {"timeMs": 999999, "label": 1},
            {"timeMs": 1100, "label": "extra"},
        ],
    }

    normalized = _normalize_chunk_summary(raw, chunk=chunk)
    parsed = _model_validate(ChunkSummary, normalized)
    out = parsed.model_dump() if hasattr(parsed, "model_dump") else parsed.dict()

    # summary coerced to string and truncated
    assert isinstance(out.get("summary"), str)
    assert len(out["summary"]) <= 20

    # points capped to 2 and importance clamped to 1..3
    assert len(out.get("points") or []) == 2
    assert {p.get("importance") for p in out["points"]} <= {1, 2, 3}

    # terms capped to 2; definition coerced to string if present
    assert len(out.get("terms") or []) == 2
    for t in out["terms"]:
        d = t.get("definition")
        if d is not None:
            assert isinstance(d, str)

    # keyMoments capped to 2; times clamped within chunk bounds; labels are non-empty strings
    assert len(out.get("keyMoments") or []) == 2
    for km in out["keyMoments"]:
        assert 1000 <= int(km["timeMs"]) < 2000
        assert isinstance(km["label"], str) and km["label"].strip()
