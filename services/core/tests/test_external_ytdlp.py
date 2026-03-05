from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from core.external.ytdlp import YtDlpError, build_ytdlp_command, download_with_ytdlp


def test_build_ytdlp_command_contains_expected_flags(tmp_path: Path):
	cmd = build_ytdlp_command(url="https://example.com/v", output_template=tmp_path / "out.%(ext)s")
	assert cmd[0] == "yt-dlp"
	assert "--ignore-config" in cmd
	assert "--no-playlist" in cmd
	assert "--no-progress" in cmd
	assert "--format" in cmd
	assert "bestvideo+bestaudio/best" in cmd
	assert "--paths" in cmd
	assert "-o" in cmd
	assert "https://example.com/v" in cmd


def test_download_with_ytdlp_raises_when_missing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
	monkeypatch.setenv("DATA_DIR", str(tmp_path))
	monkeypatch.setattr("core.external.ytdlp.shutil.which", lambda _: None)
	monkeypatch.setattr("core.external.ytdlp.importlib.util.find_spec", lambda _name: None)
	with pytest.raises(YtDlpError) as e:
		download_with_ytdlp(url="https://example.com/v", output_dir=tmp_path / "p1" / "downloads")
	assert e.value.kind == "dependency_missing"


def test_download_with_ytdlp_falls_back_to_glob(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
	monkeypatch.setenv("DATA_DIR", str(tmp_path))
	monkeypatch.setattr("core.external.ytdlp.shutil.which", lambda _: "yt-dlp")

	out_dir = tmp_path / "p1" / "downloads"
	out_dir.mkdir(parents=True, exist_ok=True)
	expected = out_dir / "source.webm"
	expected.write_bytes(b"x")

	def fake_run(*_args, **_kwargs):
		return SimpleNamespace(returncode=0, stdout="")

	monkeypatch.setattr("core.external.ytdlp.subprocess.run", fake_run)

	res = download_with_ytdlp(url="https://example.com/v", output_dir=out_dir)
	assert res.abs_path == expected.resolve()
	assert res.rel_path == expected.relative_to(tmp_path).as_posix()


def test_download_with_ytdlp_uses_exe_in_frozen_build(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
	"""PyInstaller sets sys.executable to the packaged binary; it is not a Python interpreter.

	Regression test: frozen builds must not try to run `sys.executable -m yt_dlp`.
	"""
	monkeypatch.setenv("DATA_DIR", str(tmp_path))
	monkeypatch.setattr("core.external.ytdlp.sys", SimpleNamespace(frozen=True, executable="backend.exe"))
	monkeypatch.setattr("core.external.ytdlp.shutil.which", lambda _: "yt-dlp")
	monkeypatch.setattr("core.external.ytdlp.importlib.util.find_spec", lambda _name: object())

	out_dir = tmp_path / "p1" / "downloads"
	out_dir.mkdir(parents=True, exist_ok=True)
	expected = out_dir / "source.webm"
	expected.write_bytes(b"x")

	seen = {}

	def fake_run(cmd, *args, **kwargs):
		seen["cmd"] = cmd
		return SimpleNamespace(returncode=0, stdout="")

	monkeypatch.setattr("core.external.ytdlp.subprocess.run", fake_run)

	res = download_with_ytdlp(url="https://example.com/v", output_dir=out_dir)
	assert res.abs_path == expected.resolve()
	assert seen["cmd"][0] == "yt-dlp"


def test_download_with_ytdlp_appends_extractor_args(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
	monkeypatch.setenv("DATA_DIR", str(tmp_path))
	monkeypatch.setenv("YTDLP_EXTRACTOR_ARGS", "youtube:player_client=android")
	monkeypatch.setattr("core.external.ytdlp.shutil.which", lambda _: "yt-dlp")

	out_dir = tmp_path / "p1" / "downloads"
	out_dir.mkdir(parents=True, exist_ok=True)
	(out_dir / "source.webm").write_bytes(b"x")

	seen = {}

	def fake_run(cmd, *args, **kwargs):
		seen["cmd"] = cmd
		return SimpleNamespace(returncode=0, stdout="")

	monkeypatch.setattr("core.external.ytdlp.subprocess.run", fake_run)

	download_with_ytdlp(url="https://www.youtube.com/watch?v=abc", output_dir=out_dir)
	cmd = seen["cmd"]
	assert "--extractor-args" in cmd
	idx = cmd.index("--extractor-args")
	assert cmd[idx + 1] == "youtube:player_client=android"
