from core.app.pipeline.llm_plan import validate_plan


def test_validate_plan_does_not_invent_keyframe_when_missing() -> None:
    plan = {
        "schemaVersion": "2026-02-06",
        "contentBlocks": [
            {
                "blockId": "b0",
                "idx": 0,
                "title": "Block",
                "startMs": 0,
                "endMs": 10_000,
                "highlights": [
                    {
                        "highlightId": "h0_0",
                        "idx": 0,
                        "text": "hello",
                        "startMs": 1000,
                        "endMs": 2000,
                        # keyframe intentionally omitted
                    }
                ],
            }
        ],
        "mindmap": {"nodes": [], "edges": []},
    }

    out = validate_plan(plan)
    h0 = out["contentBlocks"][0]["highlights"][0]
    assert h0.get("keyframe") is None
