from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _percentile(values: list[float], pct: float) -> float | None:
	if not values:
		return None
	sorted_vals = sorted(values)
	if len(sorted_vals) == 1:
		return round(sorted_vals[0], 4)
	idx = (len(sorted_vals) - 1) * pct
	lo = int(idx)
	hi = min(lo + 1, len(sorted_vals) - 1)
	weight = idx - lo
	return round(sorted_vals[lo] * (1 - weight) + sorted_vals[hi] * weight, 4)


def _read_verify_results(path: Path) -> list[dict[str, Any]]:
	if not path.exists():
		return []
	rows: list[dict[str, Any]] = []
	try:
		for line in path.read_text(encoding="utf-8").splitlines():
			line = line.strip()
			if not line:
				continue
			try:
				obj = json.loads(line)
			except json.JSONDecodeError:
				continue
			if isinstance(obj, dict):
				rows.append(obj)
	except OSError:
		return []
	return rows


def collect_keyframe_verify_metrics(
	*,
	data_dir: Path,
	project_id: str,
	job_id: str,
) -> dict[str, Any]:
	"""Aggregate keyframe verify outcomes for benchmark reports.

	When verify was off or no artifact exists, returns enabled=false without failing.
	"""

	path = data_dir.resolve() / project_id / "artifacts" / job_id / "keyframe_verify" / "results.jsonl"
	rows = _read_verify_results(path)
	if not rows:
		return {
			"enabled": False,
			"reason": "verify_mode_off_or_no_artifact",
			"confidenceP50": None,
			"confidenceP90": None,
			"keepRate": None,
		}

	confidences: list[float] = []
	kept = 0
	dropped = 0
	retried = 0
	mode: str | None = None

	for row in rows:
		if mode is None and isinstance(row.get("mode"), str):
			mode = row.get("mode")
		conf = row.get("confidence")
		if isinstance(conf, (int, float)):
			confidences.append(max(0.0, min(1.0, float(conf))))
		action = str(row.get("action") or "")
		if action == "kept":
			kept += 1
		elif action == "dropped":
			dropped += 1
		elif action == "retried":
			retried += 1

	count = len(rows)
	keep_rate = round(kept / count, 4) if count > 0 else None
	drop_rate = round(dropped / count, 4) if count > 0 else None
	retry_rate = round(retried / count, 4) if count > 0 else None

	return {
		"enabled": True,
		"reason": None,
		"mode": mode,
		"count": count,
		"keepRate": keep_rate,
		"dropRate": drop_rate,
		"retryRate": retry_rate,
		"confidenceP50": _percentile(confidences, 0.5),
		"confidenceP90": _percentile(confidences, 0.9),
	}
