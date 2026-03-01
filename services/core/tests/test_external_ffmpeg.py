from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from core.external.ffmpeg import FfmpegError, build_ffmpeg_extract_audio_command, extract_audio_wav_16k_mono


def test_build_ffmpeg_extract_audio_command_contains_expected_flags(tmp_path: Path):
	inp = tmp_path / "in.mp4"
	out = tmp_path / "out.wav"
	cmd = build_ffmpeg_extract_audio_command(input_path=inp, output_path=out)
	assert cmd[0] == "ffmpeg"
	assert "-i" in cmd
	assert str(inp) in cmd
	assert "-ac" in cmd and "1" in cmd
	assert "-ar" in cmd and "16000" in cmd
	assert "pcm_s16le" in cmd
	assert str(out) in cmd


def test_extract_audio_raises_when_ffmpeg_missing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
	monkeypatch.setenv("DATA_DIR", str(tmp_path))
	monkeypatch.setattr("core.external.ffmpeg.shutil.which", lambda _: None)

	inp = tmp_path / "in.mp4"
	inp.write_bytes(b"x")
	with pytest.raises(FfmpegError) as e:
		extract_audio_wav_16k_mono(input_path=inp, output_dir=tmp_path / "p1" / "audio")
	assert e.value.kind == "dependency_missing"


def test_extract_audio_success(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
	monkeypatch.setenv("DATA_DIR", str(tmp_path))
	monkeypatch.setattr("core.external.ffmpeg.shutil.which", lambda _: "ffmpeg")

	inp = tmp_path / "in.mp4"
	inp.write_bytes(b"x")
	out_dir = tmp_path / "p1" / "artifacts"

	def fake_run(args, **kwargs):
		# create output file
		out_path = Path(args[-1])
		out_path.parent.mkdir(parents=True, exist_ok=True)
		out_path.write_bytes(b"RIFF....WAVE")
		return SimpleNamespace(returncode=0, stdout="")

	monkeypatch.setattr("core.external.ffmpeg.subprocess.run", fake_run)

	res = extract_audio_wav_16k_mono(input_path=inp, output_dir=out_dir, base_filename="a")
	assert res.abs_path.exists()
	assert res.rel_path == res.abs_path.relative_to(tmp_path).as_posix()


def test_extract_audio_classifies_no_audio(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
	monkeypatch.setenv("DATA_DIR", str(tmp_path))
	monkeypatch.setattr("core.external.ffmpeg.shutil.which", lambda _: "ffmpeg")

	inp = tmp_path / "in.mp4"
	inp.write_bytes(b"x")
	out_dir = tmp_path / "p1" / "artifacts"

	def fake_run(*_args, **_kwargs):
		return SimpleNamespace(returncode=1, stdout="Output file #0 does not contain any stream")

	monkeypatch.setattr("core.external.ffmpeg.subprocess.run", fake_run)

	with pytest.raises(FfmpegError) as e:
		extract_audio_wav_16k_mono(input_path=inp, output_dir=out_dir)
	assert e.value.kind == "no_audio"
