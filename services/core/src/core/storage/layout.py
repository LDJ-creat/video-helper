from __future__ import annotations

import re
from pathlib import Path

from core.db.session import get_data_dir


_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


def sanitize_filename(name: str | None, *, default: str = "upload.bin") -> str:
	if not name:
		return default
	name = name.strip().replace("\\", "_").replace("/", "_")
	name = _SAFE_NAME_RE.sub("_", name)
	name = name.strip("._")
	return name or default


def project_dir(project_id: str) -> Path:
	return get_data_dir() / project_id


def job_upload_dir(project_id: str, job_id: str) -> Path:
	return project_dir(project_id) / "uploads" / job_id


def allocate_upload_path(*, project_id: str, job_id: str, original_filename: str | None) -> tuple[Path, str]:
	"""Return (absolute_path, relative_path_under_data_dir)."""

	filename = sanitize_filename(original_filename, default="upload.bin")
	abs_dir = job_upload_dir(project_id, job_id)
	abs_dir.mkdir(parents=True, exist_ok=True)

	abs_path = abs_dir / filename
	rel_path = abs_path.relative_to(get_data_dir()).as_posix()
	return abs_path, rel_path
