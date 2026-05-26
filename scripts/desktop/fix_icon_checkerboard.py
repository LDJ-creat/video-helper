#!/usr/bin/env python3
"""
Remove baked-in transparency checkerboard from icon PNG/ICO files.

Design tools sometimes export the gray/white checkerboard preview as opaque pixels
instead of a real alpha channel. This script detects those neutral gray tones
(from image corners) and sets them fully transparent.

Usage:
  uv run python scripts/desktop/fix_icon_checkerboard.py
  uv run python scripts/desktop/fix_icon_checkerboard.py --dry-run
  uv run python scripts/desktop/fix_icon_checkerboard.py --input path/to.png --output path/to.png
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
DEFAULT_DESKTOP_RESOURCES = REPO_ROOT / "apps" / "desktop" / "resources"

DEFAULT_TARGETS = (
    DEFAULT_DESKTOP_RESOURCES / "icon.png",
    DEFAULT_DESKTOP_RESOURCES / "icons" / "1024x1024.png",
    DEFAULT_DESKTOP_RESOURCES / "icons" / "icon.ico",
)

ICO_SIZES = (256, 128, 64, 48, 32, 16)


def is_neutral_rgb(r: int, g: int, b: int, chroma_max: int) -> bool:
    return max(r, g, b) - min(r, g, b) <= chroma_max


def rgb_distance(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2) ** 0.5


def sample_corner_pixels(
    rgba: Image.Image,
    corner_size: int,
) -> list[tuple[int, int, int]]:
    w, h = rgba.size
    corner_size = min(corner_size, w // 4, h // 4)
    if corner_size < 4:
        return []

    boxes = (
        (0, 0, corner_size, corner_size),
        (w - corner_size, 0, w, corner_size),
        (0, h - corner_size, corner_size, h),
        (w - corner_size, h - corner_size, w, h),
    )

    samples: list[tuple[int, int, int]] = []
    px = rgba.load()
    for x0, y0, x1, y1 in boxes:
        for y in range(y0, y1):
            for x in range(x0, x1):
                r, g, b, a = px[x, y]
                if a == 0:
                    continue
                if is_neutral_rgb(r, g, b, chroma_max=18):
                    samples.append((r, g, b))
    return samples


def cluster_two_grays(
    samples: list[tuple[int, int, int]],
) -> tuple[tuple[int, int, int], tuple[int, int, int]] | None:
    if len(samples) < 20:
        return None

    # Sort by luminance and split into light / dark groups.
    sorted_samples = sorted(samples, key=lambda c: sum(c) / 3)
    mid = len(sorted_samples) // 2
    dark = sorted_samples[:mid]
    light = sorted_samples[mid:]
    if not dark or not light:
        return None

    def avg(cluster: list[tuple[int, int, int]]) -> tuple[int, int, int]:
        n = len(cluster)
        return (
            round(sum(c[0] for c in cluster) / n),
            round(sum(c[1] for c in cluster) / n),
            round(sum(c[2] for c in cluster) / n),
        )

    c1, c2 = avg(dark), avg(light)
    if rgb_distance(c1, c2) < 12:
        return None
    return c1, c2


def matches_checker_color(
    r: int,
    g: int,
    b: int,
    colors: tuple[tuple[int, int, int], tuple[int, int, int]],
    *,
    chroma_max: int,
    color_distance: float,
) -> bool:
    if not is_neutral_rgb(r, g, b, chroma_max):
        return False
    rgb = (r, g, b)
    return any(rgb_distance(rgb, c) <= color_distance for c in colors)


def flood_transparent_from_corners(
    rgba: Image.Image,
    colors: tuple[tuple[int, int, int], tuple[int, int, int]],
    *,
    chroma_max: int,
    color_distance: float,
) -> int:
    w, h = rgba.size
    px = rgba.load()
    visited = bytearray(w * h)
    changed = 0
    seeds = (0, w - 1, (h - 1) * w, (h - 1) * w + (w - 1))

    def matches_at(x: int, y: int) -> bool:
        r, g, b, a = px[x, y]
        if a == 0:
            return False
        return matches_checker_color(
            r, g, b, colors, chroma_max=chroma_max, color_distance=color_distance
        )

    for start in seeds:
        sx, sy = start % w, start // w
        if visited[start] or not matches_at(sx, sy):
            continue

        q: deque[int] = deque([start])
        visited[start] = 1

        while q:
            idx = q.popleft()
            x, y = idx % w, idx // w
            pr, pg, pb, pa = px[x, y]
            if pa != 0 and matches_checker_color(
                pr, pg, pb, colors, chroma_max=chroma_max, color_distance=color_distance
            ):
                px[x, y] = (pr, pg, pb, 0)
                changed += 1

            if x > 0:
                n = idx - 1
                if not visited[n]:
                    nx, ny = x - 1, y
                    na = px[nx, ny][3]
                    if na == 0:
                        visited[n] = 1
                    elif matches_at(nx, ny):
                        visited[n] = 1
                        q.append(n)
            if x + 1 < w:
                n = idx + 1
                if not visited[n]:
                    nx, ny = x + 1, y
                    na = px[nx, ny][3]
                    if na == 0:
                        visited[n] = 1
                    elif matches_at(nx, ny):
                        visited[n] = 1
                        q.append(n)
            if y > 0:
                n = idx - w
                if not visited[n]:
                    nx, ny = x, y - 1
                    na = px[nx, ny][3]
                    if na == 0:
                        visited[n] = 1
                    elif matches_at(nx, ny):
                        visited[n] = 1
                        q.append(n)
            if y + 1 < h:
                n = idx + w
                if not visited[n]:
                    nx, ny = x, y + 1
                    na = px[nx, ny][3]
                    if na == 0:
                        visited[n] = 1
                    elif matches_at(nx, ny):
                        visited[n] = 1
                        q.append(n)

    return changed


def remove_checkerboard(
    rgba: Image.Image,
    *,
    corner_size: int,
    chroma_max: int,
    color_distance: float,
    aggressive: bool,
) -> tuple[Image.Image, dict[str, object]]:
    rgba = rgba.convert("RGBA")
    samples = sample_corner_pixels(rgba, corner_size)
    colors = cluster_two_grays(samples)

    stats: dict[str, object] = {
        "size": rgba.size,
        "corner_samples": len(samples),
        "checker_colors": colors,
        "pixels_cleared": 0,
        "mode": "none",
    }

    if colors is None:
        return rgba, stats

    if aggressive:
        # Replace every pixel close to detected checker colors (not only flood).
        px = rgba.load()
        w, h = rgba.size
        cleared = 0
        for y in range(h):
            for x in range(w):
                r, g, b, a = px[x, y]
                if a == 0:
                    continue
                if matches_checker_color(
                    r, g, b, colors, chroma_max=chroma_max, color_distance=color_distance
                ):
                    px[x, y] = (r, g, b, 0)
                    cleared += 1
        stats["mode"] = "aggressive"
        stats["pixels_cleared"] = cleared
        return rgba, stats

    cleared = flood_transparent_from_corners(
        rgba,
        colors,
        chroma_max=chroma_max,
        color_distance=color_distance,
    )
    stats["mode"] = "flood"
    stats["pixels_cleared"] = cleared
    return rgba, stats


def alpha_stats(rgba: Image.Image) -> dict[str, object]:
    alpha = rgba.getchannel("A")
    extrema = alpha.getextrema()
    flat = alpha.get_flattened_data()
    transparent = sum(1 for a in flat if a == 0)
    return {
        "alpha_min": extrema[0],
        "alpha_max": extrema[1],
        "transparent_pixels": transparent,
        "total_pixels": len(flat),
    }


def save_png(path: Path, rgba: Image.Image) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rgba.save(path, format="PNG", optimize=True)


def save_ico_from_png(png_path: Path, ico_path: Path) -> None:
    base = Image.open(png_path).convert("RGBA")
    frames = [base.resize((s, s), Image.Resampling.LANCZOS) for s in ICO_SIZES]
    ico_path.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        ico_path,
        format="ICO",
        sizes=[(s, s) for s in ICO_SIZES],
        append_images=frames[1:],
    )


def process_image_path(
    path: Path,
    *,
    output: Path | None,
    dry_run: bool,
    backup: bool,
    corner_size: int,
    chroma_max: int,
    color_distance: float,
    aggressive: bool,
    regenerate_ico: bool,
) -> dict[str, object]:
    if not path.exists():
        return {"path": str(path), "skipped": True, "reason": "not found"}

    out_path = output or path
    result: dict[str, object] = {"path": str(path), "output": str(out_path)}

    if path.suffix.lower() == ".ico":
        im = Image.open(path)
        # Process the largest frame; re-encode full ICO when saving.
        best = im.copy().convert("RGBA")
        try:
            while True:
                im.seek(im.tell() + 1)
                frame = im.copy().convert("RGBA")
                if frame.size[0] > best.size[0]:
                    best = frame
        except EOFError:
            pass
        fixed, fix_stats = remove_checkerboard(
            best,
            corner_size=corner_size,
            chroma_max=chroma_max,
            color_distance=color_distance,
            aggressive=aggressive,
        )
        result["fix"] = fix_stats
        result["before"] = alpha_stats(best)
        result["after"] = alpha_stats(fixed)

        if dry_run:
            return result

        if backup and path.exists():
            shutil.copy2(path, path.with_suffix(path.suffix + ".bak"))

        source_png = path.parent / "1024x1024.png"
        tmp_ico = out_path.with_suffix(".tmp.ico")
        if source_png.exists():
            save_ico_from_png(source_png, tmp_ico)
        else:
            tmp_png = path.parent / "_fix_icon_tmp.png"
            upscaled = fixed if fixed.size[0] >= 1024 else fixed.resize((1024, 1024), Image.Resampling.LANCZOS)
            save_png(tmp_png, upscaled)
            try:
                save_ico_from_png(tmp_png, tmp_ico)
            finally:
                tmp_png.unlink(missing_ok=True)
        tmp_ico.replace(out_path)

        return result

    rgba = Image.open(path).convert("RGBA")
    result["before"] = alpha_stats(rgba)
    fixed, fix_stats = remove_checkerboard(
        rgba,
        corner_size=corner_size,
        chroma_max=chroma_max,
        color_distance=color_distance,
        aggressive=aggressive,
    )
    result["fix"] = fix_stats
    result["after"] = alpha_stats(fixed)

    if dry_run:
        return result

    if backup and path.exists():
        shutil.copy2(path, path.with_suffix(path.suffix + ".bak"))

    save_png(out_path, fixed)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert baked checkerboard gray pixels to real transparency in desktop icons.",
    )
    parser.add_argument(
        "--input",
        "-i",
        action="append",
        type=Path,
        help="Input PNG or ICO (repeatable). Defaults to desktop resource icons.",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        help="Output path (only valid with a single --input).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Analyze only; do not write files.",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Do not create .bak copies before overwriting.",
    )
    parser.add_argument(
        "--corner-size",
        type=int,
        default=72,
        help="Corner sample square size in pixels (default: 72).",
    )
    parser.add_argument(
        "--color-distance",
        type=float,
        default=28.0,
        help="Max RGB distance to detected checker colors (default: 28).",
    )
    parser.add_argument(
        "--chroma-max",
        type=int,
        default=14,
        help="Max RGB spread for a pixel to count as neutral gray (default: 14).",
    )
    parser.add_argument(
        "--aggressive",
        action="store_true",
        help="Clear all matching grays, not only regions connected to corners.",
    )
    parser.add_argument(
        "--regenerate-ico",
        action="store_true",
        help="When processing .ico, rebuild multi-size ICO from the fixed frame.",
    )
    parser.add_argument(
        "--sync-ico",
        action="store_true",
        help="After fixing PNGs, rebuild icons/icon.ico from icons/1024x1024.png.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    inputs = args.input or list(DEFAULT_TARGETS)

    if args.output and len(inputs) != 1:
        print("--output requires exactly one --input", file=sys.stderr)
        return 2

    any_error = False
    for path in inputs:
        path = path.resolve()
        try:
            result = process_image_path(
                path,
                output=args.output.resolve() if args.output else None,
                dry_run=args.dry_run,
                backup=not args.no_backup,
                corner_size=args.corner_size,
                chroma_max=args.chroma_max,
                color_distance=args.color_distance,
                aggressive=args.aggressive,
                regenerate_ico=args.regenerate_ico or path.suffix.lower() == ".ico",
            )
        except Exception as exc:
            any_error = True
            print(f"[ERROR] {path}: {exc}", file=sys.stderr)
            continue

        if result.get("skipped"):
            print(f"[SKIP] {path}: {result.get('reason')}")
            continue

        fix = result.get("fix", {})
        before = result.get("before", {})
        after = result.get("after", {})
        print(f"[OK] {path}")
        print(f"     mode={fix.get('mode')} checker_colors={fix.get('checker_colors')}")
        print(f"     cleared={fix.get('pixels_cleared')} pixels")
        print(
            f"     alpha: {before.get('alpha_min')}..{before.get('alpha_max')} "
            f"transparent={before.get('transparent_pixels')} -> "
            f"{after.get('alpha_min')}..{after.get('alpha_max')} "
            f"transparent={after.get('transparent_pixels')}"
        )

    if args.sync_ico and not args.dry_run:
        png = DEFAULT_DESKTOP_RESOURCES / "icons" / "1024x1024.png"
        ico = DEFAULT_DESKTOP_RESOURCES / "icons" / "icon.ico"
        if png.exists():
            if not args.no_backup and ico.exists():
                shutil.copy2(ico, ico.with_suffix(".ico.bak"))
            save_ico_from_png(png, ico)
            print(f"[OK] rebuilt {ico} from {png}")

    return 1 if any_error else 0


if __name__ == "__main__":
    raise SystemExit(main())
