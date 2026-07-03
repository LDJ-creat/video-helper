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

	_disabled = {
		"enabled": False,
		"reason": "verify_mode_off_or_no_artifact",
		"confidenceP50": None,
		"confidenceP90": None,
		"keepRate": None,
		"overallKeepRate": None,
		"dropRate": None,
		"retryRate": None,
		"retryScheduledRate": None,
		"secondVerifyPassRate": None,
		"dropAfterRetryRate": None,
		"skippedPrepareRate": None,
	}

	path = data_dir.resolve() / project_id / "artifacts" / job_id / "keyframe_verify" / "results.jsonl"
	rows = _read_verify_results(path)
	if not rows:
		return dict(_disabled)

	confidences: list[float] = []
	kept = 0
	dropped = 0
	skipped_prepare = 0
	retry_scheduled = 0
	retried_kept = 0
	retried_dropped = 0
	mode: str | None = None
	requested_mode: str | None = None
	effective_modes: dict[str, int] = {}
	fallback_reasons: dict[str, int] = {}

	for row in rows:
		if mode is None and isinstance(row.get("mode"), str):
			mode = row.get("mode")
		if requested_mode is None and isinstance(row.get("requestedMode"), str):
			requested_mode = row.get("requestedMode")
		effective = row.get("effectiveMode") if isinstance(row.get("effectiveMode"), str) else row.get("mode")
		if isinstance(effective, str) and effective:
			effective_modes[effective] = effective_modes.get(effective, 0) + 1
		fallback = row.get("fallbackReason")
		if isinstance(fallback, str) and fallback:
			fallback_reasons[fallback] = fallback_reasons.get(fallback, 0) + 1
		conf = row.get("confidence")
		if isinstance(conf, (int, float)):
			confidences.append(max(0.0, min(1.0, float(conf))))
		action = str(row.get("action") or "")
		if action == "kept":
			kept += 1
		elif action == "dropped":
			dropped += 1
		elif action == "skipped_prepare":
			skipped_prepare += 1
			dropped += 1
		elif action in {"retry_scheduled", "retried"}:
			retry_scheduled += 1
		elif action == "retried_kept":
			retried_kept += 1
		elif action == "retried_dropped":
			retried_dropped += 1
			dropped += 1

	count = len(rows)
	keep_rate = round(kept / count, 4) if count > 0 else None
	overall_keep_rate = round((kept + retried_kept) / count, 4) if count > 0 else None
	drop_rate = round(dropped / count, 4) if count > 0 else None
	skipped_prepare_rate = round(skipped_prepare / count, 4) if count > 0 else None
	retry_scheduled_rate = round(retry_scheduled / count, 4) if count > 0 else None
	retry_rate = retry_scheduled_rate
	second_denom = retried_kept + retried_dropped
	second_verify_pass_rate = round(retried_kept / second_denom, 4) if second_denom > 0 else None
	drop_after_retry_rate = round(retried_dropped / count, 4) if count > 0 else None

	return {
		"enabled": True,
		"reason": None,
		"mode": mode,
		"requestedMode": requested_mode,
		"effectiveModeCounts": effective_modes or None,
		"fallbackReasonCounts": fallback_reasons or None,
		"count": count,
		"keepRate": keep_rate,
		"overallKeepRate": overall_keep_rate,
		"dropRate": drop_rate,
		"retryRate": retry_rate,
		"retryScheduledRate": retry_scheduled_rate,
		"secondVerifyPassRate": second_verify_pass_rate,
		"dropAfterRetryRate": drop_after_retry_rate,
		"skippedPrepareRate": skipped_prepare_rate,
		"confidenceP50": _percentile(confidences, 0.5),
		"confidenceP90": _percentile(confidences, 0.9),
	}
