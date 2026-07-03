from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


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


def _repo_root() -> Path:
	return Path(__file__).resolve().parents[2]


def main() -> int:
	parser = argparse.ArgumentParser(description="Score golden semantic metrics (L3)")
	parser.add_argument("--result-json", required=True)
	parser.add_argument("--expected-chapters", default="")
	parser.add_argument("--profile", default="")
	parser.add_argument("--out", default="")
	args = parser.parse_args()

	core_root = Path(__file__).resolve().parents[1]
	_load_env_file(core_root / ".env")
	src_dir = core_root / "src"
	if str(src_dir) not in sys.path:
		sys.path.insert(0, str(src_dir))

	from core.app.benchmark.semantic_score import score_semantic_golden  # noqa: E402

	result = json.loads(Path(args.result_json).read_text(encoding="utf-8"))
	expected_path = Path(args.expected_chapters) if args.expected_chapters else None
	if expected_path is None and args.profile:
		expected_path = _repo_root() / "benchmarks" / "golden" / args.profile / "expected_chapters.json"

	expected = None
	if expected_path and expected_path.exists():
		obj = json.loads(expected_path.read_text(encoding="utf-8"))
		if isinstance(obj, list):
			expected = [x for x in obj if isinstance(x, dict)]

	out = score_semantic_golden(result=result, expected_chapters=expected)
	text = json.dumps(out, ensure_ascii=False, indent=2)
	if args.out:
		Path(args.out).write_text(text, encoding="utf-8")
	else:
		print(text)
	return 0 if out.get("passed") else 10


if __name__ == "__main__":
	raise SystemExit(main())
