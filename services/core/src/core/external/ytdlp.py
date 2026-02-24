from __future__ import annotations

import importlib.util
import os
import re
import shutil
import subprocess
import sys
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


def _sanitize_output_tail(output: str, *, max_lines: int = 14) -> str:
	lines = [ln.rstrip() for ln in (output or "").splitlines() if ln.strip()]
	if not lines:
		return ""
	tail = lines[-max_lines:]
	# Strip absolute filesystem paths which may include usernames.
	# - Windows drive paths: C:\...
	# - UNC paths: \\server\share\...
	# - POSIX absolute paths: /... (but not URLs like https:// which contain //)
	path_re = re.compile(r"(?:[A-Za-z]:\\[^\s]+|\\\\[^\s]+|/(?!/)[^\s]+)")
	safe: list[str] = []
	for ln in tail:
		safe.append(path_re.sub("<path>", ln))
	return "\n".join(safe)


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
	"""
	out_dir = output_template.parent
	# Use --paths to force output placement; keep -o as a filename template
	# to avoid Windows path parsing edge cases.
	out_name = output_template.name
	# Default to video+audio for closed-loop (keyframes extraction requires video).
	# Still fully overridable via YTDLP_FORMAT env (e.g., bestaudio/best).
	fmt = _env_str("YTDLP_FORMAT") or "bestvideo+bestaudio/best"
	# Prefer conservative, repeatable network behavior. Keep overridable via env.
	# Note: yt-dlp accepts integers for retries.
	retries = _env_str("YTDLP_RETRIES") or "5"
	fragment_retries = _env_str("YTDLP_FRAGMENT_RETRIES") or "5"
	socket_timeout = _env_str("YTDLP_SOCKET_TIMEOUT")
	return [
		"yt-dlp",
		"--ignore-config",
		"--no-playlist",
		"--no-progress",
		"--retries",
		retries,
		"--fragment-retries",
		fragment_retries,
		"--retry-sleep",
		"fragment:1",
		"--format",
		fmt,
		*( ["--socket-timeout", socket_timeout] if socket_timeout else [] ),
		"--paths",
		str(out_dir),
		"-o",
		out_name,
		url,
	]


def _env_str(name: str) -> str | None:
	raw = (os.environ.get(name) or "").strip()
	return raw or None


def _apply_optional_network_args(cmd: list[str]) -> list[str]:
	# Optional headers/cookies for sites with anti-bot checks (e.g. bilibili 412).
	user_agent = _env_str("YTDLP_USER_AGENT")
	referer = _env_str("YTDLP_REFERER")
	cookies_file = _env_str("YTDLP_COOKIES_FILE")
	cookies_from_browser = _env_str("YTDLP_COOKIES_FROM_BROWSER")

	out: list[str] = list(cmd)
	if user_agent:
		out.extend(["--user-agent", user_agent])
	if referer:
		out.extend(["--referer", referer])
	if cookies_file:
		out.extend(["--cookies", cookies_file])
	if cookies_from_browser:
		out.extend(["--cookies-from-browser", cookies_from_browser])
	return out


def _resolve_ytdlp_runner() -> list[str] | None:
	# IMPORTANT (PyInstaller): in frozen builds, sys.executable is the packaged
	# app (e.g. backend.exe), not a Python interpreter. Running
	#   sys.executable -m yt_dlp
	# would re-launch the backend server instead of yt-dlp.
	is_frozen = bool(getattr(sys, "frozen", False))
	if is_frozen:
		# Prefer standalone executable on PATH (desktop app prepends _internal).
		if shutil.which("yt-dlp"):
			return ["yt-dlp"]
		return None

	# Dev/venv: Prefer the Python module in the current environment: it's
	# deterministic and avoids PATH picking up a mismatched/old executable.
	try:
		spec = importlib.util.find_spec("yt_dlp")
	except Exception:
		spec = None
	if spec is not None:
		return [sys.executable, "-m", "yt_dlp"]

	# Fallback: standalone executable on PATH.
	if shutil.which("yt-dlp"):
		return ["yt-dlp"]

	return None


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
	# Pick newest file matching base_filename.* (search recursively because some
	# extractors may create subfolders depending on config/playlist handling).
	candidates = [p for p in output_dir.rglob(f"{base_filename}.*") if p.is_file()]
	candidates = sorted(candidates, key=lambda p: p.stat().st_mtime, reverse=True)
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

	# Fast fail on obviously invalid but "supported" URLs that yt-dlp may treat as
	# a generic page and still exit 0 (producing no file).
	try:
		from urllib.parse import parse_qs, urlsplit

		parts = urlsplit(url)
		host = (parts.netloc or "").lower()
		path = (parts.path or "").rstrip("/")
		if host.endswith("youtube.com") and path == "/watch":
			qs = parse_qs(parts.query or "")
			v = (qs.get("v") or [""])[0].strip()
			if not v:
				raise YtDlpError(
					"content_error",
					"invalid YouTube URL: missing v parameter",
					details={"type": "invalid_source_url", "source": _redact_url(url)},
				)
	except YtDlpError:
		raise
	except Exception:
		# If parsing fails, let yt-dlp handle it.
		pass

	runner = _resolve_ytdlp_runner()
	if not runner:
		raise YtDlpError("dependency_missing", "yt-dlp is missing")

	output_dir.mkdir(parents=True, exist_ok=True)
	output_template = output_dir / f"{base_filename}.%(ext)s"
	cmd = runner + build_ytdlp_command(url=url, output_template=output_template)[1:]
	cmd = _apply_optional_network_args(cmd)

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
		blocked = False
		http_status: int | None = None
		cookies_error: str | None = None
		# Best-effort detect HTTP status. (Used for friendly operator messaging.)
		m = re.search(r"HTTP\s+Error\s+(?P<code>\d{3})", output)
		if m:
			try:
				http_status = int(m.group("code"))
			except Exception:
				http_status = None
		if http_status in {403, 412, 429} or "Precondition Failed" in output:
			blocked = True
		if "Could not copy Chrome cookie database" in output:
			cookies_error = "cookie_db_copy_failed"
		if "Failed to decrypt with DPAPI" in output:
			cookies_error = "cookie_dpapi_decrypt_failed"
		raise YtDlpError(
			"content_error",
			"yt-dlp failed",
			details={
				"source": safe_url,
				"blocked": blocked,
				"httpStatus": http_status,
				"cookiesError": cookies_error,
				"outputTail": _sanitize_output_tail(output),
			},
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

	# Prefer filesystem discovery (works reliably with a fixed output template).
	abs_path: Path | None = _pick_downloaded_file(output_dir=output_dir, base_filename=base_filename)

	# Back-compat: if yt-dlp printed an absolute path and it exists, trust it.
	if abs_path is None and last_path:
		candidate = Path(last_path)
		if candidate.exists():
			abs_path = candidate

	if abs_path is None or not abs_path.exists():
		safe_url = _redact_url(url)
		raise YtDlpError(
			"output_not_found",
			"yt-dlp succeeded but output file not found",
			details={"source": safe_url, "outputTail": _sanitize_output_tail(output)},
		)

	abs_path2, rel = _ensure_under_data_dir(abs_path)
	return YtDlpDownloadResult(abs_path=abs_path2, rel_path=rel)


def fetch_video_title(*, url: str, timeout_s: float = 15.0) -> str | None:
	"""Best-effort fetch a video's title via yt-dlp without downloading.

	Returns None on failure. Never raises YtDlpError.
	"""

	runner = _resolve_ytdlp_runner()
	if not runner:
		return None

	cmd = runner + [
		"--ignore-config",
		"--no-playlist",
		"--skip-download",
		"--no-warnings",
		"--no-progress",
		"--print",
		"%(title)s",
		url,
	]
	cmd = _apply_optional_network_args(cmd)

	try:
		completed = subprocess.run(
			cmd,
			stdout=subprocess.PIPE,
			stderr=subprocess.STDOUT,
			text=True,
			timeout=float(timeout_s),
			check=False,
			creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
		)
	except Exception:
		return None

	if completed.returncode != 0:
		return None

	out = (completed.stdout or "").strip()
	if not out:
		return None

	for raw in out.splitlines():
		line = (raw or "").strip()
		if not line:
			continue
		# Keep a reasonable bound to avoid pathological output.
		return line[:300]

	return None


def probe_url_support(*, url: str, timeout_s: float = 8.0) -> tuple[bool | None, dict]:
	"""Probe whether yt-dlp recognizes a URL (without downloading).

	Returns:
	- (True, {"extractor": str}) when yt-dlp successfully matches an extractor
	- (False, {"reason": "unsupported_url"}) when yt-dlp reports the URL is unsupported
	- (None, {"reason": ...}) when the probe is inconclusive (timeout/blocked/etc)

	Never raises YtDlpError.
	"""

	runner = _resolve_ytdlp_runner()
	if not runner:
		return None, {"reason": "dependency_missing"}

	cmd = runner + [
		"--ignore-config",
		"--no-playlist",
		"--skip-download",
		"--no-warnings",
		"--no-progress",
		"--print",
		"%(extractor)s",
		url,
	]
	cmd = _apply_optional_network_args(cmd)

	try:
		completed = subprocess.run(
			cmd,
			stdout=subprocess.PIPE,
			stderr=subprocess.STDOUT,
			text=True,
			timeout=float(timeout_s),
			check=False,
			creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
		)
	except subprocess.TimeoutExpired:
		return None, {"reason": "timeout"}
	except Exception:
		return None, {"reason": "probe_failed"}

	out = (completed.stdout or "").strip()
	if completed.returncode == 0:
		for raw in out.splitlines():
			line = (raw or "").strip()
			if line:
				return True, {"extractor": line[:80]}
		return True, {"extractor": None}

	low = out.lower()
	# yt-dlp typically emits one of these for unsupported URLs.
	if "unsupported url" in low or "no suitable extractor" in low:
		return False, {"reason": "unsupported_url", "source": _redact_url(url)}

	# Anything else could be blocked / requires cookies / transient.
	return None, {"reason": "inconclusive", "source": _redact_url(url)}
