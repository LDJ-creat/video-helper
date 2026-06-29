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
			key = key.strip()
			value = value.strip().strip('"').strip("'")
			if key:
				os.environ.setdefault(key, value)
	except OSError:
		return


def _default_data_dir() -> Path:
	raw = os.environ.get("DATA_DIR")
	if raw and raw.strip():
		return Path(raw.strip()).resolve()
	return Path(__file__).resolve().parents[3] / "data"


def main() -> int:
	parser = argparse.ArgumentParser(description="Collect L1 job performance metrics")
	parser.add_argument("--data-dir", default="")
	parser.add_argument("--job-id", required=True)
	parser.add_argument("--project-id", default="")
	parser.add_argument("--out", default="")
	args = parser.parse_args()

	core_root = Path(__file__).resolve().parents[1]
	_load_env_file(core_root / ".env")
	src_dir = core_root / "src"
	if str(src_dir) not in sys.path:
		sys.path.insert(0, str(src_dir))

	from core.app.benchmark.job_metrics import collect_job_metrics  # noqa: E402

	data_dir = Path(args.data_dir).resolve() if args.data_dir else _default_data_dir()
	out = collect_job_metrics(
		data_dir=data_dir,
		job_id=str(args.job_id).strip(),
		project_id=str(args.project_id).strip() or None,
	)
	text = json.dumps(out, ensure_ascii=False, indent=2)
	if args.out:
		Path(args.out).write_text(text, encoding="utf-8")
	else:
		print(text)
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
