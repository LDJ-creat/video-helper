from __future__ import annotations

import importlib.util
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable

from core.contracts.health import DependencyProbe


_DEFAULT_TIMEOUT_S = 2.0


def _run_version_command(args: list[str]) -> str:
    completed = subprocess.run(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=_DEFAULT_TIMEOUT_S,
        check=False,
    )
    return (completed.stdout or "").strip()


def _parse_ffmpeg_version(output: str) -> str | None:
    # Example: "ffmpeg version 6.1.1-full_build-www.gyan.dev ..."
    first_line = output.splitlines()[0] if output else ""
    match = re.search(r"\bffmpeg\s+version\s+([^\s]+)", first_line, flags=re.IGNORECASE)
    return match.group(1) if match else None


def _parse_ytdlp_version(output: str) -> str | None:
    # Example: "2025.01.15"
    line = output.splitlines()[0].strip() if output else ""
    return line or None


def _candidate_executable_names(executable: str) -> list[str]:
    if os.name == "nt" and not executable.lower().endswith(".exe"):
        return [executable, f"{executable}.exe"]
    return [executable]


def _resolve_executable(executable: str) -> str | None:
    resolved = shutil.which(executable)
    if resolved:
        return resolved

    # Fallback: if the process is running inside a venv, console scripts/binaries
    # often live next to `sys.executable` (Windows: .venv\\Scripts, Linux/macOS: bin).
    scripts_dir = Path(sys.executable).resolve().parent
    for name in _candidate_executable_names(executable):
        candidate = scripts_dir / name
        if candidate.is_file():
            return str(candidate)

    # Frozen backend shipped executables (desktop app bundles to `_internal`).
    internal_dir = scripts_dir / "_internal"
    for name in _candidate_executable_names(executable):
        candidate = internal_dir / name
        if candidate.is_file():
            return str(candidate)

    return None


def _check_executable(
    *,
    display_name: str,
    executable: str,
    version_args: list[str],
    version_parser: Callable[[str], str | None],
    missing_actions: list[str],
    not_executable_actions: list[str],
) -> DependencyProbe:
    # IMPORTANT: never expose absolute paths from `shutil.which()`.
    resolved = _resolve_executable(executable)
    if not resolved:
        return DependencyProbe(
            ok=False,
            version=None,
            message=f"{display_name} is missing",
            actions=list(missing_actions),
        )

    try:
        output = _run_version_command([resolved, *version_args])
        version = version_parser(output)
        return DependencyProbe(ok=True, version=version, message=None, actions=[])
    except (PermissionError, OSError):
        # Do not include exception details to avoid leaking paths.
        return DependencyProbe(
            ok=False,
            version=None,
            message=f"{display_name} is not executable",
            actions=list(not_executable_actions),
        )
    except subprocess.TimeoutExpired:
        return DependencyProbe(
            ok=False,
            version=None,
            message=f"{display_name} probe timed out",
            actions=list(not_executable_actions),
        )
    except Exception:
        # Best-effort: never leak stacktrace/paths.
        return DependencyProbe(
            ok=False,
            version=None,
            message=f"{display_name} probe failed",
            actions=list(not_executable_actions),
        )


def check_ffmpeg() -> DependencyProbe:
    return _check_executable(
        display_name="ffmpeg",
        executable="ffmpeg",
        version_args=["-version"],
        version_parser=_parse_ffmpeg_version,
        missing_actions=["Install ffmpeg and add it to PATH"],
        not_executable_actions=["Ensure ffmpeg is executable and allowed by OS policies"],
    )


def check_yt_dlp() -> DependencyProbe:
    # The backend prefers running yt-dlp as a Python module (python -m yt_dlp)
    # when available. Treat it as satisfied to avoid false "missing" banners in
    # packaged desktop builds.
    try:
        spec = importlib.util.find_spec("yt_dlp")
    except Exception:
        spec = None

    if spec is not None:
        version: str | None = None
        try:
            import yt_dlp.version as _yv  # type: ignore

            version = getattr(_yv, "__version__", None) or None
        except Exception:
            version = None

        return DependencyProbe(ok=True, version=version, message=None, actions=[])

    return _check_executable(
        display_name="yt-dlp",
        executable="yt-dlp",
        version_args=["--version"],
        version_parser=_parse_ytdlp_version,
        missing_actions=["Install yt-dlp and add it to PATH"],
        not_executable_actions=["Ensure yt-dlp is executable and allowed by OS policies"],
    )
