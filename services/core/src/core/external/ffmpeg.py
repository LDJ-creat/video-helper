from __future__ import annotations

import re
import shutil
import subprocess
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


def build_ffmpeg_extract_audio_command(*, input_path: Path, output_path: Path) -> list[str]:
	"""Build ffmpeg command for 16kHz mono PCM wav extraction."""
	return [
		"ffmpeg",
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

	if not shutil.which("ffmpeg"):
		raise FfmpegError("dependency_missing", "ffmpeg is missing")

	output_dir.mkdir(parents=True, exist_ok=True)
	out_path = output_dir / f"{base_filename}.wav"
	cmd = build_ffmpeg_extract_audio_command(input_path=input_path, output_path=out_path)

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
		if any(p.search(output) for p in _NO_AUDIO_PATTERNS):
			raise FfmpegError("no_audio", "media has no decodable audio")
		if any(p.search(output) for p in _RESOURCE_PATTERNS):
			raise FfmpegError("resource_exhausted", "resource exhausted during ffmpeg")
		raise FfmpegError("content_error", "ffmpeg failed")

	if not out_path.exists() or out_path.stat().st_size <= 0:
		raise FfmpegError("content_error", "ffmpeg succeeded but output audio missing")

	abs_path, rel = _ensure_under_data_dir(out_path)
	return AudioExtractResult(abs_path=abs_path, rel_path=rel)
