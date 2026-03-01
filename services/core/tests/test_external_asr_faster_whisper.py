from __future__ import annotations

from pathlib import Path

import pytest

from core.external.asr_faster_whisper import AsrError, AsrResult, AsrSegment, transcribe_with_faster_whisper


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
