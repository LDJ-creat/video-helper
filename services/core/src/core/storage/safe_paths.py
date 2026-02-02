from __future__ import annotations

import os
from pathlib import Path
from typing import IO

from core.db.session import get_data_dir


class PathTraversalBlockedError(ValueError):
	pass


def _is_relative_to(path: Path, other: Path) -> bool:
	try:
		return path.is_relative_to(other)
	except AttributeError:
		other = other.resolve()
		path = path.resolve()
		return other == path or other in path.parents


def resolve_under_data_dir(relative_path: str | Path) -> Path:
	"""Resolve a relative path under DATA_DIR.

	Raises PathTraversalBlockedError if the resolved path escapes DATA_DIR.
	"""

	data_dir = get_data_dir().resolve()
	rel = Path(relative_path)
	if rel.is_absolute():
		raise PathTraversalBlockedError("absolute path not allowed")

	abs_path = (data_dir / rel).resolve()
	if not _is_relative_to(abs_path, data_dir):
		raise PathTraversalBlockedError("path escapes DATA_DIR")
	return abs_path


def safe_stat_under_data_dir(relative_path: str | Path) -> os.stat_result:
	"""Stat a relative path under DATA_DIR.

	Raises PathTraversalBlockedError if the resolved path escapes DATA_DIR.
	"""

	abs_path = resolve_under_data_dir(relative_path)
	return abs_path.stat()


def safe_open_under_data_dir(relative_path: str | Path, mode: str = "rb") -> IO:
	"""Open a relative path under DATA_DIR.

	Raises PathTraversalBlockedError if the resolved path escapes DATA_DIR.
	"""

	abs_path = resolve_under_data_dir(relative_path)
	return abs_path.open(mode)


def validate_single_dir_name(value: str) -> None:
	"""Validate a single directory name (no separators, no traversal)."""

	if not value or value in {".", ".."}:
		raise PathTraversalBlockedError("invalid directory name")
	# Disallow any path separators or traversal patterns.
	if any(sep in value for sep in ("/", "\\")):
		raise PathTraversalBlockedError("path separators not allowed")
	if ".." in value:
		raise PathTraversalBlockedError("traversal not allowed")
