from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _json_size(obj: object) -> int:
	return len(json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def _count_blocks(blocks: object) -> int:
	return len(blocks) if isinstance(blocks, list) else 0


def append_editing_diff_stat(
	*,
	data_dir: Path,
	project_id: str,
	kind: str,
	before: object,
	after: object,
) -> None:
	"""Best-effort append edit diff stats for L3 evaluation signals."""

	try:
		base = (data_dir.resolve() / project_id / "artifacts" / "editing").resolve()
		base.mkdir(parents=True, exist_ok=True)
		path = base / "diff_stats.jsonl"
		record: dict[str, Any] = {
			"tsMs": int(__import__("time").time() * 1000),
			"projectId": project_id,
			"kind": kind,
			"beforeBytes": _json_size(before),
			"afterBytes": _json_size(after),
			"deltaBytes": _json_size(after) - _json_size(before),
		}
		if kind == "content_blocks":
			record["beforeBlocks"] = _count_blocks(before)
			record["afterBlocks"] = _count_blocks(after)
		elif kind == "mindmap":
			if isinstance(before, dict) and isinstance(after, dict):
				record["beforeNodes"] = len(before.get("nodes") or []) if isinstance(before.get("nodes"), list) else 0
				record["afterNodes"] = len(after.get("nodes") or []) if isinstance(after.get("nodes"), list) else 0
		with path.open("a", encoding="utf-8") as f:
			f.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
	except Exception:
		return
