from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import logging
import os
import re

from core.db.session import get_data_dir

logger = logging.getLogger(__name__)


_WIN_ABS_PATH_RE = re.compile(r"[A-Za-z]:\\[^\s\"']+")


def _scrub_error_text(text: str) -> str:
	# Avoid leaking full absolute paths in job payloads/logs.
	# Keep the message useful but replace Windows absolute paths.
	if not isinstance(text, str):
		text = str(text)
	text = _WIN_ABS_PATH_RE.sub("<path>", text)
	return text


def _extract_missing_file(exc: Exception, fallback_text: str) -> str | None:
	# Best-effort: many IO-ish exceptions expose filename/path.
	for attr in ("filename", "path", "filepath"):
		v = getattr(exc, attr, None)
		if isinstance(v, str) and v:
			try:
				return Path(v).name
			except Exception:
				return v
	# Try to parse a path-like tail from the message.
	try:
		m = re.search(r"([A-Za-z]:\\[^\s\"']+)$", fallback_text)
		if m:
			return Path(m.group(1)).name
	except Exception:
		pass
	return None


def _is_vad_onnx_missing_error(*, exc: Exception, raw_text: str, missing_file: str | None) -> bool:
	"""Heuristic: identify VAD asset load failures (Silero VAD ONNX)."""
	msg_l = (raw_text or "").lower()
	if "onnx" in msg_l or "onnxruntime" in msg_l or "silero" in msg_l or "vad" in msg_l:
		return True
	if missing_file and missing_file.lower().endswith(".onnx"):
		return True
	return False


def _get_vad_asset_diagnostics() -> dict:
	"""Best-effort diagnostics for Silero VAD asset resolution.

	This is primarily to debug PyInstaller packaging issues where
	`faster_whisper.utils.get_assets_path()` may resolve to an archive/virtual
	path instead of a real on-disk directory.
	"""
	info: dict = {}
	try:
		import faster_whisper.utils as fw_utils
		from faster_whisper.utils import get_assets_path

		utils_file = getattr(fw_utils, "__file__", None)
		if isinstance(utils_file, str) and utils_file:
			info["fasterWhisperUtilsFile"] = _scrub_error_text(utils_file)

		assets_path = get_assets_path()
		if isinstance(assets_path, str) and assets_path:
			info["fasterWhisperAssetsPath"] = _scrub_error_text(assets_path)
			vad_onnx_path = str(Path(assets_path) / "silero_vad_v6.onnx")
			info["vadOnnxPath"] = _scrub_error_text(vad_onnx_path)
			try:
				p = Path(vad_onnx_path)
				info["vadOnnxExists"] = bool(p.exists())
				if p.exists() and p.is_file():
					info["vadOnnxSize"] = int(p.stat().st_size)
			except Exception:
				pass
	except Exception as e:
		err_text = _scrub_error_text(str(e))
		if len(err_text) > 300:
			err_text = err_text[:300] + "…"
		info["vadDiagErrorType"] = type(e).__name__
		info["vadDiagError"] = err_text
	return info


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
		from faster_whisper import WhisperModel, download_model  # type: ignore

		return WhisperModel, download_model
	except ModuleNotFoundError:
		raise AsrError("dependency_missing", "faster-whisper is not installed")


def _model_dir_for_size(*, data_dir: Path, model_size: str) -> Path:
	# Keep a stable, user-discoverable location under DATA_DIR.
	# We intentionally avoid putting the username/absolute path in logs.
	ms = (model_size or "base").strip() or "base"
	return (data_dir / "models" / "faster-whisper" / ms).resolve()


def _looks_like_model_dir(model_dir: Path) -> bool:
	# Match faster_whisper.download_model allow_patterns.
	# A partial download (e.g. missing tokenizer.json / vocabulary.*) can later
	# fail at runtime with low-level "NoSuchFile".
	needed = (
		"config.json",
		"model.bin",
		"tokenizer.json",
	)
	try:
		if not model_dir.is_dir():
			return False
		if not all((model_dir / n).is_file() for n in needed):
			return False
		# vocabulary.* (exact extension varies)
		return any(p.is_file() for p in model_dir.glob("vocabulary.*"))
	except Exception:
		return False


