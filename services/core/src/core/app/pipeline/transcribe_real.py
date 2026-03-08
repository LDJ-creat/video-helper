from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from core.app.pipeline.media_source import plan_media_source
from core.app.pipeline.transcript_store import store_transcript_json
from core.contracts.error_codes import ErrorCode
from core.db.models.project import Project
from core.db.session import get_data_dir
from core.external.ffmpeg import FfmpegError, extract_audio_wav_16k_mono
from core.external.ytdlp import YtDlpError, download_with_ytdlp, fetch_video_title
from core.external.asr_faster_whisper import AsrError, transcribe_with_faster_whisper


@dataclass(frozen=True)
class TranscribeArtifacts:
	transcript: dict
	transcript_ref: str | None
	audio_ref: str | None
	transcript_meta: dict | None
	# For URL source: updated media path persisted to Project.source_path.
	updated_project_source_path: str | None


def _env_bool(name: str, default: bool = False) -> bool:
	raw = (os.environ.get(name) or "").strip().lower()
	if raw in {"1", "true", "yes", "y", "on"}:
		return True
	if raw in {"0", "false", "no", "n", "off"}:
		return False
	return default


def _now_ms() -> int:
	return int(time.time() * 1000)


def _env_int(name: str, default: int) -> int:
	raw = (os.environ.get(name) or "").strip()
	if not raw:
		return default
	try:
		return int(raw)
	except ValueError:
		return default


def _env_str(name: str) -> str | None:
	raw = (os.environ.get(name) or "").strip()
	return raw or None


def _maybe_set_project_title(*, project: Project) -> None:
	"""Best-effort: set project.title to the video's title when missing.

	This runs in the worker (off the API request path), so it's OK to spend a bit
	of time probing.
	"""

	if isinstance(project.title, str) and project.title.strip():
		return

	# Upload: derive from filename.
	if project.source_type == "upload" and isinstance(project.source_path, str) and project.source_path:
		try:
			stem = Path(project.source_path).name
			stem2 = Path(stem).stem.strip()
			if stem2:
				project.title = stem2
				project.updated_at_ms = _now_ms()
				return
		except Exception:
			pass

	# URL sources: probe via yt-dlp.
	if isinstance(project.source_url, str) and project.source_url.strip():
		timeout_s = float(max(1, _env_int("YTDLP_TITLE_TIMEOUT_S_WORKER", 30)))
		try:
			title = fetch_video_title(url=project.source_url, timeout_s=timeout_s)
			if isinstance(title, str) and title.strip():
				project.title = title.strip()
				project.updated_at_ms = _now_ms()
				return
		except Exception:
			return


