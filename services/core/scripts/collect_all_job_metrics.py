from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any


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


def _default_data_dir() -> Path:
	raw = os.environ.get("DATA_DIR")
	if raw and raw.strip():
		return Path(raw.strip()).resolve()
	return Path(__file__).resolve().parents[3] / "data"


def _scan_succeeded_jobs(data_dir: Path) -> list[dict[str, Any]]:
	db = data_dir / "core.sqlite3"
	if not db.exists():
		return []
	con = sqlite3.connect(str(db))
	con.row_factory = sqlite3.Row
	try:
		cur = con.cursor()
		cur.execute(
			"SELECT job_id, project_id, status FROM jobs WHERE status = 'succeeded' ORDER BY finished_at_ms DESC"
		)
		return [dict(row) for row in cur.fetchall()]
	except sqlite3.Error:
		return []
	finally:
		con.close()


def main() -> int:
	parser = argparse.ArgumentParser(description="Scan succeeded jobs and aggregate metrics summary")
	parser.add_argument("--data-dir", default="")
	parser.add_argument("--limit", type=int, default=50)
	parser.add_argument("--out", default="")
	args = parser.parse_args()

	core_root = Path(__file__).resolve().parents[1]
	_load_env_file(core_root / ".env")
	src_dir = core_root / "src"
	if str(src_dir) not in sys.path:
		sys.path.insert(0, str(src_dir))

	from core.app.benchmark.job_metrics import collect_job_metrics  # noqa: E402

	data_dir = Path(args.data_dir).resolve() if args.data_dir else _default_data_dir()
	rows = _scan_succeeded_jobs(data_dir)[: max(1, args.limit)]
	items: list[dict[str, Any]] = []
	for row in rows:
		try:
			metrics = collect_job_metrics(
				data_dir=data_dir,
				job_id=str(row["job_id"]),
				project_id=str(row["project_id"]),
			)
			items.append(metrics)
		except Exception as exc:
			items.append({"jobId": row.get("job_id"), "error": str(exc)})

	summary = {"count": len(items), "items": items}
	text = json.dumps(summary, ensure_ascii=False, indent=2)
	if args.out:
		Path(args.out).write_text(text, encoding="utf-8")
	else:
		print(text)
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
