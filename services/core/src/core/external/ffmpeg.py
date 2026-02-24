from __future__ import annotations

import re
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from core.db.session import get_data_dir
from core.storage.safe_paths import PathTraversalBlockedError


class FfmpegError(ValueError):
	def __init__(self, kind: str, message: str, *, details: dict | None = None):
		super().__init__(message)
		self.kind = kind
		self.details = details or {}


@dataclass(frozen=True)
class AudioExtractResult:
	abs_path: Path
	rel_path: str


_NO_AUDIO_PATTERNS: tuple[re.Pattern[str], ...] = (
	re.compile(r"Stream map '.*' matches no streams", flags=re.IGNORECASE),
	re.compile(r"Output file #0 does not contain any stream", flags=re.IGNORECASE),
)

_RESOURCE_PATTERNS: tuple[re.Pattern[str], ...] = (
	re.compile(r"No space left on device", flags=re.IGNORECASE),
	re.compile(r"Cannot allocate memory", flags=re.IGNORECASE),
	re.compile(r"Not enough space", flags=re.IGNORECASE),
)


def _sanitize_output_tail(output: str, *, max_lines: int = 14) -> str:
	lines = [ln.rstrip() for ln in (output or "").splitlines() if ln.strip()]
	if not lines:
		return ""
	tail = lines[-max_lines:]
	# Strip absolute filesystem paths which may include usernames.
	path_re = re.compile(r"(?:[A-Za-z]:\\[^\s]+|\\\\[^\s]+|/(?!/)[^\s]+)")
	safe: list[str] = []
	for ln in tail:
		safe.append(path_re.sub("<path>", ln))
	return "\n".join(safe)


def _resolve_ffmpeg_executable() -> str | None:
	resolved = shutil.which("ffmpeg")
	if resolved:
		return resolved

	# Frozen backend: desktop app usually prepends `_internal` to PATH, but keep a
	# robust fallback in case backend is launched without the wrapper.
	try:
		base_dir = Path(sys.executable).resolve().parent
		suffix = ".exe" if os.name == "nt" else ""
		candidate = base_dir / "_internal" / f"ffmpeg{suffix}"
		if candidate.is_file():
			return str(candidate)
		candidate2 = base_dir / f"ffmpeg{suffix}"
		if candidate2.is_file():
			return str(candidate2)
	except Exception:
		pass

	return None


def build_ffmpeg_extract_audio_command(*, ffmpeg: str = "ffmpeg", input_path: Path, output_path: Path) -> list[str]:
	"""Build ffmpeg command for 16kHz mono PCM wav extraction."""
	return [
		ffmpeg,
		"-hide_banner",
		"-nostdin",
		"-y",
		"-i",
		str(input_path),
		"-vn",
		"-ac",
		"1",
		"-ar",
		"16000",
		"-c:a",
		"pcm_s16le",
		"-f",
		"wav",
		str(output_path),
	]


def build_ffmpeg_extract_frame_command(*, ffmpeg: str = "ffmpeg", input_path: Path, output_path: Path, time_s: float) -> list[str]:
	"""Build ffmpeg command for extracting a single video frame as JPEG.

	We place -ss before -i for speed (best-effort seeking).
	"""
	# Use fixed-format time to keep command deterministic.
	time_arg = f"{float(time_s):.3f}"
	return [
		ffmpeg,
		"-hide_banner",
		"-nostdin",
		"-y",
		"-ss",
		time_arg,
		"-i",
		str(input_path),
		"-frames:v",
		"1",
		"-q:v",
		"2",
		str(output_path),
	]


def _ensure_under_data_dir(path: Path) -> tuple[Path, str]:
	data_dir = get_data_dir().resolve()
	abs_path = path.resolve()
	try:
		rel = abs_path.relative_to(data_dir).as_posix()
	except Exception:
		raise PathTraversalBlockedError("ffmpeg output must be under DATA_DIR")
	return abs_path, rel


