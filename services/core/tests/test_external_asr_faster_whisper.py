from __future__ import annotations

from pathlib import Path

import os

import pytest

from core.external.asr_faster_whisper import AsrError, AsrResult, AsrSegment, prefetch_faster_whisper_model, transcribe_with_faster_whisper


def test_asr_result_to_transcript_dict_duration_ms():
	res = AsrResult(
		provider="faster-whisper",
		language="en",
		segments=[AsrSegment(start_ms=0, end_ms=1200, text="a"), AsrSegment(start_ms=1200, end_ms=2500, text="b")],
	)
	out = res.to_transcript_dict()
	assert out["durationMs"] == 2500
	assert out["unit"] == "ms"


def test_transcribe_with_faster_whisper_missing_dependency(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
	audio = tmp_path / "a.wav"
	audio.write_bytes(b"x")

	def fake_loader():
		raise AsrError("dependency_missing", "faster-whisper is not installed")

	monkeypatch.setattr("core.external.asr_faster_whisper._load_faster_whisper", fake_loader)
	with pytest.raises(AsrError) as e:
		transcribe_with_faster_whisper(audio_path=audio)
	assert e.value.kind == "dependency_missing"


def test_prefetch_faster_whisper_model_auto_endpoint_fallback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
	# Ensure deterministic behavior in tests.
	monkeypatch.delenv("HF_ENDPOINT", raising=False)

	# Redirect DATA_DIR to a temp path.
	monkeypatch.setattr("core.external.asr_faster_whisper.get_data_dir", lambda: tmp_path)

	endpoints_seen: list[str | None] = []

	def fake_download_model(model_size: str, *, output_dir: str, cache_dir=None, local_files_only: bool = False):
		endpoints_seen.append(os.environ.get("HF_ENDPOINT"))
		# Fail the first attempt (official), succeed on the second (mirror).
		if len(endpoints_seen) == 1:
			raise RuntimeError("ConnectionError: timed out")
		out = Path(output_dir)
		out.mkdir(parents=True, exist_ok=True)
		(out / "config.json").write_text("{}", encoding="utf-8")
		(out / "model.bin").write_bytes(b"x")
		(out / "tokenizer.json").write_text("{}", encoding="utf-8")
		(out / "vocabulary.txt").write_text("x", encoding="utf-8")

	def fake_loader():
		return object(), fake_download_model

	monkeypatch.setattr("core.external.asr_faster_whisper._load_faster_whisper", fake_loader)
	res = prefetch_faster_whisper_model(model_size="base")
	assert res["ok"] is True
	assert endpoints_seen[0] == "https://huggingface.co"
	assert endpoints_seen[1] == "https://hf-mirror.com"


def test_prefetch_faster_whisper_model_error_includes_endpoints_tried(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
	monkeypatch.delenv("HF_ENDPOINT", raising=False)
	monkeypatch.setattr("core.external.asr_faster_whisper.get_data_dir", lambda: tmp_path)

	def fake_download_model(model_size: str, *, output_dir: str, cache_dir=None, local_files_only: bool = False):
		raise RuntimeError("ReadTimeout: timed out")

	def fake_loader():
		return object(), fake_download_model

	monkeypatch.setattr("core.external.asr_faster_whisper._load_faster_whisper", fake_loader)
	with pytest.raises(AsrError) as e:
		prefetch_faster_whisper_model(model_size="base")
	assert e.value.kind == "model_missing"
	assert isinstance(e.value.details, dict)
	assert "endpointsTried" in e.value.details
	assert "https://hf-mirror.com" in (e.value.details.get("endpointsTried") or [])
	assert "hint" in e.value.details
