from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

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


def test_transcribe_with_faster_whisper_model_cached(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
	# Redirect DATA_DIR.
	monkeypatch.setattr("core.external.asr_faster_whisper.get_data_dir", lambda: tmp_path)

	# Pretend the model dir is complete to avoid downloads.
	monkeypatch.setattr("core.external.asr_faster_whisper._looks_like_model_dir", lambda _p: True)

	# Ensure no env overrides affect the cache key.
	monkeypatch.delenv("TRANSCRIBE_CPU_THREADS", raising=False)
	monkeypatch.delenv("TRANSCRIBE_NUM_WORKERS", raising=False)
	monkeypatch.delenv("TRANSCRIBE_DEVICE_INDEX", raising=False)

	# Reset cache between tests.
	from core.external import asr_faster_whisper as mod

	mod._reset_model_cache_for_tests()

	init_calls = {"n": 0}

	class FakeWhisperModel:
		def __init__(
			self,
			model_size_or_path: str,
			device: str = "auto",
			device_index=0,
			compute_type: str = "default",
			cpu_threads: int = 0,
			num_workers: int = 1,
			**_kwargs,
		):
			init_calls["n"] += 1
			self._device = device
			self._compute_type = compute_type

		def transcribe(self, audio, vad_filter: bool = False, language: str | None = None, beam_size: int = 5, best_of: int = 5):
			seg = SimpleNamespace(start=0.0, end=1.0, text="hello")
			info = SimpleNamespace(language=language or "en")
			return iter([seg]), info

	def fake_loader():
		return FakeWhisperModel, (lambda *args, **kwargs: None)

	monkeypatch.setattr("core.external.asr_faster_whisper._load_faster_whisper", fake_loader)

	audio = tmp_path / "a.wav"
	audio.write_bytes(b"x")

	res1 = transcribe_with_faster_whisper(audio_path=audio, model_size="base", device="cpu")
	res2 = transcribe_with_faster_whisper(audio_path=audio, model_size="base", device="cpu")
	assert init_calls["n"] == 1
	assert res1.segments and res2.segments


def test_transcribe_with_faster_whisper_device_auto_selects_cuda_when_available(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
	monkeypatch.setattr("core.external.asr_faster_whisper.get_data_dir", lambda: tmp_path)
	monkeypatch.setattr("core.external.asr_faster_whisper._looks_like_model_dir", lambda _p: True)

	from core.external import asr_faster_whisper as mod

	mod._reset_model_cache_for_tests()

	# Simulate CUDA availability.
	monkeypatch.setattr("core.external.asr_faster_whisper._get_cuda_device_count", lambda: 1)

	seen = {"device": None, "compute_type": None}

	class FakeWhisperModel:
		def __init__(
			self,
			model_size_or_path: str,
			device: str = "auto",
			device_index=0,
			compute_type: str = "default",
			cpu_threads: int = 0,
			num_workers: int = 1,
			**_kwargs,
		):
			seen["device"] = device
			seen["compute_type"] = compute_type

		def transcribe(self, audio, vad_filter: bool = False, language: str | None = None, beam_size: int = 5, best_of: int = 5):
			seg = SimpleNamespace(start=0.0, end=1.0, text="hi")
			info = SimpleNamespace(language="en")
			return iter([seg]), info

	def fake_loader():
		return FakeWhisperModel, (lambda *args, **kwargs: None)

	monkeypatch.setattr("core.external.asr_faster_whisper._load_faster_whisper", fake_loader)

	audio = tmp_path / "a.wav"
	audio.write_bytes(b"x")

	transcribe_with_faster_whisper(audio_path=audio, model_size="base", device="auto", compute_type=None)
	assert seen["device"] == "cuda"
	assert seen["compute_type"] == "float16"


def test_transcribe_with_faster_whisper_device_auto_falls_back_to_cpu_when_cuda_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
	monkeypatch.setattr("core.external.asr_faster_whisper.get_data_dir", lambda: tmp_path)
	monkeypatch.setattr("core.external.asr_faster_whisper._looks_like_model_dir", lambda _p: True)

	from core.external import asr_faster_whisper as mod

	mod._reset_model_cache_for_tests()

	# Simulate CUDA availability.
	monkeypatch.setattr("core.external.asr_faster_whisper._get_cuda_device_count", lambda: 1)

	seen_devices: list[str] = []
	seen_compute_types: list[str] = []
	init_calls = {"n": 0}

	class FakeWhisperModel:
		def __init__(
			self,
			model_size_or_path: str,
			device: str = "auto",
			device_index=0,
			compute_type: str = "default",
			cpu_threads: int = 0,
			num_workers: int = 1,
			**_kwargs,
		):
			init_calls["n"] += 1
			self._device = device
			seen_devices.append(str(device))
			seen_compute_types.append(str(compute_type))

		def transcribe(self, audio, vad_filter: bool = False, language: str | None = None, beam_size: int = 5, best_of: int = 5):
			if self._device == "cuda":
				raise RuntimeError("CUDA error: driver version is insufficient for CUDA runtime version")
			seg = SimpleNamespace(start=0.0, end=1.0, text="ok")
			info = SimpleNamespace(language="en")
			return iter([seg]), info

	def fake_loader():
		return FakeWhisperModel, (lambda *args, **kwargs: None)

	monkeypatch.setattr("core.external.asr_faster_whisper._load_faster_whisper", fake_loader)

	audio = tmp_path / "a.wav"
	audio.write_bytes(b"x")

	res = transcribe_with_faster_whisper(audio_path=audio, model_size="base", device="auto", compute_type=None)
	assert res.segments
	# One init for CUDA attempt + one for CPU fallback.
	assert init_calls["n"] == 2
	assert seen_devices[0] == "cuda"
	assert seen_devices[1] == "cpu"
	assert seen_compute_types[0] == "float16"
	assert seen_compute_types[1] == "int8"
