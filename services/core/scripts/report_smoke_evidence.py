from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

GUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")


@dataclass(frozen=True)
class EvidenceFile:
    path: Path
    size: int
    mtime: float


def _fmt_ts(ts: float) -> str:
    try:
        return datetime.fromtimestamp(ts).isoformat(timespec="seconds")
    except Exception:
        return str(ts)


def scan_job_dir(job_dir: Path) -> list[EvidenceFile]:
    files: list[EvidenceFile] = []
    for p in job_dir.rglob("*"):
        if not p.is_file():
            continue
        try:
            st = p.stat()
        except OSError:
            continue
        files.append(EvidenceFile(path=p, size=st.st_size, mtime=st.st_mtime))
    files.sort(key=lambda e: (e.mtime, e.size), reverse=True)
    return files


def find_latest_job_dir(data_dir: Path) -> Path | None:
    candidates: list[tuple[float, Path]] = []
    for p in data_dir.iterdir():
        if not p.is_dir():
            continue
        if not GUID_RE.match(p.name):
            continue
        try:
            ts = p.stat().st_mtime
        except OSError:
            continue
        candidates.append((ts, p))
    if not candidates:
        return None
    candidates.sort(key=lambda t: t[0], reverse=True)
    return candidates[0][1]


def discover_inner_job_ids(run_dir: Path) -> list[str]:
    """Run directories may contain inner job directories under artifacts/ and downloads/."""
    found: set[str] = set()
    for parent in (run_dir / "artifacts", run_dir / "downloads"):
        if not parent.exists() or not parent.is_dir():
            continue
        for p in parent.iterdir():
            if p.is_dir() and GUID_RE.match(p.name):
                found.add(p.name)
    return sorted(found)


def find_run_dir_for_job_id(data_dir: Path, job_id: str) -> Path | None:
    for run_dir in data_dir.iterdir():
        if not run_dir.is_dir() or not GUID_RE.match(run_dir.name):
            continue
        if (run_dir / "artifacts" / job_id).exists() or (run_dir / "downloads" / job_id).exists():
            return run_dir
    return None


def _guess_key_files(files: Iterable[EvidenceFile]) -> dict[str, EvidenceFile]:
    wanted_names = {
        "audio.wav",
        "transcript.json",
        "chapters.json",
        "segments.json",
        "source.wav",
        "source.m4a",
        "source.mp4",
    }

    found: dict[str, EvidenceFile] = {}
    for ef in files:
        name = ef.path.name
        if name in wanted_names and name not in found:
            found[name] = ef
    return found


def _sqlite_row_to_dict(cur: sqlite3.Cursor, row: sqlite3.Row) -> dict[str, Any]:
    return {k: row[k] for k in row.keys()}


def read_job_refs_from_db(db_path: Path, job_id: str) -> dict[str, Any] | None:
    if not db_path.exists():
        return None

    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    try:
        cur = con.cursor()
        def try_lookup(table: str, col: str) -> dict[str, Any] | None:
            try:
                cur.execute(f"SELECT * FROM {table} WHERE {col} = ?", (job_id,))
                row = cur.fetchone()
                if row is None:
                    return None
                return {"table": table, "matchColumn": col, "row": _sqlite_row_to_dict(cur, row)}
            except sqlite3.Error:
                return None

        # Try common job table names.
        for table in ("jobs", "job", "pipeline_jobs"):
            for col in ("id", "job_id", "jobId"):
                hit = try_lookup(table, col)
                if hit is not None:
                    return hit

        # Fallback: scan sqlite_master for a table that has an `id` column.
        try:
            cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [r[0] for r in cur.fetchall()]
        except sqlite3.Error:
            tables = []

        for table in tables:
            try:
                cur.execute(f"PRAGMA table_info({table})")
                cols = [r[1] for r in cur.fetchall()]
                lookup_cols = [c for c in ("id", "job_id", "jobId") if c in cols]
                for col in lookup_cols:
                    hit = try_lookup(table, col)
                    if hit is not None:
                        return hit
            except sqlite3.Error:
                continue

        return None
    finally:
        con.close()


