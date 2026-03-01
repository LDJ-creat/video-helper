#!/usr/bin/env python3
"""
Backend packaging script for Video Helper Desktop.

Steps:
  1. Install PyInstaller into the venv (via uv)
  2. Run PyInstaller with backend.spec
  3. Copy output to apps/desktop/resources/backend/

Usage (from project root):
    python services/core/scripts/build_backend.py

Or from services/core/:
    uv run python scripts/build_backend.py
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path
from typing import Iterable

CORE_DIR = Path(__file__).parent.parent.resolve()
PROJECT_ROOT = CORE_DIR.parent.parent.resolve()
DIST_DIR = CORE_DIR / "dist" / "backend"
RESOURCES_DIR = PROJECT_ROOT / "apps" / "desktop" / "resources" / "backend"


def maybe_fix_conda_libexpat(resources_dir: Path) -> None:
    """PyInstaller + Conda sometimes bundles an incompatible libexpat.dll.

    Symptom in packaged backend.exe:
      ImportError: DLL load failed while importing pyexpat: [WinError 182]

    If we detect a Conda layout, prefer Conda's Library/bin/libexpat.dll.
    """

    if os.name != "nt":
        return

    internal_dir = resources_dir / "_internal"
    if not internal_dir.exists():
        return

    # Conda base prefix: e.g. D:\conda
    conda_libexpat = Path(sys.base_prefix) / "Library" / "bin" / "libexpat.dll"
    target = internal_dir / "libexpat.dll"

    if conda_libexpat.exists() and target.exists():
        print(f"\n[fix] Overriding libexpat.dll with Conda version: {conda_libexpat}")
        shutil.copy2(conda_libexpat, target)
        return

    if conda_libexpat.exists() and not target.exists():
        print(f"\n[fix] Copying Conda libexpat.dll into _internal: {conda_libexpat}")
        shutil.copy2(conda_libexpat, target)


def _pick_first_existing(paths: Iterable[Path]) -> Path | None:
    for p in paths:
        try:
            if p and p.exists() and p.is_file():
                return p
        except Exception:
            continue
    return None


def maybe_bundle_external_executables(resources_dir: Path) -> None:
    """Best-effort bundle external executables into the packaged backend.

    - yt-dlp: improves UX when environment lacks PATH configuration
    - ffmpeg/ffprobe: required for audio extraction/keyframes

    This function does NOT download anything. It only copies from the local
    build environment when available.
    """

    internal_dir = resources_dir / "_internal"
    if not internal_dir.exists():
        return

    exe_suffix = ".exe" if os.name == "nt" else ""

    # Common locations in virtualenv/conda setups.
    venv_bin = Path(sys.executable).resolve().parent
    conda_prefix = Path(sys.base_prefix)

    conda_candidates: dict[str, list[Path]]
    if os.name == "nt":
        conda_candidates = {
            "yt-dlp": [conda_prefix / "Scripts" / f"yt-dlp{exe_suffix}"],
            "ffmpeg": [conda_prefix / "Library" / "bin" / f"ffmpeg{exe_suffix}"],
            "ffprobe": [conda_prefix / "Library" / "bin" / f"ffprobe{exe_suffix}"],
        }
    else:
        conda_candidates = {
            "yt-dlp": [conda_prefix / "bin" / "yt-dlp"],
            "ffmpeg": [conda_prefix / "bin" / "ffmpeg"],
            "ffprobe": [conda_prefix / "bin" / "ffprobe"],
        }

    tools: list[tuple[str, str, list[Path]]] = [
        (
            "yt-dlp",
            f"yt-dlp{exe_suffix}",
            [
                Path(shutil.which("yt-dlp") or ""),
                venv_bin / f"yt-dlp{exe_suffix}",
                *conda_candidates["yt-dlp"],
            ],
        ),
        (
            "ffmpeg",
            f"ffmpeg{exe_suffix}",
            [
                Path(shutil.which("ffmpeg") or ""),
                *conda_candidates["ffmpeg"],
            ],
        ),
        (
            "ffprobe",
            f"ffprobe{exe_suffix}",
            [
                Path(shutil.which("ffprobe") or ""),
                *conda_candidates["ffprobe"],
            ],
        ),
    ]

    for tool_name, dest_name, candidates in tools:
        src = _pick_first_existing(candidates)
        if not src:
            continue

        dest = internal_dir / dest_name
        try:
            shutil.copy2(src, dest)
            if os.name != "nt":
                try:
                    mode = dest.stat().st_mode
                    dest.chmod(mode | 0o111)
                except Exception:
                    pass
            print(f"\n[fix] Bundled {tool_name}: {src}")
        except Exception as e:
            print(f"\n[warn] Failed to bundle {tool_name} from {src}: {e}")


def run(cmd: list[str], cwd: Path = CORE_DIR) -> None:
    print(f"\n$ {' '.join(str(c) for c in cmd)}")
    result = subprocess.run(cmd, cwd=cwd)
    if result.returncode != 0:
        sys.exit(f"Command failed with exit code {result.returncode}")


def main() -> None:
    print("=" * 60)
    print("  Video Helper — Backend Packaging (PyInstaller)")
    print("=" * 60)

    # 1. Install PyInstaller
    print("\n[1/3] Installing PyInstaller...")
    run(["uv", "pip", "install", "pyinstaller"])

    # 2. Build with PyInstaller
    print("\n[2/3] Running PyInstaller...")
    run(["uv", "run", "pyinstaller", "backend.spec", "--clean", "--noconfirm"])

    # 3. Copy to Electron resources
    print(f"\n[3/3] Copying output to: {RESOURCES_DIR}")
    if RESOURCES_DIR.exists():
        shutil.rmtree(RESOURCES_DIR)
    shutil.copytree(DIST_DIR, RESOURCES_DIR)

    # Conda-specific hotfix for WinError 182 (pyexpat load failure)
    maybe_fix_conda_libexpat(RESOURCES_DIR)

    # Best-effort: bundle external executables when present on build machine.
    maybe_bundle_external_executables(RESOURCES_DIR)

    print("\n[ok] Backend packaged successfully!")
    print(f"   Output: {RESOURCES_DIR}")
    exe_name = "backend.exe" if os.name == "nt" else "backend"
    print("\n   Run the backend executable to test:")
    print(f"   {RESOURCES_DIR / exe_name}")


if __name__ == "__main__":
    main()
