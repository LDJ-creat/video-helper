from __future__ import annotations

import argparse
import mimetypes
import os
import sys
import time
import uuid
from pathlib import Path


def _now_ms() -> int:
    return int(time.time() * 1000)


def _is_safe_rel_path(rel: str) -> bool:
    rel = (rel or "").strip()
    if not rel:
        return False
    p = Path(rel)
    # Reject absolute paths (including drive-letter paths on Windows).
    if p.is_absolute() or p.drive:
        return False
    if rel.startswith("/") or rel.startswith("\\"):
        return False
    # Reject obvious traversal.
    if ".." in Path(rel).parts:
        return False
    return True


def _normalize_source_path(*, data_dir: Path, source_path: str) -> tuple[str | None, str | None]:
    """Return (normalized_rel_path, skip_reason).

    DB contract: Project.source_path should be relative under DATA_DIR (posix-style).
    This helper tolerates older DBs that may have stored an absolute path.
    """
    raw = (source_path or "").strip()
    if not raw:
        return None, "no_source_path"

    # Normalize slashes early for consistent matching.
    raw_norm = raw.replace("\\", "/")
    p = Path(raw)
    if p.is_absolute() or p.drive:
        try:
            abs_path = p.expanduser().resolve()
            base = data_dir.resolve()
            rel = abs_path.relative_to(base).as_posix()
            if not _is_safe_rel_path(rel):
                return None, "unsafe_rel_from_abs"
            return rel, None
        except Exception:
            return None, "abs_outside_data_dir"

    # Relative path.
    if not _is_safe_rel_path(raw_norm):
        return None, "unsafe_rel"
    # Ensure posix separators in DB.
    return Path(raw_norm).as_posix(), None


