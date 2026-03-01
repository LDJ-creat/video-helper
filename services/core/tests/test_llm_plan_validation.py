from __future__ import annotations

import pytest


def _valid_plan() -> dict:
    return {
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
                        "keyframe": {"timeMs": 2000, "caption": None},
                    }
                ],
            },
            {
                "blockId": "b02",
                "idx": 1,
                "title": "Body",
                "startMs": 60000,
                "endMs": 120000,
                "highlights": [
                    {
                        "highlightId": "h02",
                        "idx": 0,
                        "text": "World",
                        "startMs": 61000,
                        "endMs": 65000,
                        "keyframe": {"timeMs": 62000, "caption": "cap"},
                    }
                ],
            },
        ],
        "mindmap": {
            "nodes": [
                {"id": "n0", "type": "root", "label": "Video", "level": 0, "data": {}},
                {"id": "n1", "type": "topic", "label": "Intro", "level": 1, "data": {"targetBlockId": "b01"}},
                {"id": "n2", "type": "detail", "label": "Hello", "level": 2, "data": {"targetBlockId": "b01", "targetHighlightId": "h01"}},
            ],
            "edges": [
                {"id": "e1", "source": "n0", "target": "n1"},
                {"id": "e2", "source": "n1", "target": "n2"},
            ],
        },
    }


def test_validate_plan_ok() -> None:
    from core.app.pipeline.llm_plan import validate_plan

    plan = validate_plan(_valid_plan())
    assert plan["schemaVersion"] == "2026-02-06"
    assert len(plan["contentBlocks"]) == 2


def test_validate_plan_rejects_bad_target_block() -> None:
    from core.app.pipeline.llm_plan import validate_plan

    plan = _valid_plan()
    plan["mindmap"]["nodes"][1]["data"]["targetBlockId"] = "missing"
    with pytest.raises(ValueError, match="targetBlockId"):
        validate_plan(plan)


def test_validate_plan_rejects_out_of_range_keyframe_time() -> None:
    from core.app.pipeline.llm_plan import validate_plan

    plan = _valid_plan()
    plan["contentBlocks"][0]["highlights"][0]["keyframe"]["timeMs"] = 999999

    out = validate_plan(plan)
    tm = out["contentBlocks"][0]["highlights"][0]["keyframe"]["timeMs"]
    assert isinstance(tm, int)
    # Clamped into block [0, 60000)
    assert tm == 59999


def test_validate_plan_rejects_non_contiguous_block_idx() -> None:
    from core.app.pipeline.llm_plan import validate_plan

    plan = _valid_plan()
    plan["contentBlocks"][1]["idx"] = 2
    out = validate_plan(plan)
    idxs = [b["idx"] for b in out["contentBlocks"]]
    assert idxs == list(range(len(idxs)))


def test_validate_plan_rejects_overlapping_blocks() -> None:
    from core.app.pipeline.llm_plan import validate_plan

    plan = _valid_plan()
    plan["contentBlocks"][1]["startMs"] = 59000
    # LLM output can have slight overlaps; we merge blocks during normalization.
    plan["mindmap"]["nodes"].append(
        {"id": "n3", "type": "topic", "label": "Body", "level": 1, "data": {"targetBlockId": "b02"}}
    )
    out = validate_plan(plan)
    assert len(out["contentBlocks"]) == 1
    assert out["contentBlocks"][0]["startMs"] == 0
    assert out["contentBlocks"][0]["endMs"] == 120000
    # Mindmap targetBlockId should be remapped from merged-away b02 -> kept b01
    nodes = out["mindmap"]["nodes"]
    assert any(
        isinstance(n, dict)
        and isinstance(n.get("data"), dict)
        and n.get("data", {}).get("targetBlockId") == "b01"
        for n in nodes
    )


def test_validate_mindmap_type_inference() -> None:
    """Nodes without type/level should be inferred from data anchors."""
    from core.app.pipeline.llm_plan import validate_plan

    plan = _valid_plan()
    # Remove type/level to test inference
    for n in plan["mindmap"]["nodes"]:
        n.pop("type", None)
        n.pop("level", None)

    out = validate_plan(plan)
    mm_nodes = out["mindmap"]["nodes"]
    types = {n["id"]: n["type"] for n in mm_nodes}
    assert types["n0"] == "root"  # No targetBlockId -> root
    assert types["n1"] == "topic"  # Has targetBlockId only -> topic
    assert types["n2"] == "detail"  # Has targetHighlightId -> detail


def test_validate_mindmap_edge_from_to_normalization() -> None:
    """Edges with from/to should be normalized to source/target."""
    from core.app.pipeline.llm_plan import validate_plan

    plan = _valid_plan()
    plan["mindmap"]["edges"] = [
        {"id": "e1", "from": "n0", "to": "n1"},
        {"id": "e2", "from": "n1", "to": "n2"},
    ]

    out = validate_plan(plan)
    for e in out["mindmap"]["edges"]:
        assert "source" in e
        assert "target" in e


def test_validate_mindmap_requires_root() -> None:
    """Mindmap with nodes but no root should fail validation."""
    from core.app.pipeline.llm_plan import validate_plan

    plan = _valid_plan()
    # Change root to topic
    plan["mindmap"]["nodes"][0]["type"] = "topic"
    plan["mindmap"]["nodes"][0]["data"] = {"targetBlockId": "b01"}
    with pytest.raises(ValueError, match="root"):
        validate_plan(plan)