def _safe_env_hints() -> dict:
	# Useful for diagnosing why downloads don't happen in packaged builds.
	# Do not include values that may contain secrets.
	keys = (
		"HF_HUB_OFFLINE",
		"TRANSFORMERS_OFFLINE",
		"HF_HOME",
		"HUGGINGFACE_HUB_CACHE",
		"HF_ENDPOINT",
	)
	out: dict = {}
	for k in keys:
		v = os.environ.get(k)
		if v is None:
			continue
		# Keep it compact; do not leak full paths if operator considers them sensitive.
		out[k] = v
	return out


def prefetch_faster_whisper_model(*, model_size: str = "base") -> dict:
	"""Best-effort download of faster-whisper model into DATA_DIR.

	Returns safe metadata (no absolute paths).
	"""
	data_dir = get_data_dir().resolve()
	model_dir = _model_dir_for_size(data_dir=data_dir, model_size=model_size)
	model_dir_rel = None
	try:
		model_dir_rel = model_dir.relative_to(data_dir).as_posix()
	except Exception:
		model_dir_rel = None

	WhisperModel, download_model = _load_faster_whisper()

	if _looks_like_model_dir(model_dir):
		return {"ok": True, "alreadyPresent": True, "modelSize": model_size, "modelDir": model_dir_rel}

	model_dir.mkdir(parents=True, exist_ok=True)
	logger.info("asr prefetch starting model=%s dir=%s", model_size, model_dir_rel or "<unknown>")
	try:
		download_model(model_size, output_dir=str(model_dir), cache_dir=None, local_files_only=False)
		ok = _looks_like_model_dir(model_dir)
		logger.info("asr prefetch finished model=%s ok=%s", model_size, bool(ok))
		return {"ok": bool(ok), "alreadyPresent": False, "modelSize": model_size, "modelDir": model_dir_rel}
	except Exception as e:
		logger.warning("asr prefetch failed model=%s type=%s", model_size, type(e).__name__)
		err_text = str(e)
		if len(err_text) > 300:
			err_text = err_text[:300] + "…"
		raise AsrError(
			"model_missing",
			"failed to prefetch faster-whisper model",
			details={
				"type": type(e).__name__,
				"error": err_text,
				"modelSize": model_size,
				"modelDir": model_dir_rel,
				"env": _safe_env_hints(),
			},
		)


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

	WhisperModel, download_model = _load_faster_whisper()

	data_dir = get_data_dir().resolve()
	model_dir = _model_dir_for_size(data_dir=data_dir, model_size=model_size)
	model_dir_rel: str | None = None
	try:
		model_dir_rel = model_dir.relative_to(data_dir).as_posix()
	except Exception:
		model_dir_rel = None

	# 1) Prefer explicit, user-discoverable model directory under DATA_DIR.
	if _looks_like_model_dir(model_dir):
		try:
			model = WhisperModel(str(model_dir), device=device, compute_type=compute_type)
		except Exception as e:
			err_text = str(e)
			if len(err_text) > 300:
				err_text = err_text[:300] + "…"

			# Common in the field: directory exists but is incomplete/corrupt.
			# Attempt to re-download missing assets into the same dir, then retry.
			if type(e).__name__ in {"NoSuchFile", "FileNotFoundError"}:
				try:
					logger.info("asr model heal starting model=%s dir=%s", model_size, model_dir_rel or "<unknown>")
					download_model(model_size, output_dir=str(model_dir), cache_dir=None, local_files_only=False)
					logger.info("asr model heal finished model=%s ok=%s", model_size, _looks_like_model_dir(model_dir))
					model = WhisperModel(str(model_dir), device=device, compute_type=compute_type)
				except Exception as e2:
					err2 = str(e2)
					if len(err2) > 300:
						err2 = err2[:300] + "…"
					raise AsrError(
						"model_missing",
						"failed to load faster-whisper model from local cache",
						details={
							"type": type(e2).__name__,
							"error": err2,
							"modelSize": model_size,
							"modelDir": model_dir_rel,
						},
					)

			raise AsrError(
				"model_missing",
				"failed to load faster-whisper model from local cache",
				details={
					"type": type(e).__name__,
					"error": err_text,
					"modelSize": model_size,
					"modelDir": model_dir_rel,
				},
			)
	else:
		# 2) Attempt to download into DATA_DIR (best-effort). This makes packaged
		# desktops reproducible and avoids relying on per-user HF caches.
		fallback_tried = False
		try:
			model_dir.mkdir(parents=True, exist_ok=True)
			logger.info("asr model download starting model=%s dir=%s", model_size, model_dir_rel or "<unknown>")
			download_model(model_size, output_dir=str(model_dir), cache_dir=None, local_files_only=False)
			logger.info("asr model download finished model=%s ok=%s", model_size, _looks_like_model_dir(model_dir))
			model = WhisperModel(str(model_dir), device=device, compute_type=compute_type)
		except Exception as e:
			# 3) Last resort: reuse system HF cache (useful when a dev/web run already
			# downloaded the model). This still may fail on clean machines.
			err_type = type(e).__name__
			err_text = str(e)
			if len(err_text) > 300:
				err_text = err_text[:300] + "…"
			fallback_tried = True
			try:
				model = WhisperModel(model_size, device=device, compute_type=compute_type)
			except Exception as e2:
				raise AsrError(
					"model_missing",
					"failed to load faster-whisper model",
					details={
						"type": type(e2).__name__,
						"fallbackTried": bool(fallback_tried),
						"modelSize": model_size,
						"modelDir": model_dir_rel,
						"downloadErrorType": err_type,
						"downloadError": err_text,
						"env": _safe_env_hints(),
					},
				)

	segments_iter = None
	info = None
	try_vad_values = (vad_filter, False) if vad_filter else (False,)
	for use_vad in try_vad_values:
		try:
			segments_iter, info = model.transcribe(
				str(audio_path),
				vad_filter=bool(use_vad),
			)
			break
		except MemoryError:
			raise AsrError("resource_exhausted", "out of memory during ASR")
		except Exception as e:
			err_type = type(e).__name__
			if err_type in {"NoSuchFile", "FileNotFoundError"}:
				raw_text = str(e)
				missing_file = _extract_missing_file(e, raw_text)
				looks_like_vad_missing = _is_vad_onnx_missing_error(
					exc=e,
					raw_text=raw_text,
					missing_file=missing_file,
				)
				# If this looks like missing VAD assets and VAD was enabled, retry once
				# without VAD before surfacing an error.
				if use_vad and looks_like_vad_missing:
					diag = _get_vad_asset_diagnostics()
					logger.warning(
						"asr vad unavailable; retrying without vad_filter (model=%s) diag=%s",
						model_size,
						diag,
					)
					continue

				err_text = _scrub_error_text(raw_text)
				if len(err_text) > 300:
					err_text = err_text[:300] + "…"
				still_exists = False
				try:
					still_exists = audio_path.exists() and audio_path.is_file()
				except Exception:
					still_exists = False
				if not still_exists:
					raise AsrError(
						"content_error",
						"audio file not readable",
						details={"type": err_type, "error": err_text, "missingFile": missing_file},
					)
				raise AsrError(
					"model_missing",
					"failed to transcribe due to missing model files",
					details={
						"type": err_type,
						"error": err_text,
						"missingFile": missing_file,
						"modelSize": model_size,
						"modelDir": model_dir_rel,
						"vad": _get_vad_asset_diagnostics() if looks_like_vad_missing else None,
					},
				)
			raise AsrError("content_error", "ASR transcription failed", details={"type": err_type})

	if segments_iter is None or info is None:
		raise AsrError("content_error", "ASR transcription failed", details={"type": "unknown"})

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
