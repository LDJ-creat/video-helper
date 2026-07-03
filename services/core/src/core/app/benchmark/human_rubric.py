from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping


def load_rubric_template(repo_root: Path) -> dict[str, Any]:
	path = repo_root / "benchmarks" / "golden" / "rubric.template.json"
	if not path.exists():
		raise FileNotFoundError(path)
	obj = json.loads(path.read_text(encoding="utf-8"))
	if not isinstance(obj, dict):
		raise ValueError("rubric template must be an object")
	return obj


def validate_rubric_scores(payload: Mapping[str, Any], *, template: Mapping[str, Any]) -> dict[str, Any]:
	dims = template.get("dimensions")
	if not isinstance(dims, list):
		raise ValueError("template.dimensions missing")

	scale = template.get("scale") if isinstance(template.get("scale"), dict) else {}
	min_score = int(scale.get("min", 1))
	max_score = int(scale.get("max", 5))

	dimensions_in = payload.get("dimensions")
	if not isinstance(dimensions_in, dict):
		raise ValueError("dimensions must be an object")

	normalized: dict[str, dict[str, Any]] = {}
	for dim in dims:
		if not isinstance(dim, dict):
			continue
		dim_id = str(dim.get("id") or "")
		if not dim_id:
			continue
		entry = dimensions_in.get(dim_id)
		if not isinstance(entry, dict):
			raise ValueError(f"missing dimension: {dim_id}")
		score = entry.get("score")
		if not isinstance(score, int) or score < min_score or score > max_score:
			raise ValueError(f"invalid score for {dim_id}")
		note = entry.get("note")
		normalized[dim_id] = {
			"score": int(score),
			"note": str(note) if isinstance(note, str) else "",
		}

	if not normalized:
		raise ValueError("no dimensions scored")

	scores = [v["score"] for v in normalized.values()]
	mean_score = round(sum(scores) / len(scores), 4)
	passed_threshold = float(template.get("passedMeanScoreMin", 3.5))
	return {
		"passed": mean_score >= passed_threshold,
		"scores": {k: v["score"] for k, v in normalized.items()},
		"dimensions": normalized,
		"meanScore": mean_score,
	}


def find_rubric_score_file(*, repo_root: Path, profile: str, job_id: str) -> Path | None:
	scores_dir = repo_root / "benchmarks" / "golden" / profile / "scores"
	if not scores_dir.exists():
		return None
	candidates = sorted(scores_dir.glob(f"*_{job_id}.json"), reverse=True)
	return candidates[0] if candidates else None


def load_human_rubric_for_report(
	*,
	repo_root: Path,
	profile: str | None,
	job_id: str,
	rubric_scores_path: Path | None = None,
) -> dict[str, Any] | None:
	path = rubric_scores_path
	if path is None and profile:
		path = find_rubric_score_file(repo_root=repo_root, profile=profile, job_id=job_id)
	if path is None or not path.exists():
		return None
	try:
		payload = json.loads(path.read_text(encoding="utf-8"))
	except (OSError, json.JSONDecodeError):
		return None
	if not isinstance(payload, dict):
		return None
	template = load_rubric_template(repo_root)
	validated = validate_rubric_scores(payload, template=template)
	return {
		"passed": validated["passed"],
		"scores": validated["scores"],
		"dimensions": validated["dimensions"],
		"meanScore": validated["meanScore"],
		"scoredAtMs": payload.get("scoredAtMs"),
		"scorer": payload.get("scorer"),
		"sourcePath": path.as_posix(),
	}
