from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from core.app.smoke.closed_loop import SmokeValidationError, validate_result_dto

# Soft-check minimums and weights (sum = 1.0).
_SOFT_CHECKS: tuple[tuple[str, float, float], ...] = (
	("blocks_count", 2.0, 0.10),
	("highlights_count", 5.0, 0.10),
	("mindmap_nodes", 3.0, 0.10),
	("keyframe_coverage", 0.5, 0.20),
	("timestamp_in_range", 1.0, 0.20),
	("timestamp_monotonic", 1.0, 0.15),
	("mindmap_link_rate", 0.8, 0.15),
)

_KEYFRAME_PIPELINE_STEPS = frozenset({"keyframes.extract", "keyframes", "keyframe_verify"})
_KEYFRAME_EXTRACT_NOOP_MAX_MS = 500


def _keyframes_stage_ran(pipeline_stages: Mapping[str, Any] | None) -> bool:
	if not pipeline_stages:
		return False
	for step in _KEYFRAME_PIPELINE_STEPS:
		if step in pipeline_stages:
			return True
	return False


def _keyframes_extract_entry(pipeline_stages: Mapping[str, Any] | None) -> dict[str, Any] | None:
	if not pipeline_stages:
		return None
	entry = pipeline_stages.get("keyframes.extract")
	return entry if isinstance(entry, dict) else None


def _keyframes_extract_noop(pipeline_stages: Mapping[str, Any] | None, *, coverage: float) -> bool:
	"""True when extract step ran but exited quickly with no keyframes in Result."""
	if coverage > 0:
		return False
	entry = _keyframes_extract_entry(pipeline_stages)
	if entry is None:
		return False
	duration = entry.get("durationMs")
	return isinstance(duration, (int, float)) and 0 <= int(duration) < _KEYFRAME_EXTRACT_NOOP_MAX_MS


def _keyframe_coverage_skip_reason(
	*,
	pipeline_stages: Mapping[str, Any] | None,
	coverage: float,
) -> str | None:
	if not _keyframes_stage_ran(pipeline_stages):
		return "keyframes_stage_not_executed"
	if _keyframes_extract_noop(pipeline_stages, coverage=coverage):
		return "keyframes_extract_no_output"
	return None


def _as_int_ms(value: object) -> int | None:
	if isinstance(value, bool):
		return None
	if isinstance(value, int):
		return value
	if isinstance(value, float):
		return int(value)
	return None


def _estimate_duration_ms(result: Mapping[str, Any]) -> int | None:
	blocks = result.get("contentBlocks")
	if not isinstance(blocks, list):
		return None
	max_end: int | None = None
	for block in blocks:
		if not isinstance(block, dict):
			continue
		end_ms = _as_int_ms(block.get("endMs"))
		if end_ms is not None and end_ms >= 0:
			max_end = end_ms if max_end is None else max(max_end, end_ms)
	return max_end