def map_transcribe_error(exc: Exception) -> dict:
	"""Map internal exceptions to job.error payload.

	Must not leak sensitive paths/URLs.
	"""

	# Dependency missing (hard errors, no fallback).
	if isinstance(exc, YtDlpError) and exc.kind == "dependency_missing":
		return {"code": ErrorCode.YTDLP_MISSING, "message": str(exc), "details": {"reason": "dependency_missing", "step": "download"}}
	if isinstance(exc, FfmpegError) and exc.kind == "dependency_missing":
		return {"code": ErrorCode.FFMPEG_MISSING, "message": str(exc), "details": {"reason": "dependency_missing", "step": "ffmpeg"}}

	# Resource exhaustion.
	if isinstance(exc, (YtDlpError, FfmpegError, AsrError)) and getattr(exc, "kind", None) in {"resource_exhausted"}:
		step = "unknown"
		if isinstance(exc, YtDlpError):
			step = "download"
		elif isinstance(exc, FfmpegError):
			step = "ffmpeg"
		elif isinstance(exc, AsrError):
			step = "asr"
		return {"code": ErrorCode.RESOURCE_EXHAUSTED, "message": "Resource exhausted", "details": {"reason": "resource_exhausted", "step": step}}

	# Model / dependency missing.
	if isinstance(exc, AsrError) and exc.kind == "dependency_missing":
		details = {"reason": "dependency_missing", "step": "asr"}
		if isinstance(getattr(exc, "details", None), dict):
			for k in (
				"type",
				"error",
				"missingFile",
				"modelSize",
				"modelDir",
				"cacheDir",
				"fallbackTried",
				"downloadErrorType",
				"downloadError",
				"vad",
			):
				if k in exc.details:
					details[k] = exc.details.get(k)
		return {"code": ErrorCode.JOB_STAGE_FAILED, "message": "ASR dependency missing", "details": details}
	if isinstance(exc, AsrError) and exc.kind == "model_missing":
		details = {"reason": "model_missing", "step": "asr"}
		if isinstance(getattr(exc, "details", None), dict):
			for k in (
				"type",
				"error",
				"missingFile",
				"modelSize",
				"modelDir",
				"cacheDir",
				"fallbackTried",
				"downloadErrorType",
				"downloadError",
				"vad",
			):
				if k in exc.details:
					details[k] = exc.details.get(k)
		return {"code": ErrorCode.JOB_STAGE_FAILED, "message": "ASR model not available", "details": details}

	# Timeouts.
	if isinstance(exc, (YtDlpError, FfmpegError)) and getattr(exc, "kind", None) == "timeout":
		step = "download" if isinstance(exc, YtDlpError) else "ffmpeg"
		return {"code": ErrorCode.JOB_STAGE_FAILED, "message": "Stage timed out", "details": {"reason": "timeout", "step": step}}
	if isinstance(exc, AsrError) and exc.kind == "timeout":
		return {"code": ErrorCode.JOB_STAGE_FAILED, "message": "Stage timed out", "details": {"reason": "timeout", "step": "asr"}}

	# Content issues.
	if isinstance(exc, FfmpegError) and exc.kind == "no_audio":
		details = {"reason": "no_audio", "step": "ffmpeg"}
		if isinstance(getattr(exc, "details", None), dict):
			for k in ("exitCode", "ffmpegTail"):
				if k in exc.details:
					details[k] = exc.details.get(k)
		return {"code": ErrorCode.JOB_STAGE_FAILED, "message": "Media has no audio", "details": details}
	if isinstance(exc, YtDlpError) and exc.kind == "content_error" and isinstance(getattr(exc, "details", None), dict):
		if exc.details.get("type") == "invalid_source_url":
			return {
				"code": ErrorCode.JOB_STAGE_FAILED,
				"message": "Invalid sourceUrl for yt-dlp",
				"details": {
					"reason": "invalid_source_url",
					"step": "download",
					"source": exc.details.get("source"),
				},
			}
		if exc.details.get("cookiesError") in {"cookie_db_copy_failed", "cookie_dpapi_decrypt_failed"}:
			return {
				"code": ErrorCode.JOB_STAGE_FAILED,
				"message": "Cannot read browser cookies on this machine. Export cookies.txt and pass it to yt-dlp.",
				"details": {"reason": "cookies_required", "source": exc.details.get("source")},
			}
		if exc.details.get("blocked") is True and isinstance(exc.details.get("httpStatus"), int):
			status = int(exc.details.get("httpStatus"))
			# Include non-sensitive cookie diagnostics to help operators understand
			# whether cookies were actually detected on this machine.
			cookie_diag: dict = {}
			for k in ("cookiesProvided", "cookiesFromBrowser", "cookiesFileExists", "cookiesFileBytes"):
				if k in exc.details:
					cookie_diag[k] = exc.details.get(k)
			return {
				"code": ErrorCode.JOB_STAGE_FAILED,
				"message": f"Source blocked by provider (HTTP {status}). Provide cookies for yt-dlp.",
				"details": {"reason": "content_blocked", "source": exc.details.get("source"), "httpStatus": status, **cookie_diag},
			}
	if isinstance(exc, YtDlpError) and exc.kind == "output_not_found":
		return {
			"code": ErrorCode.JOB_STAGE_FAILED,
			"message": "yt-dlp reported success but no output file was produced.",
			"details": {
				"reason": "output_not_found",
				"step": "download",
				"source": (getattr(exc, "details", None) or {}).get("source"),
				"ytdlpTail": (getattr(exc, "details", None) or {}).get("outputTail"),
			},
		}
	if isinstance(exc, (YtDlpError, FfmpegError, AsrError)) and getattr(exc, "kind", None) in {"content_error", "output_not_found"}:
		step = "unknown"
		if isinstance(exc, YtDlpError):
			step = "download"
		elif isinstance(exc, FfmpegError):
			step = "ffmpeg"
		elif isinstance(exc, AsrError):
			step = "asr"
		details = {"reason": "content_error", "step": step, "kind": getattr(exc, "kind", None)}
		if isinstance(getattr(exc, "details", None), dict):
			# Keep only safe/curated detail keys.
			for k in ("type", "exitCode", "ffmpegTail", "outputTail"):
				if k in exc.details:
					details[k] = exc.details.get(k)
		return {"code": ErrorCode.JOB_STAGE_FAILED, "message": "Invalid media content", "details": details}

	return {"code": ErrorCode.JOB_STAGE_FAILED, "message": "Unexpected error", "details": {"reason": "unexpected"}}


