from __future__ import annotations

import pytest

from core.app.smoke.closed_loop import SmokeValidationError, validate_asset_dto, validate_result_dto


def _valid_result(asset_id: str = "a1") -> dict:
	return {
		"resultId": "r1",
		"projectId": "p1",
		"schemaVersion": "2026-01-29",
		"pipelineVersion": "dev",
		"createdAtMs": 123,
		"contentBlocks": [
			{
				"blockId": "b1",
				"idx": 0,
				"title": "Intro",
				"startMs": 0,
				"endMs": 1000,
				"highlights": [
					{
						"highlightId": "h1",
						"idx": 0,
						"text": "x",
						"startMs": 0,
						"endMs": 10,
						"keyframe": {"assetId": asset_id, "contentUrl": f"/api/v1/assets/{asset_id}/content", "timeMs": 1},
					}
				],
			}
		],
		"mindmap": {"nodes": [{"id": "node_root"}], "edges": []},
		"assetRefs": [{"assetId": asset_id, "kind": "video", "contentUrl": f"/api/v1/assets/{asset_id}/content"}],
	}


def _valid_asset(asset_id: str = "a1") -> dict:
	return {
		"assetId": asset_id,
		"projectId": "p1",
		"kind": "keyframe",
		"origin": "pipeline",
		"mimeType": "image/jpeg",
		"sizeBytes": 10,
		"width": 1,
		"height": 1,
		"chapterId": None,
		"timeMs": 1,
		"createdAtMs": 123,
		"contentUrl": f"/api/v1/assets/{asset_id}/content",
	}


def test_validate_result_ok() -> None:
	out = validate_result_dto(_valid_result())
	assert out["resultId"] == "r1"
	assert out["assetRefs"][0]["assetId"] == "a1"


@pytest.mark.parametrize(
	"mutate,expected",
	[
		(lambda d: d.pop("contentBlocks"), "result.contentBlocks"),
		(lambda d: d.__setitem__("contentBlocks", []), "contentBlocks"),
		(lambda d: d.__setitem__("assetRefs", []), "assetRefs"),
		(lambda d: d.__setitem__("mindmap", {}), "mindmap.nodes"),
		(lambda d: d["mindmap"].__setitem__("nodes", []), "mindmap.nodes"),
	],
)
def test_validate_result_rejects_invalid(mutate, expected: str) -> None:
	d = _valid_result()
	mutate(d)
	with pytest.raises(SmokeValidationError) as ei:
		validate_result_dto(d)
	assert expected in str(ei.value)


def test_validate_asset_ok() -> None:
	out = validate_asset_dto(_valid_asset("a2"), expected_asset_id="a2")
	assert out["contentUrl"].endswith("/content")


def test_validate_asset_rejects_mismatch() -> None:
	with pytest.raises(SmokeValidationError):
		validate_asset_dto(_valid_asset("a1"), expected_asset_id="a2")