def _extract_refs(db_payload: dict[str, Any]) -> dict[str, Any]:
    row = db_payload.get("row") or {}
    keys = [
        "id",
        "job_id",
        "status",
        "stage",
        "progress",
        "error",
        "transcript",
        "chapters",
        "audio_ref",
        "transcript_ref",
        "transcript_meta",
        "result_ref",
        "updated_at",
        "created_at",
    ]
    out: dict[str, Any] = {"table": db_payload.get("table")}
    for k in keys:
        if k in row:
            out[k] = row.get(k)

    # Error field variants.
    if "error_code" not in out:
        for k in ("errorCode", "error_code"):
            if k in row:
                out["error_code"] = row.get(k)
                break
    if "error_message" not in out:
        for k in ("errorMessage", "error_message"):
            if k in row:
                out["error_message"] = row.get(k)
                break
    if "error_details" not in out:
        for k in ("errorDetails", "error_details"):
            if k in row:
                out["error_details"] = row.get(k)
                break

    # Try variant column names.
    if "audio_ref" not in out:
        for k in ("audioPath", "audio_path", "audioUri", "audio_uri"):
            if k in row:
                out["audio_ref"] = row.get(k)
                break
    if "transcript_ref" not in out:
        for k in ("transcriptPath", "transcript_path", "transcriptUri", "transcript_uri"):
            if k in row:
                out["transcript_ref"] = row.get(k)
                break
    if "transcript_meta" not in out:
        for k in ("transcriptMeta", "transcript_meta_json"):
            if k in row:
                out["transcript_meta"] = row.get(k)
                break

    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Report smoke-run evidence (files + DB refs) for latest or specified job.")
    ap.add_argument("--data-dir", default=os.environ.get("DATA_DIR") or r"D:\\vh-smoke-data")
    ap.add_argument(
        "--job-id",
        default="",
        help="Job GUID (API job id). If omitted, auto-detect latest run dir under data-dir and infer inner job id.",
    )
    ap.add_argument("--max-files", type=int, default=30)
    ap.add_argument("--out", default="", help="If set, write JSON output to this path (UTF-8)")
    args = ap.parse_args()

    data_dir = Path(args.data_dir).resolve()
    if not data_dir.exists():
        raise SystemExit(f"DATA_DIR does not exist: {data_dir}")

    run_id = ""
    job_id = args.job_id.strip()

    if job_id:
        # Prefer to locate the run dir that contains this job id.
        found_run = find_run_dir_for_job_id(data_dir, job_id)
        if found_run is not None:
            run_dir = found_run.resolve()
            run_id = run_dir.name
        else:
            # Fallback: assume run dir matches the job id.
            run_id = job_id
            run_dir = (data_dir / run_id).resolve()
    else:
        latest = find_latest_job_dir(data_dir)
        if latest is None:
            raise SystemExit(f"No run directories found under DATA_DIR: {data_dir}")
        run_dir = latest.resolve()
        run_id = run_dir.name

    if not run_dir.exists():
        raise SystemExit(f"Run dir not found: {run_dir}")

    inner_job_ids = discover_inner_job_ids(run_dir)
    if not job_id:
        # Prefer an inferred inner job id when present.
        job_id = inner_job_ids[0] if inner_job_ids else run_id

    files = scan_job_dir(run_dir)
    key_files = _guess_key_files(files)

    db_path = data_dir / "core.sqlite3"
    db_payload = read_job_refs_from_db(db_path, job_id)
    refs = _extract_refs(db_payload) if db_payload else None

    output: dict[str, Any] = {
        "dataDir": str(data_dir),
        "runId": run_id,
        "jobId": job_id,
        "runDir": str(run_dir),
        "innerJobIds": inner_job_ids,
        "dbPath": str(db_path),
        "dbFound": db_path.exists(),
        "dbRefs": refs,
        "keyFiles": {
            k: {"path": str(v.path), "size": v.size, "mtime": _fmt_ts(v.mtime)} for k, v in key_files.items()
        },
        "recentFiles": [
            {"path": str(ef.path), "size": ef.size, "mtime": _fmt_ts(ef.mtime)}
            for ef in files[: max(0, args.max_files)]
        ],
    }

    rendered = json.dumps(output, ensure_ascii=False, indent=2)
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(rendered, encoding="utf-8")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
