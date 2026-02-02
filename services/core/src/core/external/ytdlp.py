from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from core.db.session import get_data_dir
from core.storage.safe_paths import PathTraversalBlockedError


class YtDlpError(ValueError):
	def __init__(self, kind: str, message: str, *, details: dict | None = None):
		super().__init__(message)
		self.kind = kind
		self.details = details or {}


@dataclass(frozen=True)
class YtDlpDownloadResult:
	abs_path: Path
	rel_path: str


_LAST_PATH_RE = re.compile(r"^(?:\[download\]\s+)?(?P<path>(?:[A-Za-z]:\\|/).+)$")


def _redact_url(url: str) -> str:
	"""Best-effort redaction: keep scheme+host+path; strip query/fragment."""
	try:
		from urllib.parse import urlsplit, urlunsplit

		parts = urlsplit(url)
		return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
	except Exception:
		return "(invalid-url)"


def build_ytdlp_command(*, url: str, output_template: Path) -> list[str]:
	"""Build yt-dlp command args.

	We rely on `--print filename` to learn the final output path.
	"""
	return [
		"yt-dlp",
		"--no-playlist",
		"--no-progress",
		"--print",
		"filename",
		"-o",
		str(output_template),
		url,
	]


def _ensure_under_data_dir(path: Path) -> tuple[Path, str]:
	data_dir = get_data_dir().resolve()
	abs_path = path.resolve()
	try:
		rel = abs_path.relative_to(data_dir).as_posix()
	except Exception:
		raise PathTraversalBlockedError("download output must be under DATA_DIR")
	return abs_path, rel


def _pick_downloaded_file(*, output_dir: Path, base_filename: str) -> Path | None:
	if not output_dir.exists():
		return None
	# Pick newest file matching base_filename.*
	candidates = sorted(output_dir.glob(f"{base_filename}.*"), key=lambda p: p.stat().st_mtime, reverse=True)
	return candidates[0] if candidates else None


def download_with_ytdlp(
	*,
	url: str,
	output_dir: Path,
	base_filename: str = "source",
	timeout_s: float = 20 * 60,
) -> YtDlpDownloadResult:
	"""Download a URL media using yt-dlp.

	Returns absolute and DATA_DIR-relative paths.

	Raises YtDlpError with kinds:
	- dependency_missing
	- timeout
	- content_error
	- resource_exhausted
	- output_not_found
	"""

	if not shutil.which("yt-dlp"):
		raise YtDlpError("dependency_missing", "yt-dlp is missing")

	output_dir.mkdir(parents=True, exist_ok=True)
	output_template = output_dir / f"{base_filename}.%(ext)s"
	cmd = build_ytdlp_command(url=url, output_template=output_template)

	try:
		completed = subprocess.run(
			cmd,
			stdout=subprocess.PIPE,
			stderr=subprocess.STDOUT,
			text=True,
			timeout=float(timeout_s),
			check=False,
			# Avoid opening a new window on Windows.
			creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
		)
	except subprocess.TimeoutExpired:
		raise YtDlpError("timeout", "yt-dlp timed out")
	except (PermissionError, OSError):
		raise YtDlpError("dependency_missing", "yt-dlp is not executable")

	output = (completed.stdout or "").strip()
	if completed.returncode != 0:
		# Keep errors non-sensitive: do not echo full URL or full command.
		safe_url = _redact_url(url)
		raise YtDlpError(
			"content_error",
			"yt-dlp failed",
			details={"source": safe_url},
		)

	# First try: last printed filename line.
	last_path: str | None = None
	for line in reversed(output.splitlines()):
		line = line.strip()
		if not line:
			continue
		m = _LAST_PATH_RE.match(line)
		if m:
			last_path = m.group("path")
			break
		# Some yt-dlp versions print just the path.
		if os.path.isabs(line) and ("/" in line or "\\" in line):
			last_path = line
			break

	abs_path: Path | None = None
	if last_path:
		candidate = Path(last_path)
		if candidate.exists():
			abs_path = candidate

	if abs_path is None:
		abs_path = _pick_downloaded_file(output_dir=output_dir, base_filename=base_filename)

	if abs_path is None or not abs_path.exists():
		raise YtDlpError("output_not_found", "yt-dlp succeeded but output file not found")

	abs_path2, rel = _ensure_under_data_dir(abs_path)
	return YtDlpDownloadResult(abs_path=abs_path2, rel_path=rel)
