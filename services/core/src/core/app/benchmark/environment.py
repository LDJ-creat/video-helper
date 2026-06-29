from __future__ import annotations

import os
import subprocess
from typing import Any


def _env_snapshot_keys() -> tuple[str, ...]:
	return (
		"TRANSCRIBE_MODEL_SIZE",
		"TRANSCRIBE_DEVICE",
		"TRANSCRIBE_COMPUTE_TYPE",
		"LLM_MODEL",
		"LLM_API_BASE",
		"MAX_CONCURRENT_JOBS",
		"CHUNK_LLM_MAX_CONCURRENCY",
		"WORKER_ENABLE",
	)


def collect_environment_snapshot() -> dict[str, Any]:
	out: dict[str, Any] = {}
	for key in _env_snapshot_keys():
		val = os.environ.get(key)
		if val is not None and str(val).strip():
			if key == "LLM_API_KEY":
				continue
			out[key] = str(val).strip()
	try:
		sha = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], stderr=subprocess.DEVNULL, text=True).strip()
		if sha:
			out["gitSha"] = sha
	except Exception:
		pass
	return out
