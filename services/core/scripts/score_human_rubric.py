from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


def _repo_root() -> Path:
	return Path(__file__).resolve().parents[2]


def _load_env_file(path: Path) -> None:
	if not path.exists():
		return
	try:
		for raw in path.read_text(encoding="utf-8").splitlines():
			line = raw.strip()
			if not line or line.startswith("#") or "=" not in line:
				continue
			key, value = line.split("=", 1)
			if key.strip():
				os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
	except OSError:
		return


def _prompt_score(*, dim_id: str, label: str, min_score: int, max_score: int, anchors: dict[str, str]) -> tuple[int, str]:
	print("")
	print(f"## {label} ({dim_id})")
	for level in ("1", "3", "5"):
		anchor = anchors.get(level)
		if anchor:
			print(f"  {level}: {anchor}")
	while True:
		raw = input(f"Score ({min_score}-{max_score}): ").strip()
		try:
			score = int(raw)
		except ValueError:
			print("Please enter an integer.")
			continue
		if score < min_score or score > max_score:
			print(f"Score must be between {min_score} and {max_score}.")
			continue
		break
	note = input("Note (optional): ").strip()
	return score, note


def _print_result_summary(result: dict) -> None:
	blocks = result.get("contentBlocks") if isinstance(result.get("contentBlocks"), list) else []
	mindmap = result.get("mindmap") if isinstance(result.get("mindmap"), dict) else {}
	nodes = mindmap.get("nodes") if isinstance(mindmap.get("nodes"), list) else []
	highlight_count = 0
	print("\n--- Result summary ---")
	for block in blocks:
		if not isinstance(block, dict):
			continue
		title = block.get("title") or block.get("blockId")
		highlights = block.get("highlights") if isinstance(block.get("highlights"), list) else []
		highlight_count += len(highlights)
		print(f"- block: {title} ({len(highlights)} highlights)")
	print(f"- mindmap nodes: {len(nodes)}")
	print(f"- total highlights: {highlight_count}")
	print("---\n")


def main() -> int:
	parser = argparse.ArgumentParser(description="Interactive human rubric scoring for benchmark golden set")
	parser.add_argument("--profile", required=True)
	parser.add_argument("--job-id", required=True)
	parser.add_argument("--project-id", required=True)
	parser.add_argument("--api-base", default="http://127.0.0.1:8000")
	parser.add_argument("--scorer", default="")
	parser.add_argument("--output", default="")
	args = parser.parse_args()

	core_root = Path(__file__).resolve().parents[1]
	repo_root = _repo_root()
	_load_env_file(core_root / ".env")
	src_dir = core_root / "src"
	if str(src_dir) not in sys.path:
		sys.path.insert(0, str(src_dir))

	import httpx

	from core.app.benchmark.human_rubric import load_rubric_template, validate_rubric_scores
	from core.app.benchmark.http_client import get_latest_result

	api_base = str(args.api_base).rstrip("/")
	profile = str(args.profile).strip()
	job_id = str(args.job_id).strip()
	project_id = str(args.project_id).strip()

	template = load_rubric_template(repo_root)
	dims = template.get("dimensions")
	if not isinstance(dims, list):
		raise SystemExit("invalid rubric template: dimensions")

	scale = template.get("scale") if isinstance(template.get("scale"), dict) else {}
	min_score = int(scale.get("min", 1))
	max_score = int(scale.get("max", 5))

	try:
		with httpx.Client(timeout=60.0) as client:
			result = get_latest_result(client=client, api_base=api_base, project_id=project_id)
	except Exception as exc:
		print(f"[warn] could not load result from API: {exc}")
		result = {}

	if isinstance(result, dict):
		_print_result_summary(result)

	rubric_path = repo_root / "benchmarks" / "golden" / profile / "rubric.md"
	if rubric_path.exists():
		print(f"Reference rubric: {rubric_path}")

	scored: dict[str, dict[str, object]] = {}
	for dim in dims:
		if not isinstance(dim, dict):
			continue
		dim_id = str(dim.get("id") or "")
		if not dim_id:
			continue
		label = str(dim.get("label") or dim_id)
		anchors_raw = dim.get("anchors") if isinstance(dim.get("anchors"), dict) else {}
		anchors = {str(k): str(v) for k, v in anchors_raw.items()}
		score, note = _prompt_score(
			dim_id=dim_id,
			label=label,
			min_score=min_score,
			max_score=max_score,
			anchors=anchors,
		)
		scored[dim_id] = {"score": score, "note": note}

	payload: dict[str, object] = {
		"schemaVersion": str(template.get("schemaVersion") or "2026-06-22"),
		"profile": profile,
		"jobId": job_id,
		"projectId": project_id,
		"scoredAtMs": int(datetime.now(tz=timezone.utc).timestamp() * 1000),
		"scorer": str(args.scorer).strip() or getpass.getuser(),
		"dimensions": scored,
	}
	validated = validate_rubric_scores(payload, template=template)
	payload["meanScore"] = validated["meanScore"]

	confirm = input("\nSave scores? [y/N]: ").strip().lower()
	if confirm not in {"y", "yes"}:
		print("Aborted.")
		return 1

	out_path = Path(args.output).resolve() if args.output else None
	if out_path is None:
		date_str = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
		scores_dir = repo_root / "benchmarks" / "golden" / profile / "scores"
		scores_dir.mkdir(parents=True, exist_ok=True)
		out_path = scores_dir / f"{date_str}_{job_id}.json"

	out_path.parent.mkdir(parents=True, exist_ok=True)
	out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
	print(f"[rubric] saved: {out_path}")
	print(f"[rubric] meanScore={validated['meanScore']} passed={validated['passed']}")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
