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


def main() -> int:
	parser = argparse.ArgumentParser(description="Score Result structure (L2)")
	parser.add_argument("--result-json", default="")
	parser.add_argument("--api-base", default="http://127.0.0.1:8000")
	parser.add_argument("--project-id", default="")
	parser.add_argument("--duration-ms", type=int, default=-1)
	parser.add_argument("--out", default="")
	args = parser.parse_args()

	core_root = Path(__file__).resolve().parents[1]
	_load_env_file(core_root / ".env")
	src_dir = core_root / "src"
	if str(src_dir) not in sys.path:
		sys.path.insert(0, str(src_dir))

	from core.app.benchmark.structure_score import score_result_structure  # noqa: E402

	result: dict
	if args.result_json:
		result = json.loads(Path(args.result_json).read_text(encoding="utf-8"))
	elif args.project_id:
		import httpx

		api_base = str(args.api_base).rstrip("/")
		with httpx.Client(timeout=60.0) as client:
			resp = client.get(f"{api_base}/api/v1/projects/{args.project_id}/results/latest")
			resp.raise_for_status()
			data = resp.json()
			if not isinstance(data, dict):
				raise RuntimeError("latest result is not an object")
			result = data
	else:
		parser.error("provide --result-json or --project-id")

	duration_ms = None if args.duration_ms < 0 else int(args.duration_ms)
	out = score_result_structure(result, duration_ms=duration_ms)
	text = json.dumps(out, ensure_ascii=False, indent=2)
	if args.out:
		Path(args.out).write_text(text, encoding="utf-8")
	else:
		print(text)
	return 0 if out.get("passed") else 10


if __name__ == "__main__":
	raise SystemExit(main())
