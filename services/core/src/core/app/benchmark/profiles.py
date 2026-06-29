from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping


def load_profiles(path: Path) -> dict[str, Any]:
	if not path.exists():
		raise FileNotFoundError(path)
	if path.suffix.lower() in {".json"}:
		obj = json.loads(path.read_text(encoding="utf-8"))
		return obj if isinstance(obj, dict) else {"profiles": {}}

	try:
		import yaml  # type: ignore

		obj = yaml.safe_load(path.read_text(encoding="utf-8"))
		return obj if isinstance(obj, dict) else {"profiles": {}}
	except ImportError:
		return _parse_minimal_yaml(path.read_text(encoding="utf-8"))


def get_profile(profiles_doc: dict[str, Any], name: str) -> dict[str, Any]:
	profiles = profiles_doc.get("profiles") if isinstance(profiles_doc.get("profiles"), dict) else {}
	profile = profiles.get(name)
	if not isinstance(profile, dict):
		raise KeyError(f"unknown profile: {name}")
	return profile


def _parse_minimal_yaml(text: str) -> dict[str, Any]:
	profiles: dict[str, Any] = {}
	current: str | None = None
	block: dict[str, Any] = {}
	thresholds: dict[str, Any] = {}
	in_thresholds = False
	for line in text.splitlines():
		stripped = line.strip()
		if not stripped or stripped.startswith("#"):
			continue
		if stripped == "profiles:":
			continue
		if line.startswith("  ") and not line.startswith("    ") and stripped.endswith(":"):
			if current and block:
				if thresholds:
					block["thresholds"] = thresholds
				profiles[current] = block
			current = stripped[:-1]
			block = {}
			thresholds = {}
			in_thresholds = False
			continue
		if "sourceType:" in stripped:
			block["sourceType"] = stripped.split(":", 1)[1].strip()
		elif "file:" in stripped:
			block["file"] = stripped.split(":", 1)[1].strip()
		elif "sourceUrl:" in stripped:
			block["sourceUrl"] = stripped.split(":", 1)[1].strip().strip('"')
		elif "timeoutSec:" in stripped:
			block["timeoutSec"] = int(stripped.split(":", 1)[1].strip())
		elif stripped == "thresholds:":
			in_thresholds = True
		elif in_thresholds and ":" in stripped:
			k, v = stripped.split(":", 1)
			v = v.strip()
			if v.lower() == "true":
				thresholds[k.strip()] = True
			elif v.lower() == "false":
				thresholds[k.strip()] = False
			else:
				try:
					thresholds[k.strip()] = float(v) if "." in v else int(v)
				except ValueError:
					thresholds[k.strip()] = v
	if current and block:
		if thresholds:
			block["thresholds"] = thresholds
		profiles[current] = block
	return {"profiles": profiles}


def profile_env_overrides(profile: Mapping[str, Any]) -> dict[str, str]:
	"""Environment variables to inject when running a benchmark profile."""

	overrides: dict[str, str] = {}
	kv = profile.get("keyframeVerify")
	if isinstance(kv, dict):
		mode = kv.get("mode")
		if isinstance(mode, str) and mode.strip():
			overrides["KEYFRAME_VERIFY_MODE"] = mode.strip()
		max_per_job = kv.get("maxPerJob")
		if isinstance(max_per_job, int) and max_per_job > 0:
			overrides["KEYFRAME_VERIFY_MAX_PER_JOB"] = str(max_per_job)
	return overrides