def run_real_transcribe(
	*,
	project: Project,
	job_id: str,
	default_duration_ms: int,
	progress_cb: object | None = None,
	log_cb: object | None = None,
) -> TranscribeArtifacts:
	"""Real transcribe closed-loop: (optional) yt-dlp → ffmpeg → faster-whisper → transcript file.

	This function is synchronous; callers can run it inside worker loop.
	"""

	def _progress(value: float, msg: str) -> None:
		if progress_cb and callable(progress_cb):
			progress_cb(value, msg)
		if log_cb and callable(log_cb):
			log_cb(msg)

	plan = plan_media_source(project)
	_maybe_set_project_title(project=project)

	_progress(0.05, f"mediaSource={plan.kind}")
	updated_source_path: str | None = None
	media_abs: Path | None = plan.media_abs_path

	if plan.requires_download:
		_progress(0.10, "download=starting")
		if not plan.download_dir_abs or not plan.source_url:
			raise ValueError("invalid url source plan")
		stop_evt = threading.Event()
		start_ts = time.time()

		def _download_heartbeat() -> None:
			# Keep UX alive during long yt-dlp runs (which are otherwise a single blocking call).
			interval_s = 15.0
			raw = (os.environ.get("YTDLP_DOWNLOAD_HEARTBEAT_S") or "").strip()
			if raw:
				try:
					interval_s = float(max(5.0, float(raw)))
				except ValueError:
					interval_s = 15.0
			while not stop_evt.wait(interval_s):
				elapsed = int(max(0.0, time.time() - start_ts))
				_progress(0.10, f"download=running elapsed={elapsed}s")

		th = threading.Thread(target=_download_heartbeat, name="ytdlp-download-heartbeat", daemon=True)
		th.start()
		try:
			res = download_with_ytdlp(url=plan.source_url, output_dir=plan.download_dir_abs / job_id, base_filename="source")
		finally:
			stop_evt.set()
		updated_source_path = res.rel_path
		media_abs = res.abs_path
		_progress(0.20, f"download=ok media={res.rel_path}")
	else:
		_progress(0.20, "download=skip")

	if media_abs is None:
		raise ValueError("media file not resolved")

	# Extract audio
	_progress(0.25, "audio=extracting")
	audio_result = extract_audio_wav_16k_mono(
		input_path=media_abs,
		output_dir=(get_data_dir() / project.project_id / "artifacts" / job_id),
		base_filename="audio",
	)
	_progress(0.35, f"audio=ok wav={audio_result.rel_path}")

	# ASR
	_progress(0.40, "asr=starting provider=faster-whisper")
	model_size = (os.environ.get("TRANSCRIBE_MODEL_SIZE") or "base").strip() or "base"
	device = (os.environ.get("TRANSCRIBE_DEVICE") or "cpu").strip() or "cpu"
	compute_type = (os.environ.get("TRANSCRIBE_COMPUTE_TYPE") or "int8").strip() or "int8"
	asr = transcribe_with_faster_whisper(
		audio_path=audio_result.abs_path,
		model_size=model_size,
		device=device,
		compute_type=compute_type,
	)
	transcript = asr.to_transcript_dict()
	_progress(0.45, f"asr=ok language={asr.language or 'unknown'}")

	# Persist transcript file
	stored = store_transcript_json(project_id=project.project_id, job_id=job_id, transcript=transcript)
	_progress(0.50, f"transcript=stored ref={stored.rel_path}")

	meta = {
		"provider": transcript.get("provider") or "unknown",
		"language": transcript.get("language"),
		"audioRef": audio_result.rel_path,
		"sha256": stored.sha256,
	}

	return TranscribeArtifacts(
		transcript=transcript,
		transcript_ref=stored.rel_path,
		audio_ref=audio_result.rel_path,
		transcript_meta=meta,
		updated_project_source_path=updated_source_path,
	)
