from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class VideoMetadata:
    duration_ms: int | None
    format: str | None
    width: int | None = None
    height: int | None = None
    fps: float | None = None


class MetadataError(RuntimeError):
    def __init__(self, kind: str, message: str) -> None:
        super().__init__(message)
        self.kind = kind


def _resolve_ffprobe_executable() -> str | None:
    resolved = shutil.which("ffprobe")
    if resolved:
        return resolved

    # Frozen backend: executables may be shipped under `_internal`.
    try:
        base_dir = Path(sys.executable).resolve().parent
        suffix = ".exe" if os.name == "nt" else ""
        candidate = base_dir / "_internal" / f"ffprobe{suffix}"
        if candidate.is_file():
            return str(candidate)
        candidate2 = base_dir / f"ffprobe{suffix}"
        if candidate2.is_file():
            return str(candidate2)
    except Exception:
        pass

    return None


def _parse_fps(value: str | None) -> float | None:
    if not value:
        return None
    if "/" in value:
        num_s, den_s = value.split("/", 1)
        try:
            num = float(num_s)
            den = float(den_s)
            if den == 0:
                return None
            return num / den
        except ValueError:
            return None
    try:
        return float(value)
    except ValueError:
        return None


def extract_video_metadata(path: Path) -> VideoMetadata:
    """Best-effort metadata extraction.

    Uses ffprobe if available (part of ffmpeg distributions).

    Raises:
      - MetadataError(kind="dependency_missing")
      - MetadataError(kind="file_unreadable")
      - MetadataError(kind="parse_failed")
    """

    if not path.exists() or not path.is_file():
        raise MetadataError("file_unreadable", "File is not readable")

    ffprobe = _resolve_ffprobe_executable()
    if not ffprobe:
        raise MetadataError("dependency_missing", "ffprobe is missing")

    try:
        completed = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-print_format",
                "json",
                "-show_format",
                "-show_streams",
                str(path),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=5.0,
            check=False,
        )
    except (PermissionError, OSError):
        raise MetadataError("dependency_missing", "ffprobe is not executable")
    except subprocess.TimeoutExpired:
        raise MetadataError("parse_failed", "ffprobe timed out")

    output = (completed.stdout or "").strip()
    if completed.returncode != 0:
        raise MetadataError("parse_failed", "ffprobe failed")

    try:
        payload = json.loads(output)
    except json.JSONDecodeError:
        raise MetadataError("parse_failed", "ffprobe returned invalid json")

    fmt = payload.get("format") if isinstance(payload, dict) else None
    duration_s = None
    format_name = None
    if isinstance(fmt, dict):
        duration_s = fmt.get("duration")
        format_name = fmt.get("format_name")

    duration_ms = None
    if duration_s is not None:
        try:
            duration_ms = int(float(duration_s) * 1000)
        except (TypeError, ValueError):
            duration_ms = None

    width = height = None
    fps = None
    streams = payload.get("streams") if isinstance(payload, dict) else None
    if isinstance(streams, list):
        for stream in streams:
            if not isinstance(stream, dict):
                continue
            if stream.get("codec_type") != "video":
                continue
            try:
                width = int(stream.get("width")) if stream.get("width") is not None else None
                height = int(stream.get("height")) if stream.get("height") is not None else None
            except (TypeError, ValueError):
                width = height = None
            fps = _parse_fps(stream.get("avg_frame_rate"))
            break

    return VideoMetadata(
        duration_ms=duration_ms,
        format=str(format_name) if format_name else None,
        width=width,
        height=height,
        fps=fps,
    )