def extract_audio_wav_16k_mono(
	*,
	input_path: Path,
	output_dir: Path,
	base_filename: str = "audio",
	timeout_s: float = 10 * 60,
) -> AudioExtractResult:
	"""Extract audio from media as 16kHz mono PCM WAV.

	Raises FfmpegError with kinds:
	- dependency_missing
	- timeout
	- content_error
	- no_audio
	- resource_exhausted
	"""

	if not input_path.exists() or not input_path.is_file():
		raise FfmpegError("content_error", "input media file not readable")

	ffmpeg = _resolve_ffmpeg_executable()
	if not ffmpeg:
		raise FfmpegError("dependency_missing", "ffmpeg is missing")

	output_dir.mkdir(parents=True, exist_ok=True)
	out_path = output_dir / f"{base_filename}.wav"
	cmd = build_ffmpeg_extract_audio_command(ffmpeg=ffmpeg, input_path=input_path, output_path=out_path)

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
		raise FfmpegError("timeout", "ffmpeg timed out")
	except (PermissionError, OSError):
		raise FfmpegError("dependency_missing", "ffmpeg is not executable")

	output = (completed.stdout or "").strip()
	if completed.returncode != 0:
		tail = _sanitize_output_tail(output)
		if any(p.search(output) for p in _NO_AUDIO_PATTERNS):
			raise FfmpegError("no_audio", "media has no decodable audio", details={"exitCode": completed.returncode, "ffmpegTail": tail})
		if any(p.search(output) for p in _RESOURCE_PATTERNS):
			raise FfmpegError("resource_exhausted", "resource exhausted during ffmpeg", details={"exitCode": completed.returncode, "ffmpegTail": tail})
		raise FfmpegError("content_error", "ffmpeg failed", details={"exitCode": completed.returncode, "ffmpegTail": tail})

	if not out_path.exists() or out_path.stat().st_size <= 0:
		raise FfmpegError("content_error", "ffmpeg succeeded but output audio missing")

	abs_path, rel = _ensure_under_data_dir(out_path)
	return AudioExtractResult(abs_path=abs_path, rel_path=rel)


def extract_video_frame_jpeg(
	*,
	input_path: Path,
	output_path: Path,
	time_s: float,
	timeout_s: float = 2 * 60,
) -> tuple[Path, str]:
	"""Extract a single video frame to a JPEG file under DATA_DIR.

	Raises FfmpegError with kinds:
	- dependency_missing
	- timeout
	- content_error
	- resource_exhausted
	"""

	if not input_path.exists() or not input_path.is_file():
		raise FfmpegError("content_error", "input media file not readable")

	ffmpeg = _resolve_ffmpeg_executable()
	if not ffmpeg:
		raise FfmpegError("dependency_missing", "ffmpeg is missing")

	output_path.parent.mkdir(parents=True, exist_ok=True)
	cmd = build_ffmpeg_extract_frame_command(ffmpeg=ffmpeg, input_path=input_path, output_path=output_path, time_s=time_s)

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
		raise FfmpegError("timeout", "ffmpeg timed out")
	except (PermissionError, OSError):
		raise FfmpegError("dependency_missing", "ffmpeg is not executable")

	output = (completed.stdout or "").strip()
	if completed.returncode != 0:
		tail = _sanitize_output_tail(output)
		if any(p.search(output) for p in _RESOURCE_PATTERNS):
			raise FfmpegError(
				"resource_exhausted",
				"resource exhausted during ffmpeg",
				details={"exitCode": completed.returncode, "ffmpegTail": tail},
			)
		raise FfmpegError("content_error", "ffmpeg failed", details={"exitCode": completed.returncode, "ffmpegTail": tail})

	if not output_path.exists() or output_path.stat().st_size <= 0:
		raise FfmpegError("content_error", "ffmpeg succeeded but output image missing")

	abs_path, rel = _ensure_under_data_dir(output_path)
	return abs_path, rel
