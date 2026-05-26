#!/usr/bin/env python3
"""
Make the outer black background of an icon PNG transparent via corner flood-fill.

Only pixels connected to the image corners that match the black threshold are
cleared (alpha set to 0). RGB values are never modified. Interior icon colors
are untouched as long as they are not connected to the corner background.

Usage:
  uv run python scripts/desktop/remove_black_background.py
  uv run python scripts/desktop/remove_black_background.py --dry-run
  uv run python scripts/desktop/remove_black_background.py --sync-icons
"""

from __future__ import annotations

import argparse
import shutil
import sys
from collections import deque
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("Pillow is required. Install with: pip install pillow", file=sys.stderr)
    raise SystemExit(1)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = (
    REPO_ROOT / "apps" / "desktop" / "resources" / "Gemini_Generated_Image_xzrr89xzrr89xzrr.png"
)
DESKTOP_RESOURCES = REPO_ROOT / "apps" / "desktop" / "resources"
ICON_OUTPUTS = (
    DESKTOP_RESOURCES / "icon.png",
    DESKTOP_RESOURCES / "icons" / "1024x1024.png",
)

ICO_SIZES = (256, 128, 64, 48, 32, 16)
ICON_PNG_SIZE = 1024


def is_background_black(r: int, g: int, b: int, a: int, threshold: int) -> bool:
    return a > 0 and max(r, g, b) <= threshold


def flood_clear_black_background(
    rgba: Image.Image,
    threshold: int,
) -> tuple[Image.Image, int]:
    """Return image copy with corner-connected black pixels made transparent."""
    rgba = rgba.convert("RGBA")
    w, h = rgba.size
    px = rgba.load()
    visited = bytearray(w * h)
    changed = 0
    seeds = (0, w - 1, (h - 1) * w, (h - 1) * w + (w - 1))

    for start in seeds:
        sx, sy = start % w, start // w
        if visited[start]:
            continue
        sr, sg, sb, sa = px[sx, sy]
        if not is_background_black(sr, sg, sb, sa, threshold):
            continue

        q: deque[int] = deque([start])
        visited[start] = 1

        while q:
            idx = q.popleft()
            x, y = idx % w, idx // w
            r, g, b, a = px[x, y]
            if is_background_black(r, g, b, a, threshold):
                if a != 0:
                    px[x, y] = (r, g, b, 0)
                    changed += 1

            if x > 0:
                n = idx - 1
                if not visited[n]:
                    visited[n] = 1
                    nr, ng, nb, na = px[x - 1, y]
                    if na > 0 and is_background_black(nr, ng, nb, na, threshold):
                        q.append(n)
            if x + 1 < w:
                n = idx + 1
                if not visited[n]:
                    visited[n] = 1
                    nr, ng, nb, na = px[x + 1, y]
                    if na > 0 and is_background_black(nr, ng, nb, na, threshold):
                        q.append(n)
            if y > 0:
                n = idx - w
                if not visited[n]:
                    visited[n] = 1
                    nr, ng, nb, na = px[x, y - 1]
                    if na > 0 and is_background_black(nr, ng, nb, na, threshold):
                        q.append(n)
            if y + 1 < h:
                n = idx + w
                if not visited[n]:
                    visited[n] = 1
                    nr, ng, nb, na = px[x, y + 1]
                    if na > 0 and is_background_black(nr, ng, nb, na, threshold):
                        q.append(n)

    return rgba, changed


def alpha_stats(rgba: Image.Image) -> dict[str, int]:
    alpha = rgba.getchannel("A")
    lo, hi = alpha.getextrema()
    flat = alpha.get_flattened_data()
    return {
        "alpha_min": lo,
        "alpha_max": hi,
        "transparent_pixels": sum(1 for v in flat if v == 0),
        "total_pixels": len(flat),
    }


def save_png(path: Path, rgba: Image.Image) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rgba.save(path, format="PNG", optimize=True)


