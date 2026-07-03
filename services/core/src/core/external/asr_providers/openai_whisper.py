from __future__ import annotations

import base64
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Callable

import httpx

from core.external.asr_faster_whisper import AsrResult
from core.external.asr_providers.base import AsrCloudError, AsrCloudTimingsMs, classify_http_error
from core.external.asr_providers.normalize import segments_from_openai_verbose

OPENAI_TRANSCRIPTIONS_URL = "https://api.openai.com/v1/audio/transcriptions"
OPENAI_MAX_BYTES = 24 * 1024 * 1024  # 24MB safety margin under 25MB limit


def _file_size(path: Path) -> int:
	try:
		return path.stat().st_size
	except OSError:
		return 0


def _compress_to_mp3(*, ffmpeg: str, input_path: Path, output_path: Path) -> None:
	cmd = [
		ffmpeg,
		"-hide_banner",
		"-nostdin",
		"-y",
		"-i",
		str(input_path),
		"-vn",
		"-ac",
		"1",
		"-ar",
		"16000",
		"-b:a",
		"64k",
		"-f",
		"mp3",
		str(output_path),
	]
	proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
	if proc.returncode != 0:
		raise AsrCloudError("content_error", "failed to compress audio for OpenAI", fallback_eligible=True)
	if not output_path.is_file() or output_path.stat().st_size == 0:
		raise AsrCloudError("content_error", "OpenAI mp3 compression produced empty file", fallback_eligible=True)


def _resolve_upload_path(audio_path: Path) -> tuple[Path, tempfile.TemporaryDirectory[str] | None]:
	size = _file_size(audio_path)
	if size <= OPENAI_MAX_BYTES:
		return audio_path, None

	import shutil

	ffmpeg = shutil.which("ffmpeg")
	if not ffmpeg:
		raise AsrCloudError("openai_file_too_large", "audio exceeds OpenAI limit and ffmpeg missing", fallback_eligible=True)

	tmp = tempfile.TemporaryDirectory(prefix="openai-asr-")
	mp3_path = Path(tmp.name) / f"{audio_path.stem}.mp3"
	_compress_to_mp3(ffmpeg=ffmpeg, input_path=audio_path, output_path=mp3_path)
	if _file_size(mp3_path) > OPENAI_MAX_BYTES:
		tmp.cleanup()
		raise AsrCloudError("openai_file_too_large", "audio still exceeds OpenAI 25MB after compression", fallback_eligible=True)
	return mp3_path, tmp


def transcribe_openai_whisper(
	*,
	audio_path: Path,
	api_key: str,
	model: str,
	language: str | None,
	audio_duration_s: float | None,
	progress_cb: Callable[[str], None] | None = None,
) -> tuple[AsrResult, AsrCloudTimingsMs]:
	if not audio_path.is_file():
		raise AsrCloudError("content_error", "audio file not readable", fallback_eligible=False)

	upload_path, tmp_ctx = _resolve_upload_path(audio_path)
	timings = AsrCloudTimingsMs()
	total_start = time.perf_counter()
	timeout_s = max(120.0, float(audio_duration_s or 60.0) * 1.5)

	if progress_cb:
		progress_cb(f"asr=cloud provider=openai model={model}")

	try:
		data: dict[str, str] = {
			"model": model,
			"response_format": "verbose_json",
			"timestamp_granularities[]": "segment",
		}
		if language:
			data["language"] = language

		t0 = time.perf_counter()
		with httpx.Client(timeout=timeout_s, trust_env=False) as client:
			with upload_path.open("rb") as fh:
				files = {"file": (upload_path.name, fh, "application/octet-stream")}
				resp = client.post(
					OPENAI_TRANSCRIPTIONS_URL,
					headers={"Authorization": f"Bearer {api_key}"},
					data=data,
					files=files,
				)
		if resp.status_code != 200:
			raise classify_http_error(resp.status_code, resp.text)
		body = resp.json()
		timings.wait_ms = (time.perf_counter() - t0) * 1000.0
		timings.total_ms = (time.perf_counter() - total_start) * 1000.0

		segments, detected_language = segments_from_openai_verbose(body)
		if not segments:
			raise AsrCloudError("empty_transcript", "OpenAI produced empty transcript", fallback_eligible=False)
		provider_label = f"openai/{model}"
		return AsrResult(provider=provider_label, language=detected_language or language, segments=segments), timings
	finally:
		if tmp_ctx is not None:
			tmp_ctx.cleanup()
