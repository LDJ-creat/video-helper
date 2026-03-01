from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from core.db.session import get_data_dir
from core.storage.safe_paths import PathTraversalBlockedError


@dataclass(frozen=True)
class StoredJson:
	abs_path: Path
	rel_path: str
	sha256: str


def store_transcript_json(*, project_id: str, job_id: str, transcript: dict) -> StoredJson:
	"""Store transcript JSON under DATA_DIR and return relative ref + sha256."""

	data_dir = get_data_dir().resolve()
	abs_dir = (data_dir / project_id / "artifacts" / job_id).resolve()
	if not abs_dir.is_relative_to(data_dir):
		raise PathTraversalBlockedError("artifact dir escapes DATA_DIR")
	abs_dir.mkdir(parents=True, exist_ok=True)

	abs_path = (abs_dir / "transcript.json").resolve()
	if not abs_path.is_relative_to(data_dir):
		raise PathTraversalBlockedError("artifact path escapes DATA_DIR")

	content = json.dumps(transcript, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
	sha256 = hashlib.sha256(content).hexdigest()
	abs_path.write_bytes(content)
	rel_path = abs_path.relative_to(data_dir).as_posix()
	return StoredJson(abs_path=abs_path, rel_path=rel_path, sha256=sha256)