def save_ico_from_png(png_path: Path, ico_path: Path) -> None:
    base = Image.open(png_path).convert("RGBA")
    frames = [base.resize((s, s), Image.Resampling.LANCZOS) for s in ICO_SIZES]
    ico_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = ico_path.with_suffix(".tmp.ico")
    frames[0].save(
        tmp,
        format="ICO",
        sizes=[(s, s) for s in ICO_SIZES],
        append_images=frames[1:],
    )
    tmp.replace(ico_path)


def process_file(
    input_path: Path,
    output_path: Path,
    *,
    threshold: int,
    dry_run: bool,
    backup: bool,
) -> dict[str, object]:
    if not input_path.exists():
        return {"path": str(input_path), "skipped": True, "reason": "not found"}

    rgba = Image.open(input_path).convert("RGBA")
    before = alpha_stats(rgba)
    fixed, cleared = flood_clear_black_background(rgba, threshold)
    after = alpha_stats(fixed)

    result: dict[str, object] = {
        "path": str(input_path),
        "output": str(output_path),
        "before": before,
        "after": after,
        "pixels_cleared": cleared,
        "threshold": threshold,
    }

    if dry_run:
        return result

    if backup and output_path.exists():
        shutil.copy2(output_path, output_path.with_suffix(output_path.suffix + ".bak"))

    save_png(output_path, fixed)
    return result


def sync_desktop_icons(fixed: Image.Image, *, backup: bool, dry_run: bool) -> None:
    """Resize to 1024² and write icon.png + icons/1024x1024.png + icon.ico."""
    if dry_run:
        print("[dry-run] would sync desktop icon outputs at 1024x1024")
        return

    resized = fixed.resize((ICON_PNG_SIZE, ICON_PNG_SIZE), Image.Resampling.LANCZOS)

    for out in ICON_OUTPUTS:
        if backup and out.exists():
            shutil.copy2(out, out.with_suffix(out.suffix + ".bak"))
        save_png(out, resized)
        print(f"[OK] wrote {out}")

    ico = DESKTOP_RESOURCES / "icons" / "icon.ico"
    if backup and ico.exists():
        shutil.copy2(ico, ico.with_suffix(".ico.bak"))
    save_ico_from_png(ICON_OUTPUTS[1], ico)
    print(f"[OK] wrote {ico}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Remove corner-connected black background; keep interior colors unchanged.",
    )
    parser.add_argument(
        "--input",
        "-i",
        type=Path,
        default=DEFAULT_INPUT,
        help=f"Source PNG (default: {DEFAULT_INPUT.name})",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        help="Output PNG. Default: <input-stem>_transparent.png beside input.",
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=30,
        help="Max RGB value treated as black background (default: 30).",
    )
    parser.add_argument("--dry-run", action="store_true", help="Analyze only.")
    parser.add_argument("--no-backup", action="store_true", help="Skip .bak files.")
    parser.add_argument(
        "--sync-icons",
        action="store_true",
        help="Also write apps/desktop/resources/icon.png, icons/1024x1024.png, icons/icon.ico.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = args.input.resolve()
    output_path = (
        args.output.resolve()
        if args.output
        else input_path.with_name(f"{input_path.stem}_transparent.png")
    )

    result = process_file(
        input_path,
        output_path,
        threshold=args.threshold,
        dry_run=args.dry_run,
        backup=not args.no_backup,
    )

    if result.get("skipped"):
        print(f"[SKIP] {input_path}: {result.get('reason')}", file=sys.stderr)
        return 1

    before = result["before"]
    after = result["after"]
    print(f"[OK] {input_path}")
    print(f"     output: {output_path}")
    print(f"     threshold={result['threshold']} cleared={result['pixels_cleared']} px")
    print(
        f"     alpha {before['alpha_min']}..{before['alpha_max']} "
        f"(transparent {before['transparent_pixels']}) -> "
        f"{after['alpha_min']}..{after['alpha_max']} "
        f"(transparent {after['transparent_pixels']})"
    )

    if args.sync_icons:
        fixed = Image.open(input_path).convert("RGBA")
        fixed, _ = flood_clear_black_background(fixed, args.threshold)
        sync_desktop_icons(fixed, backup=not args.no_backup, dry_run=args.dry_run)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
