from __future__ import annotations

from pathlib import Path

import pytest

from core.db.models.asset import Asset
from core.db.models.project import Project
from core.db.session import get_sessionmaker, init_db, reset_db_for_tests


def test_extract_keyframes_at_times_dedup_and_persist(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    reset_db_for_tests()
    init_db()

    # Create a fake source media file under DATA_DIR.
    proj_dir = tmp_path / "p1"
    proj_dir.mkdir(parents=True, exist_ok=True)
    source_abs = proj_dir / "source.mp4"
    source_abs.write_bytes(b"x")

    # Fake ffmpeg extraction: just write output file.
    def fake_extract_video_frame_jpeg(*, input_path: Path, output_path: Path, time_s: float, timeout_s: float = 0) -> tuple[Path, str]:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"jpg")
        rel = output_path.relative_to(tmp_path).as_posix()
        return output_path, rel

    monkeypatch.setattr("core.app.pipeline.keyframes.extract_video_frame_jpeg", fake_extract_video_frame_jpeg)

    SessionLocal = get_sessionmaker()
    with SessionLocal() as session:
        p = Project(
            project_id="p1",
            title=None,
            source_type="upload",
            source_url=None,
            source_path="p1/source.mp4",
            duration_ms=120000,
            format=None,
            latest_result_id=None,
            created_at_ms=1,
            updated_at_ms=1,
        )
        session.add(p)
        session.commit()

        from core.app.pipeline.keyframes import extract_keyframes_at_times

        artifacts = extract_keyframes_at_times(
            session=session,
            project=p,
            job_id="j1",
            times_ms=[2000, 1000, 2000],
            allow_skip_if_placeholder=False,
            transcript_meta=None,
        )

        assert sorted(list(artifacts.keyframes_by_time.keys())) == [1000, 2000]
        assert len(artifacts.asset_refs) == 2

        assets = session.query(Asset).filter(Asset.project_id == "p1").all()
        assert len(assets) == 2
        assert sorted([a.time_ms for a in assets if a.time_ms is not None]) == [1000, 2000]
