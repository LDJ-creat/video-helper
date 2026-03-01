from __future__ import annotations

from pathlib import Path

import pytest

from core.app.pipeline.media_source import plan_media_source
from core.db.models.project import Project
from core.db.session import get_data_dir


def _mk_project(**kwargs):
	base = dict(
		project_id="p1",
		title=None,
		source_type="upload",
		source_url=None,
		source_path=None,
		duration_ms=None,
		format=None,
		latest_result_id=None,
		created_at_ms=0,
		updated_at_ms=0,
	)
	base.update(kwargs)
	return Project(**base)


def test_plan_media_source_upload_requires_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
	monkeypatch.setenv("DATA_DIR", str(tmp_path))
	project = _mk_project(source_type="upload", source_path=None)
	with pytest.raises(ValueError):
		plan_media_source(project)


def test_plan_media_source_upload_resolves_abs_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
	monkeypatch.setenv("DATA_DIR", str(tmp_path))
	(rel_dir := tmp_path / "p1" / "uploads" / "j1").mkdir(parents=True, exist_ok=True)
	media = rel_dir / "a.mp4"
	media.write_bytes(b"x")
	rel = media.relative_to(tmp_path).as_posix()
	project = _mk_project(source_type="upload", source_path=rel)
	plan = plan_media_source(project)
	assert plan.kind == "upload"
	assert plan.requires_download is False
	assert plan.media_abs_path == media
	assert plan.media_rel_path == rel


def test_plan_media_source_url_requires_url(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
	monkeypatch.setenv("DATA_DIR", str(tmp_path))
	project = _mk_project(source_type="youtube", source_url=None)
	with pytest.raises(ValueError):
		plan_media_source(project)


def test_plan_media_source_url_needs_download_when_no_source_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
	monkeypatch.setenv("DATA_DIR", str(tmp_path))
	project = _mk_project(source_type="youtube", source_url="https://example.com", source_path=None)
	plan = plan_media_source(project)
	assert plan.kind == "url"
	assert plan.requires_download is True
	assert plan.media_abs_path is None
	assert plan.download_dir_abs == (get_data_dir() / "p1" / "downloads").resolve()


def test_plan_media_source_url_uses_existing_source_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
	monkeypatch.setenv("DATA_DIR", str(tmp_path))
	(tmp_path / "p1" / "downloads").mkdir(parents=True, exist_ok=True)
	media = tmp_path / "p1" / "downloads" / "source.mp4"
	media.write_bytes(b"x")
	rel = media.relative_to(tmp_path).as_posix()
	project = _mk_project(source_type="bilibili", source_url="https://example.com", source_path=rel)
	plan = plan_media_source(project)
	assert plan.kind == "url"
	assert plan.requires_download is False
	assert plan.media_abs_path == media
	assert plan.media_rel_path == rel
