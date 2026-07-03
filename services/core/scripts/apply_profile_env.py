from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _repo_root() -> Path:
	return Path(__file__).resolve().parents[2]


def main() -> int:
	parser = argparse.ArgumentParser(description="Print profile env overrides as JSON")
	parser.add_argument("--profile", required=True)
	parser.add_argument("--profiles-file", default="")
	args = parser.parse_args()

	core_root = Path(__file__).resolve().parents[1]
	repo_root = _repo_root()
	src_dir = core_root / "src"
	if str(src_dir) not in sys.path:
		sys.path.insert(0, str(src_dir))

	from core.app.benchmark.profiles import get_profile, load_profiles, profile_env_overrides

	profiles_path = Path(args.profiles_file).resolve() if args.profiles_file else repo_root / "benchmarks" / "profiles.yaml"
	doc = load_profiles(profiles_path)
	profile_cfg = get_profile(doc, str(args.profile))
	overrides = profile_env_overrides(profile_cfg)
	print(json.dumps(overrides))
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
