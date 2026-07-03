from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def _overlap_ms(a_start: int, a_end: int, b_start: int, b_end: int) -> int:
	start = max(a_start, b_start)
	end = min(a_end, b_end)
	return max(0, end - start)


def score_chapter_boundaries(
	*,
	predicted_blocks: list[Mapping[str, Any]],
	expected_chapters: list[Mapping[str, Any]],
	tolerance_ms: int = 30_000,
) -> dict[str, Any]:
	"""Chapter boundary F1 with ±tolerance_ms matching on time overlap."""

	if not expected_chapters:
		return {"passed": True, "f1": 1.0, "precision": 1.0, "recall": 1.0, "matched": 0, "expected": 0, "predicted": len(predicted_blocks)}

	pred_ranges: list[tuple[int, int]] = []
	for block in predicted_blocks:
		if not isinstance(block, dict):
			continue
		start = block.get("startMs")
		end = block.get("endMs")
		if isinstance(start, int) and isinstance(end, int) and end > start:
			pred_ranges.append((start, end))

	exp_ranges: list[tuple[int, int]] = []
	for chapter in expected_chapters:
		if not isinstance(chapter, dict):
			continue
		start = chapter.get("startMs")
		end = chapter.get("endMs")
		if isinstance(start, int) and isinstance(end, int) and end > start:
			exp_ranges.append((start, end))

	matched_pred = set()
	matched_exp = set()
	for pi, (ps, pe) in enumerate(pred_ranges):
		for ei, (es, ee) in enumerate(exp_ranges):
			if _overlap_ms(ps - tolerance_ms, pe + tolerance_ms, es, ee) > 0:
				matched_pred.add(pi)
				matched_exp.add(ei)

	tp = len(matched_pred)
	fp = max(0, len(pred_ranges) - tp)
	fn = max(0, len(exp_ranges) - len(matched_exp))
	precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
	recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
	f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
	passed = f1 >= 0.7 if exp_ranges else True

	return {
		"passed": passed,
		"f1": round(f1, 4),
		"precision": round(precision, 4),
		"recall": round(recall, 4),
		"matched": tp,
		"expected": len(exp_ranges),
		"predicted": len(pred_ranges),
		"toleranceMs": tolerance_ms,
	}


def score_semantic_golden(
	*,
	result: Mapping[str, Any],
	expected_chapters: list[Mapping[str, Any]] | None = None,
	faithfulness: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
	blocks = result.get("contentBlocks") if isinstance(result.get("contentBlocks"), list) else []
	chapter = score_chapter_boundaries(predicted_blocks=blocks, expected_chapters=expected_chapters or [])
	passed = bool(chapter.get("passed"))
	if faithfulness is not None and faithfulness.get("enabled") is True and not faithfulness.get("skipped"):
		passed = passed and bool(faithfulness.get("passed", True))
	out: dict[str, Any] = {
		"passed": passed,
		"chapterBoundary": chapter,
	}
	if faithfulness is not None:
		out["highlightFaithfulness"] = dict(faithfulness)
	return out
