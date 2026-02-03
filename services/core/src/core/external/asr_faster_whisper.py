from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class AsrError(ValueError):
	def __init__(self, kind: str, message: str, *, details: dict | None = None):
		super().__init__(message)
		self.kind = kind
		self.details = details or {}


@dataclass(frozen=True)
class AsrSegment:
	start_ms: int
	end_ms: int
	text: str

	def to_dict(self) -> dict:
		return {"startMs": self.start_ms, "endMs": self.end_ms, "text": self.text}


@dataclass(frozen=True)
class AsrResult:
	provider: str
	language: str | None
	segments: list[AsrSegment]

	def to_transcript_dict(self) -> dict:
		duration_ms = 0
		if self.segments:
			duration_ms = max(0, int(self.segments[-1].end_ms))
		return {
			"version": 1,
			"provider": self.provider,
			"language": self.language,
			"segments": [s.to_dict() for s in self.segments],
			"durationMs": duration_ms,
			"unit": "ms",
		}


def _sec_to_ms(value: float | int | None) -> int:
	if value is None:
		return 0
	try:
		return max(0, int(float(value) * 1000))
	except (TypeError, ValueError):
		return 0


def _load_faster_whisper():
	try:
		from faster_whisper import WhisperModel  # type: ignore

		return WhisperModel
	except ModuleNotFoundError:
		raise AsrError("dependency_missing", "faster-whisper is not installed")


def transcribe_with_faster_whisper(
	*,
	audio_path: Path,
	model_size: str = "base",
	device: str = "cpu",
	compute_type: str = "int8",
	vad_filter: bool = True,
) -> AsrResult:
	"""Transcribe audio via faster-whisper.

	Outputs ms-based segments (startMs/endMs) aligned to the audio timeline.

	Raises AsrError with kinds:
	- dependency_missing
	- model_missing
	- resource_exhausted
	- content_error
	"""

	if not audio_path.exists() or not audio_path.is_file():
		raise AsrError("content_error", "audio file not readable")

	WhisperModel = _load_faster_whisper()

	try:
		model = WhisperModel(model_size, device=device, compute_type=compute_type)
	except Exception as e:
		# Model download/load failures are typically reported as OSError/RuntimeError.
		raise AsrError("model_missing", "failed to load faster-whisper model", details={"type": type(e).__name__})

	try:
		segments_iter, info = model.transcribe(str(audio_path), vad_filter=vad_filter)
	except MemoryError:
		raise AsrError("resource_exhausted", "out of memory during ASR")
	except Exception as e:
		raise AsrError("content_error", "ASR transcription failed", details={"type": type(e).__name__})

	language = getattr(info, "language", None)
	if not isinstance(language, str) or not language:
		language = None

	segments: list[AsrSegment] = []
	last_end = 0
	try:
		for seg in segments_iter:
			start_ms = _sec_to_ms(getattr(seg, "start", None))
			end_ms = _sec_to_ms(getattr(seg, "end", None))
			text = getattr(seg, "text", "")
			if not isinstance(text, str):
				text = str(text)
			text = text.strip()
			if end_ms <= start_ms:
				continue
			# Ensure monotonic non-decreasing timeline.
			if start_ms < last_end:
				start_ms = last_end
				if end_ms <= start_ms:
					continue
			segments.append(AsrSegment(start_ms=start_ms, end_ms=end_ms, text=text))
			last_end = end_ms
	except Exception as e:
		raise AsrError("content_error", "ASR segment parse failed", details={"type": type(e).__name__})

	if not segments:
		raise AsrError("content_error", "ASR produced empty transcript")

	return AsrResult(provider="faster-whisper", language=language, segments=segments)
