from __future__ import annotations

import argparse
import os
import sys
import time
import uuid
from pathlib import Path


def _default_seed_data_dir() -> Path:
    # Use a dedicated seed directory to avoid schema drift in an existing core.sqlite3.
    return _repo_root() / "data" / "seed-phase3"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _ensure_core_on_path() -> None:
    # Add services/core/src so `import core` works from repo root.
    src_dir = _repo_root() / "services" / "core" / "src"
    sys.path.insert(0, str(src_dir))


def _now_ms() -> int:
    return int(time.time() * 1000)


def _write_project_files(*, data_dir: Path, project_id: str, job_id: str) -> None:
    # Create a small placeholder tree so Phase 3 delete can remove it.
    project_root = data_dir / project_id
    (project_root / "uploads" / job_id).mkdir(parents=True, exist_ok=True)
    (project_root / "README.txt").write_text(
        f"Seeded project {project_id}\n", encoding="utf-8"
    )
    (project_root / "uploads" / job_id / "upload.bin").write_bytes(b"seed")


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed Phase 3 (projects) data into SQLite.")
    parser.add_argument(
        "--data-dir",
        type=str,
        default=os.environ.get("DATA_DIR") or str(_default_seed_data_dir()),
        help="DATA_DIR used by backend (contains core.sqlite3). Default: repo-root/data/seed-phase3",
    )
    parser.add_argument("--count", type=int, default=12, help="Number of projects to create")
    parser.add_argument(
        "--wipe",
        action="store_true",
        help="Delete all rows from projects/jobs before seeding (DANGEROUS)",
    )
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="Delete existing core.sqlite3 in target data dir before seeding (recreates schema)",
    )
    parser.add_argument(
        "--no-files",
        action="store_true",
        help="Do not create DATA_DIR/<projectId> file trees (delete-project tests need files)",
    )
    args = parser.parse_args()

    data_dir = Path(args.data_dir).resolve()
    data_dir.mkdir(parents=True, exist_ok=True)

    os.environ["DATA_DIR"] = str(data_dir)

    _ensure_core_on_path()

    from sqlalchemy import delete  # noqa: WPS433

    from core.db.models.job import Job  # noqa: WPS433
    from core.db.models.project import Project  # noqa: WPS433
    from core.db.session import init_db, get_sessionmaker, reset_db_for_tests  # noqa: WPS433

    reset_db_for_tests()

    db_path = data_dir / "core.sqlite3"
    if args.fresh:
        for p in (db_path, db_path.with_suffix(db_path.suffix + "-wal"), db_path.with_suffix(db_path.suffix + "-shm")):
            try:
                if p.exists():
                    p.unlink()
            except OSError:
                pass

    init_db()

    # Schema sanity check: if user points at an old DB, create_all won't add missing columns.
    # We fail fast with a clear hint.
    try:
        import sqlite3

        with sqlite3.connect(db_path.as_posix()) as conn:
            cols = {row[1] for row in conn.execute("PRAGMA table_info(jobs)").fetchall()}
        required = {"created_at_ms", "updated_at_ms"}
        if not required.issubset(cols):
            missing = ", ".join(sorted(required - cols))
            raise RuntimeError(
                "Detected an older schema in jobs table (missing: "
                + missing
                + "). Use --fresh or choose a new --data-dir to recreate core.sqlite3."
            )
    except Exception as e:
        print(f"ERROR: {e}")
        print(f"Hint: rerun with: python scripts/seed_phase3_sqlite.py --fresh --data-dir {data_dir}")
        return 2

    SessionLocal = get_sessionmaker()

    now_ms = _now_ms()

    with SessionLocal() as session:
        if args.wipe:
            session.execute(delete(Job))
            session.execute(delete(Project))
            session.commit()

        created_projects = 0
        skipped_projects = 0

        # Build deterministic-ish IDs to make pagination testing easier.
        # List is ordered by (updated_at_ms desc, project_id desc).
        # We'll intentionally create a few projects with the same updated_at_ms.
        for i in range(args.count):
            # Every 3 projects share same updated_at_ms to exercise cursor tiebreak.
            updated_at_ms = now_ms - (i // 3) * 60_000
            created_at_ms = updated_at_ms - 10_000

            project_id = f"proj-{i:04d}"

            existing = session.get(Project, project_id)
            if existing is not None:
                skipped_projects += 1
                continue

            source_type = "youtube" if i % 2 == 0 else "upload"
            source_url = (
                f"https://example.com/watch?v={i:04d}" if source_type == "youtube" else None
            )
            source_path = (
                f"{project_id}/uploads/seed/upload.bin" if source_type == "upload" else None
            )

            latest_result_id = str(uuid.uuid4()) if i % 4 == 0 else None

            project = Project(
                project_id=project_id,
                title=f"Phase3 Seed Project {i:02d}",
                source_type=source_type,
                source_url=source_url,
                source_path=source_path,
                duration_ms=120_000 + i * 1_000,
                format="mp4" if source_type == "upload" else None,
                latest_result_id=latest_result_id,
                created_at_ms=created_at_ms,
                updated_at_ms=updated_at_ms,
            )

            # Create one job per project so delete-project also clears jobs.
            job_id = str(uuid.uuid4())
            job = Job(
                job_id=job_id,
                project_id=project_id,
                type="analyze_video",
                status=("queued" if i % 3 == 0 else "running" if i % 3 == 1 else "failed"),
                stage=("ingest" if i % 2 == 0 else "transcribe"),
                progress=(None if i % 3 == 0 else 0.25 if i % 3 == 1 else 0.9),
                error=(
                    None
                    if i % 3 != 2
                    else {
                        "code": "SEED_FAILED",
                        "message": "Seeded failure for UI testing",
                    }
                ),
                created_at_ms=created_at_ms,
                updated_at_ms=updated_at_ms,
            )

            session.add(project)
            session.add(job)
            session.commit()

            created_projects += 1

            if not args.no_files:
                _write_project_files(data_dir=data_dir, project_id=project_id, job_id=job_id)

    print(f"Seed complete. data_dir={data_dir}")
    print(f"SQLite: {db_path} (exists={db_path.exists()})")
    print(f"Created projects: {created_projects}, skipped(existing): {skipped_projects}")
    print("Use this DATA_DIR when starting backend to test Phase 3 endpoints.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
