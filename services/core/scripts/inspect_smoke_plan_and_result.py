"""Inspect smoke artifacts for a given project/job.

Prints:
- latest Result row for a project (content_blocks/mindmap/note_json sizes)
- parsed content_blocks summary
- keyframes output directory file counts

This is a dev-only helper script.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any


def _loads_json_maybe(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    if not isinstance(value, str):
        return value
    s = value.strip()
    if s == "":
        return None
    try:
        return json.loads(s)
    except Exception:
        return value


def _summarize_content_blocks(blocks: Any) -> dict:
    if not isinstance(blocks, list):
        return {"type": type(blocks).__name__, "blocks": None}

    keyframe_count = 0
    highlight_count = 0

    for b in blocks:
        if not isinstance(b, dict):
            continue
        highlights = b.get("highlights")
        if isinstance(highlights, list):
            highlight_count += len(highlights)
            for h in highlights:
                if isinstance(h, dict) and isinstance(h.get("keyframe"), dict):
                    keyframe_count += 1

    return {
        "type": "list",
        "blocks": len(blocks),
        "highlights": highlight_count,
        "highlights_with_keyframe": keyframe_count,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, default=Path(r"D:\vh-smoke-data"))
    ap.add_argument("--project-id", required=True)
    ap.add_argument("--job-id", required=True)
    args = ap.parse_args()

    db_path = args.data_dir / "core.sqlite3"
    if not db_path.exists():
        raise SystemExit(f"DB not found: {db_path}")

    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row

    try:
        cur = con.cursor()
        cur.execute(
            "SELECT * FROM results WHERE project_id=? ORDER BY created_at_ms DESC LIMIT 1",
            (args.project_id,),
        )
        row = cur.fetchone()
        if row is None:
            print("No results row for project")
        else:
            d = dict(row)
            raw_content_blocks = d.get("content_blocks")
            raw_mindmap = d.get("mindmap")
            raw_note = d.get("note_json")
            raw_asset_refs = d.get("asset_refs")

            parsed_content_blocks = _loads_json_maybe(raw_content_blocks)
            parsed_mindmap = _loads_json_maybe(raw_mindmap)
            parsed_note = _loads_json_maybe(raw_note)
            parsed_asset_refs = _loads_json_maybe(raw_asset_refs)

            print("== Latest Result ==")
            print("result_id:", d.get("result_id"))
            print("schema_version:", d.get("schema_version"))
            print("pipeline_version:", d.get("pipeline_version"))
            print("created_at_ms:", d.get("created_at_ms"))

            def _len(v: Any) -> Any:
                if v is None:
                    return None
                if isinstance(v, str):
                    return len(v)
                if isinstance(v, (list, dict)):
                    return len(v)
                return None

            print("content_blocks raw type:", type(raw_content_blocks).__name__, "len:", _len(raw_content_blocks))
            print("mindmap raw type:", type(raw_mindmap).__name__, "len:", _len(raw_mindmap))
            print("note_json raw type:", type(raw_note).__name__, "len:", _len(raw_note))
            print("asset_refs raw type:", type(raw_asset_refs).__name__, "len:", _len(raw_asset_refs))

            print("content_blocks parsed summary:", json.dumps(_summarize_content_blocks(parsed_content_blocks), ensure_ascii=False))
            print("mindmap parsed type:", type(parsed_mindmap).__name__)
            print("note_json parsed type:", type(parsed_note).__name__)
            print("asset_refs parsed type:", type(parsed_asset_refs).__name__)

    finally:
        con.close()

    # Keyframes directory inspection
    base = args.data_dir / args.project_id / "assets" / "keyframes" / args.job_id
    plan_dir = base / "plan"

    def _count_files(p: Path) -> int | None:
        if not p.exists():
            return None
        return sum(1 for x in p.rglob("*") if x.is_file())

    print("== Keyframes Files ==")
    print("base:", str(base))
    print("base files:", _count_files(base))
    print("plan dir:", str(plan_dir))
    print("plan files:", _count_files(plan_dir))


if __name__ == "__main__":
    main()
