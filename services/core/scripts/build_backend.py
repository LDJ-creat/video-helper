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


def maybe_bundle_windows_executables(resources_dir: Path) -> None:
    """Best-effort bundle external executables into the packaged backend.

    - yt-dlp.exe: improves UX when environment lacks PATH configuration
    - ffmpeg.exe/ffprobe.exe: required for audio extraction/keyframes

    This function does NOT download anything. It only copies from the local
    build environment when available.
    """

    if os.name != "nt":
        return

    internal_dir = resources_dir / "_internal"
    if not internal_dir.exists():
        return

    # Common locations in virtualenv/conda setups.
    venv_scripts = Path(sys.executable).resolve().parent
    conda_prefix = Path(sys.base_prefix)
    conda_scripts = conda_prefix / "Scripts"
    conda_bin = conda_prefix / "Library" / "bin"

    tools: list[tuple[str, list[Path]]] = [
        (
            "yt-dlp.exe",
            [
                Path(shutil.which("yt-dlp") or ""),
                venv_scripts / "yt-dlp.exe",
                conda_scripts / "yt-dlp.exe",
            ],
        ),
        (
            "ffmpeg.exe",
            [
                Path(shutil.which("ffmpeg") or ""),
                conda_bin / "ffmpeg.exe",
            ],
        ),
        (
            "ffprobe.exe",
            [
                Path(shutil.which("ffprobe") or ""),
                conda_bin / "ffprobe.exe",
            ],
        ),
    ]

    for dest_name, candidates in tools:
        src = _pick_first_existing(candidates)
        if not src:
            continue

        dest = internal_dir / dest_name
        try:
            shutil.copy2(src, dest)
            print(f"\n[fix] Bundled {dest_name}: {src}")
        except Exception as e:
            print(f"\n[warn] Failed to bundle {dest_name} from {src}: {e}")


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
    maybe_bundle_windows_executables(RESOURCES_DIR)

    print("\n✅ Backend packaged successfully!")
    print(f"   Output: {RESOURCES_DIR}")
    print("\n   Run the backend exe to test:")
    print(f"   {RESOURCES_DIR / 'backend.exe'}")


if __name__ == "__main__":
    main()