def _resolve_under_data_dir(*, data_dir: Path, rel: str) -> Path | None:
    if not _is_safe_rel_path(rel):
        return None
    base = data_dir.resolve()
    abs_path = (base / Path(rel)).resolve()
    try:
        abs_path.relative_to(base)
    except Exception:
        return None
    return abs_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Backfill video Asset rows from projects.source_path and inject kind=video into latest Result.asset_refs.")
    parser.add_argument(
        "--data-dir",
        required=True,
        help="DATA_DIR directory containing core.sqlite3 and project files (absolute path recommended)",
    )
    parser.add_argument("--project-id", default="", help="Only process a single projectId")
    parser.add_argument("--dry-run", action="store_true", help="Do not write DB changes")
    parser.add_argument("--limit", type=int, default=0, help="Max projects to process (0 = no limit)")
    parser.add_argument(
        "--inspect",
        action="store_true",
        help="Print DB/project/asset summary before and after backfill",
    )
    parser.add_argument(
        "--inspect-only",
        action="store_true",
        help="Only print DB summary (requires --inspect); do not perform backfill",
    )
    args = parser.parse_args()

    data_dir = Path(str(args.data_dir)).expanduser().resolve()
    if not data_dir.exists() or not data_dir.is_dir():
        print(f"[err] data-dir not found: {data_dir}")
        return 2

    # Ensure core uses the requested DATA_DIR.
    os.environ["DATA_DIR"] = str(data_dir)

    # Explicitly show which sqlite DB file we will touch.
    db_path = data_dir / "core.sqlite3"
    print(f"[info] DATA_DIR={data_dir} db={db_path} dbExists={db_path.exists()}")

    core_root = Path(__file__).resolve().parents[1]
    src_dir = core_root / "src"
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))

    from core.db.session import get_sessionmaker, init_db, reset_db_engine_for_tests  # noqa: E402
    from core.db.models.asset import Asset  # noqa: E402
    from core.db.models.project import Project  # noqa: E402
    from core.db.models.result import Result  # noqa: E402

    reset_db_engine_for_tests()
    init_db()

    SessionLocal = get_sessionmaker()

    processed = 0
    planned_assets = 0
    created_assets = 0
    planned_results = 0
    updated_results = 0

    skipped_missing_file = 0
    skipped_no_source_path = 0
    skipped_no_latest_result = 0
    skipped_already_has_video_ref = 0
    skipped_abs_outside_data_dir = 0
    skipped_unsafe_source_path = 0

    started_ms = _now_ms()

    def _inspect_db(*, session) -> None:
        try:
            projects_count = session.query(Project).count()
            assets_count = session.query(Asset).count()
            results_count = session.query(Result).count()
            print(f"[inspect] projects={projects_count} assets={assets_count} results={results_count}")
            rows = session.query(Asset.kind).all()
            kinds: dict[str, int] = {}
            for (k,) in rows:
                kinds[str(k)] = kinds.get(str(k), 0) + 1
            print(f"[inspect] assetKinds={kinds}")
        except Exception as e:
            print(f"[inspect][err] {e}")

    with SessionLocal() as session:
        if args.inspect:
            _inspect_db(session=session)
            if args.inspect_only:
                return 0

        q = session.query(Project)
        project_id = (args.project_id or "").strip()
        if project_id:
            q = q.filter(Project.project_id == project_id)
        q = q.order_by(Project.updated_at_ms.desc())

        projects = q.all()
        if args.limit and args.limit > 0:
            projects = projects[: int(args.limit)]

        for project in projects:
            processed += 1
            source_raw = project.source_path
            if not isinstance(source_raw, str) or not source_raw.strip():
                skipped_no_source_path += 1
                continue

            source_rel, skip_reason = _normalize_source_path(data_dir=data_dir, source_path=source_raw)
            if source_rel is None:
                if skip_reason == "abs_outside_data_dir":
                    skipped_abs_outside_data_dir += 1
                elif skip_reason == "no_source_path":
                    skipped_no_source_path += 1
                else:
                    skipped_unsafe_source_path += 1
                continue

            abs_path = _resolve_under_data_dir(data_dir=data_dir, rel=source_rel)
            if abs_path is None or not abs_path.exists() or not abs_path.is_file():
                skipped_missing_file += 1
                continue

            # 1) Ensure Asset(kind=video) exists
            existing = (
                session.query(Asset)
                .filter(Asset.project_id == project.project_id, Asset.kind == "video", Asset.file_path == source_rel)
                .first()
            )
            if existing is not None:
                video_asset_id = existing.asset_id
            else:
                planned_assets += 1
                video_asset_id = str(uuid.uuid4())
                mime, _ = mimetypes.guess_type(abs_path.name)
                if not mime:
                    mime = "video/mp4"

                if not args.dry_run:
                    session.add(
                        Asset(
                            asset_id=video_asset_id,
                            project_id=project.project_id,
                            kind="video",
                            origin="generated",
                            mime_type=mime,
                            width=None,
                            height=None,
                            file_path=source_rel,
                            chapter_id=None,
                            time_ms=None,
                            created_at_ms=_now_ms(),
                        )
                    )
                    session.commit()
                    created_assets += 1

            # 2) Inject kind=video into latest result
            latest_result_id = project.latest_result_id
            if not isinstance(latest_result_id, str) or not latest_result_id.strip():
                skipped_no_latest_result += 1
                continue

            result = session.get(Result, latest_result_id)
            if result is None:
                skipped_no_latest_result += 1
                continue

            refs = result.asset_refs if isinstance(result.asset_refs, list) else []

            # If already has a video ref, keep as-is.
            if any(isinstance(r, dict) and r.get("kind") == "video" for r in refs):
                skipped_already_has_video_ref += 1
                continue

            planned_results += 1
            new_refs = [{"assetId": video_asset_id, "kind": "video"}]
            for r in refs:
                if isinstance(r, dict) and r.get("assetId") and r.get("kind"):
                    new_refs.append({"assetId": r.get("assetId"), "kind": r.get("kind")})

            if not args.dry_run:
                result.asset_refs = new_refs
                session.add(result)
                session.commit()
                updated_results += 1

        if args.inspect:
            _inspect_db(session=session)

    elapsed_ms = _now_ms() - started_ms

    print(
        "[ok] backfill complete "
        f"processed={processed} plannedAssets={planned_assets} createdAssets={created_assets} "
        f"plannedLatestResults={planned_results} updatedLatestResults={updated_results} "
        f"skippedNoSourcePath={skipped_no_source_path} skippedMissingFile={skipped_missing_file} "
        f"skippedNoLatestResult={skipped_no_latest_result} skippedAlreadyHasVideoRef={skipped_already_has_video_ref} "
        f"skippedAbsOutsideDataDir={skipped_abs_outside_data_dir} skippedUnsafeSourcePath={skipped_unsafe_source_path} "
        f"elapsedMs={elapsed_ms} dryRun={bool(args.dry_run)}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