def _compute_checks(
	result: Mapping[str, Any],
	*,
	duration_ms: int | None,
	pipeline_stages: Mapping[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
	blocks = result.get("contentBlocks") if isinstance(result.get("contentBlocks"), list) else []
	mindmap = result.get("mindmap") if isinstance(result.get("mindmap"), dict) else {}
	nodes = mindmap.get("nodes") if isinstance(mindmap.get("nodes"), list) else []

	highlight_count = 0
	keyframe_count = 0
	timestamp_total = 0
	timestamp_ok = 0
	prev_start: int | None = None
	monotonic_ok = True

	for block in blocks:
		if not isinstance(block, dict):
			continue
		start_ms = _as_int_ms(block.get("startMs"))
		end_ms = _as_int_ms(block.get("endMs"))
		if start_ms is not None and prev_start is not None and start_ms < prev_start:
			monotonic_ok = False
		if start_ms is not None:
			prev_start = start_ms

		for field, val in (("startMs", start_ms), ("endMs", end_ms)):
			if val is None:
				continue
			timestamp_total += 1
			if duration_ms is None or (0 <= val <= duration_ms):
				timestamp_ok += 1

		highlights = block.get("highlights")
		if not isinstance(highlights, list):
			continue
		for highlight in highlights:
			if not isinstance(highlight, dict):
				continue
			highlight_count += 1
			if isinstance(highlight.get("keyframe"), dict):
				keyframe_count += 1
			for field in ("startMs", "endMs"):
				val = _as_int_ms(highlight.get(field))
				if val is None:
					continue
				timestamp_total += 1
				if duration_ms is None or (0 <= val <= duration_ms):
					timestamp_ok += 1

	non_root_nodes = 0
	linked_nodes = 0
	for node in nodes:
		if not isinstance(node, dict):
			continue
		node_type = str(node.get("type") or "").lower()
		if node_type == "root":
			continue
		non_root_nodes += 1
		data = node.get("data") if isinstance(node.get("data"), dict) else {}
		if isinstance(data.get("targetBlockId"), str) and data.get("targetBlockId"):
			linked_nodes += 1

	keyframe_coverage = (keyframe_count / highlight_count) if highlight_count > 0 else 0.0
	timestamp_in_range = (timestamp_ok / timestamp_total) if timestamp_total > 0 else 1.0
	mindmap_link_rate = (linked_nodes / non_root_nodes) if non_root_nodes > 0 else 1.0

	raw = {
		"blocks_count": float(len(blocks)),
		"highlights_count": float(highlight_count),
		"mindmap_nodes": float(len(nodes)),
		"keyframe_coverage": keyframe_coverage,
		"timestamp_in_range": timestamp_in_range,
		"timestamp_monotonic": 1.0 if monotonic_ok else 0.0,
		"mindmap_link_rate": mindmap_link_rate,
	}

	checks: dict[str, dict[str, Any]] = {}
	skip_reason = _keyframe_coverage_skip_reason(pipeline_stages=pipeline_stages, coverage=raw["keyframe_coverage"])
	for name, minimum, _weight in _SOFT_CHECKS:
		value = raw[name]
		if name == "keyframe_coverage" and skip_reason:
			checks[name] = {
				"value": value,
				"min": minimum,
				"ok": None,
				"skipped": True,
				"reason": skip_reason,
			}
			continue
		if name in {"blocks_count", "highlights_count", "mindmap_nodes"}:
			ok = value >= minimum
		else:
			ok = value >= minimum
		checks[name] = {"value": value, "min": minimum, "ok": ok}
	return checks


def _weighted_score(checks: Mapping[str, Mapping[str, Any]]) -> float:
	total = 0.0
	weight_sum = 0.0
	for name, minimum, weight in _SOFT_CHECKS:
		check = checks.get(name) or {}
		if check.get("skipped") is True:
			continue
		weight_sum += weight
		value = float(check.get("value") or 0.0)
		minimum = float(check.get("min") or 0.0)
		if name in {"blocks_count", "highlights_count", "mindmap_nodes"}:
			ratio = min(1.0, value / minimum) if minimum > 0 else 1.0
		else:
			ratio = min(1.0, value / minimum) if minimum > 0 else 1.0
		total += ratio * weight
	if weight_sum <= 0:
		return 1.0
	return round(min(1.0, max(0.0, total / weight_sum)), 4)


def score_result_structure(
	result: Mapping[str, Any],
	*,
	duration_ms: int | None = None,
	pipeline_stages: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
	"""Score Result structure (L2). Hard gate via validate_result_dto, then soft metrics."""

	validation_error: str | None = None
	try:
		normalized = validate_result_dto(result)
	except SmokeValidationError as exc:
		normalized = dict(result) if isinstance(result, dict) else {}
		validation_error = str(exc)

	effective_duration = duration_ms if duration_ms is not None else _estimate_duration_ms(normalized)
	checks = _compute_checks(normalized, duration_ms=effective_duration, pipeline_stages=pipeline_stages)
	score = _weighted_score(checks)
	hard_ok = validation_error is None
	soft_ok = all(
		c.get("ok") is not False
		for c in checks.values()
		if c.get("skipped") is not True
	)
	passed = hard_ok and soft_ok

	out: dict[str, Any] = {
		"passed": passed,
		"score": score if hard_ok else 0.0,
		"checks": checks,
	}
	if validation_error:
		out["validationError"] = validation_error
	if effective_duration is not None:
		out["durationMs"] = int(effective_duration)
	return out
