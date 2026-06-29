from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
	parser = argparse.ArgumentParser(description="Render benchmark report JSON to HTML")
	parser.add_argument("json_path", help="Path to benchmark report .json")
	parser.add_argument("--out", default="", help="Output .html path (default: same basename as input)")
	args = parser.parse_args()

	core_root = Path(__file__).resolve().parents[1]
	src_dir = core_root / "src"
	if str(src_dir) not in sys.path:
		sys.path.insert(0, str(src_dir))

	from core.app.benchmark.report_html import render_benchmark_report_html_from_json, write_benchmark_report_html

	json_path = Path(args.json_path).resolve()
	if not json_path.exists():
		raise SystemExit(f"file not found: {json_path}")

	payload = json.loads(json_path.read_text(encoding="utf-8"))
	if not isinstance(payload, dict):
		raise SystemExit("report JSON must be an object")

	out_path = Path(args.out).resolve() if args.out else json_path.with_suffix(".html")
	write_benchmark_report_html(payload, html_path=out_path)
	print(f"[html] written: {out_path}")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
