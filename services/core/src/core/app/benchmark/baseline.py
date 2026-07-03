from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping


def load_baseline(path: Path) -> dict[str, Any]:
	if not path.exists():
		return {"profiles": {}}
	try:
		obj = json.loads(path.read_text(encoding="utf-8"))
	except (OSError, json.JSONDecodeError):
		return {"profiles": {}}
	return obj if isinstance(obj, dict) else {"profiles": {}}


def compare_to_baseline(
	*,
	profile: str | None,
	job_metrics: Mapping[str, Any],
	structure_score: Mapping[str, Any],
	thresholds: Mapping[str, Any] | None,
	baseline: Mapping[str, Any],
) -> dict[str, Any]:
	"""Compare current run against baseline and profile thresholds."""

	diff: dict[str, Any] = {"passed": True, "alerts": []}
	profiles = baseline.get("profiles") if isinstance(baseline.get("profiles"), dict) else {}
	base = profiles.get(profile) if profile and isinstance(profiles.get(profile), dict) else None

	def _alert(code: str, message: str, **details: Any) -> None:
		diff["passed"] = False
		diff["alerts"].append({"code": code, "message": message, **details})

	if thresholds:
		sf_max = thresholds.get("speedFactorMax")
		if isinstance(sf_max, (int, float)):
			sf = job_metrics.get("speedFactor")
			if isinstance(sf, (int, float)) and sf > float(sf_max):
				_alert("speed_factor_exceeded", f"speedFactor {sf} > max {sf_max}", metric="speedFactor", value=sf, max=sf_max)

		score_min = thresholds.get("structureScoreMin")
		if isinstance(score_min, (int, float)):
			score = structure_score.get("score")
			if isinstance(score, (int, float)) and score < float(score_min):
				_alert("structure_score_below_min", f"structure score {score} < min {score_min}", metric="structureScore", value=score, min=score_min)

		if thresholds.get("jobSuccess") is True and job_metrics.get("status") != "succeeded":
			_alert("job_not_succeeded", f"job status={job_metrics.get('status')}", status=job_metrics.get("status"))

	if base:
		for metric, key in (("e2eMs", "e2eMs"), ("speedFactor", "speedFactor")):
			base_val = base.get(metric)
			cur_val = job_metrics.get(key)
			if not isinstance(base_val, (int, float)) or not isinstance(cur_val, (int, float)):
				continue
			if base_val <= 0:
				continue
			ratio = cur_val / float(base_val)
			if ratio > 1.10:
				_alert(
					"regression_vs_baseline",
					f"{metric} regressed {ratio:.2%} vs baseline",
					metric=metric,
					current=cur_val,
					baseline=base_val,
					ratio=round(ratio, 4),
				)

		base_score = base.get("structureScore")
		cur_score = structure_score.get("score")
		if isinstance(base_score, (int, float)) and isinstance(cur_score, (int, float)):
			if cur_score < float(base_score) - 0.05:
				_alert(
					"structure_regression",
					f"structureScore dropped from {base_score} to {cur_score}",
					metric="structureScore",
					current=cur_score,
					baseline=base_score,
				)

	if base:
		diff["baselineProfile"] = profile
		diff["baseline"] = base
	return diff
