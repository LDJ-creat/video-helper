from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import logging
import os
import re
import time
import threading
import inspect
from contextlib import contextmanager

from core.db.session import get_data_dir

logger = logging.getLogger(__name__)


_WIN_ABS_PATH_RE = re.compile(r"[A-Za-z]:\\[^\s\"']+")


_HF_DEFAULT_ENDPOINT = "https://huggingface.co"
_HF_MIRROR_ENDPOINT = "https://hf-mirror.com"
_ASR_DOWNLOAD_MAX_ATTEMPTS = 3


# Process-local WhisperModel cache.
# Rationale: initializing WhisperModel can be expensive (model load + CT2 init).
# The worker can process multiple jobs sequentially; caching significantly reduces
# per-job latency without changing transcript quality.
_MODEL_CACHE: dict[tuple, object] = {}
_MODEL_CACHE_LOCK = threading.Lock()
_MODEL_KEY_LOCKS: dict[tuple, threading.Lock] = {}


class _AutoCudaFallback(Exception):
	"""Internal control-flow exception.

	Raised when device=auto selected CUDA but runtime fails in a way that looks
	CUDA/GPU-related. Caller should retry once on CPU.
	"""

	def __init__(self, exc: Exception):
		super().__init__(str(exc))
		self.exc = exc


def _looks_like_cuda_failure_text(text: str) -> bool:
	if not isinstance(text, str):
		text = str(text)
	t = text.lower()
	# Heuristic keywords for common CUDA initialization/runtime failures.
	return any(k in t for k in (
		"cuda",
		"cublas",
		"cudnn",
		"cufft",
		"curand",
		"nvrtc",
		"nvcuda",
		"libcuda",
		"cudart",
		"no kernel image",
		"driver version",
		"cuda driver",
		"failed to initialize cuda",
		"failed to create cublas",
		"failed to load cublas",
		"could not load library",
		"cannot load library",
		"dll load failed",
		"cuinit",
		"cudagetdevicecount",
		"device ordinal",
		"invalid device",
		"gpu",
	))


def _looks_like_cuda_failure(exc: Exception) -> bool:
	try:
		if _looks_like_cuda_failure_text(str(exc)):
			return True
		mod = (type(exc).__module__ or "").lower()
		name = (type(exc).__name__ or "").lower()
		# Some wrappers hide CUDA in type/module.
		if "ctranslate2" in mod or "faster_whisper" in mod:
			if _looks_like_cuda_failure_text(str(exc)):
				return True
		# On Windows, missing CUDA DLLs often show up as OSError/RuntimeError.
		if name in {"oserror", "runtimeerror"} and _looks_like_cuda_failure_text(str(exc)):
			return True
	except Exception:
		return False
	return False


def _exception_text_for_cuda_fallback(exc: Exception) -> str:
	parts: list[str] = [str(exc)]
	# Avoid referencing AsrError directly here (defined later in this module).
	if type(exc).__name__ == "AsrError" and hasattr(exc, "details"):
		try:
			d = getattr(exc, "details", None) or {}
			for k in ("error", "downloadError"):
				v = d.get(k)
				if isinstance(v, str) and v:
					parts.append(v)
			# Some nested dicts may contain the underlying error.
			dd = d.get("downloadDetails")
			if isinstance(dd, dict):
				v = dd.get("error")
				if isinstance(v, str) and v:
					parts.append(v)
		except Exception:
			pass
	return " | ".join(p for p in parts if isinstance(p, str) and p)


def _get_model_key(
	*,
	model_size_or_path: str,
	device: str,
	device_index: int | list[int],
	compute_type: str,
	cpu_threads: int,
	num_workers: int,
) -> tuple:
	# NOTE: keep key stable and JSON-unsafe types out.
	if isinstance(device_index, list):
		device_index_key: tuple = tuple(int(x) for x in device_index)
	else:
		device_index_key = int(device_index)
	return (
		"faster-whisper",
		str(model_size_or_path),
		str(device or ""),
		device_index_key,
		str(compute_type or ""),
		int(cpu_threads),
		int(num_workers),
	)


def _normalize_device(value: str | None) -> str:
	# faster-whisper supports device: auto/cpu/cuda
	# Keep backward compatibility: treat empty as cpu.
	if not isinstance(value, str):
		return "cpu"
	v = value.strip().lower()
	if not v:
		return "cpu"
	# Common aliases.
	if v in {"gpu", "nvidia"}:
		return "cuda"
	return v


def _normalize_compute_type_optional(value: str | None) -> str | None:
	# faster-whisper accepts values like: default, float16, int8, int8_float16, ...
	# We treat empty/None as "unspecified" so auto-mode can choose per device.
	if value is None:
		return None
	if not isinstance(value, str):
		return str(value)
	v = value.strip()
	return v or None


def _get_cuda_device_count() -> int:
	# Best-effort CUDA availability check.
	# - If ctranslate2 is built without CUDA, this typically returns 0.
	# - Respect common operator disables via CUDA_VISIBLE_DEVICES.
	cvd = os.environ.get("CUDA_VISIBLE_DEVICES")
	if isinstance(cvd, str) and cvd.strip() in {"", "-1", "none", "void"}:
		return 0
	try:
		import ctranslate2  # type: ignore

		fn = getattr(ctranslate2, "get_cuda_device_count", None)
		if callable(fn):
			return int(fn())
	except Exception:
		return 0
	return 0


def _select_device_and_compute_type(*, device: str, compute_type: str | None) -> tuple[str, str]:
	dev = _normalize_device(device)
	ct = _normalize_compute_type_optional(compute_type)

	if dev == "auto":
		cuda_count = _get_cuda_device_count()
		dev = "cuda" if cuda_count > 0 else "cpu"

	if ct is None:
		# Quality-preserving defaults.
		if dev == "cuda":
			ct = "float16"
		else:
			ct = "int8"

	return dev, ct


def _parse_int_env(value: str | None, *, default: int) -> int:
	if not isinstance(value, str):
		return default
	raw = value.strip()
	if not raw:
		return default
	try:
		return int(raw)
	except ValueError:
		return default


def _get_int_env_optional(name: str) -> int | None:
	raw = os.environ.get(name)
	if raw is None:
		return None
	text = raw.strip()
	if not text:
		return None
	try:
		return int(text)
	except ValueError:
		return None


def _default_cpu_threads_for_concurrency(*, max_concurrent_jobs: int) -> int:
	# Only apply an opinionated default when there is concurrent job execution.
	# Otherwise keep 0 (library default) for best single-job performance.
	try:
		mc = int(max_concurrent_jobs)
	except Exception:
		mc = 1
	if mc <= 1:
		return 0
	cpu_count = os.cpu_count() or 1
	# Spread cores across jobs to avoid oversubscription.
	return max(1, int(cpu_count) // mc)


def _parse_bool_env(value: str | None, *, default: bool) -> bool:
	if value is None:
		return default
	if not isinstance(value, str):
		return bool(value)
	v = value.strip().lower()
	if v in {"1", "true", "yes", "y", "on"}:
		return True
	if v in {"0", "false", "no", "n", "off"}:
		return False
	return default


def _create_whisper_model(
	*,
	WhisperModel,
	model_size_or_path: str,
	device: str,
	device_index: int | list[int],
	compute_type: str,
	cpu_threads: int,
	num_workers: int,
):
	# Build kwargs defensively based on installed faster-whisper version.
	kwargs: dict = {
		"device": device,
		"compute_type": compute_type,
		"device_index": device_index,
		"cpu_threads": cpu_threads,
		"num_workers": num_workers,
	}
	try:
		sig = inspect.signature(WhisperModel.__init__)
		params = sig.parameters
		filtered = {k: v for k, v in kwargs.items() if k in params}
		return WhisperModel(model_size_or_path, **filtered)
	except Exception:
		# Best-effort fallback.
		return WhisperModel(model_size_or_path, **kwargs)


def _get_or_create_cached_model(
	*,
	WhisperModel,
	model_size_or_path: str,
	device: str,
	device_index: int | list[int],
	compute_type: str,
	cpu_threads: int,
	num_workers: int,
):
	key = _get_model_key(
		model_size_or_path=model_size_or_path,
		device=device,
		device_index=device_index,
		compute_type=compute_type,
		cpu_threads=cpu_threads,
		num_workers=num_workers,
	)

	with _MODEL_CACHE_LOCK:
		cached = _MODEL_CACHE.get(key)
		if cached is not None:
			return cached, True
		lock = _MODEL_KEY_LOCKS.get(key)
		if lock is None:
			lock = threading.Lock()
			_MODEL_KEY_LOCKS[key] = lock

	with lock:
		with _MODEL_CACHE_LOCK:
			cached = _MODEL_CACHE.get(key)
			if cached is not None:
				return cached, True
		model = _create_whisper_model(
			WhisperModel=WhisperModel,
			model_size_or_path=model_size_or_path,
			device=device,
			device_index=device_index,
			compute_type=compute_type,
			cpu_threads=cpu_threads,
			num_workers=num_workers,
		)
		with _MODEL_CACHE_LOCK:
			_MODEL_CACHE[key] = model
		return model, False


def _invalidate_cached_model(
	*,
	model_size_or_path: str,
	device: str,
	device_index: int | list[int],
	compute_type: str,
	cpu_threads: int,
	num_workers: int,
) -> None:
	key = _get_model_key(
		model_size_or_path=model_size_or_path,
		device=device,
		device_index=device_index,
		compute_type=compute_type,
		cpu_threads=cpu_threads,
		num_workers=num_workers,
	)
	with _MODEL_CACHE_LOCK:
		_MODEL_CACHE.pop(key, None)
		_MODEL_KEY_LOCKS.pop(key, None)


def _reset_model_cache_for_tests() -> None:
	# Used by unit tests to avoid cross-test pollution.
	with _MODEL_CACHE_LOCK:
		_MODEL_CACHE.clear()
		_MODEL_KEY_LOCKS.clear()


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


def _normalize_hf_endpoint(value: str | None) -> str | None:
	if not isinstance(value, str):
		return None
	v = value.strip()
	if not v:
		return None
	# Keep a canonical form (no trailing slash) for stable comparisons/logs.
	while v.endswith("/"):
		v = v[:-1]
	return v or None


def _candidate_hf_endpoints() -> list[str]:
	"""Return ordered unique endpoints to try for Hugging Face downloads.

	Order:
	1) User/operator configured HF_ENDPOINT (if present)
	2) Official huggingface.co
	3) hf-mirror.com (China-friendly mirror)
	"""
	seen: set[str] = set()
	out: list[str] = []
	for raw in (
		_normalize_hf_endpoint(os.environ.get("HF_ENDPOINT")),
		_HF_DEFAULT_ENDPOINT,
		_HF_MIRROR_ENDPOINT,
	):
		v = _normalize_hf_endpoint(raw)
		if not v or v in seen:
			continue
		seen.add(v)
		out.append(v)
	return out


def _looks_transient_network_error(exc: Exception) -> bool:
	"""Heuristic: only retry on likely transient download/network errors."""
	name = type(exc).__name__
	mod = type(exc).__module__
	msg = str(exc).lower()

	# Some libraries wrap requests/urllib3 errors in a generic RuntimeError.
	if any(k in msg for k in (
		"connectionerror",
		"readtimeout",
		"connecttimeout",
		"timeout",
		"timed out",
		"max retries exceeded",
		"name resolution",
		"temporary failure",
		"connection reset",
		"connection refused",
		"proxyerror",
		"sslerror",
		"tls",
		"eof occurred",
	)):
		return True

	# Common requests/urllib3 exceptions.
	if name in {
		"ConnectionError",
		"ConnectTimeout",
		"ReadTimeout",
		"Timeout",
		"TimeoutError",
		"SSLError",
		"ProxyError",
		"ChunkedEncodingError",
	}:
		return True
	if any(m in (mod or "") for m in ("requests", "urllib3", "httpx", "huggingface_hub")):
		if any(k in msg for k in ("timeout", "timed out", "connection", "max retries", "name resolution", "ssl")):
			return True

	# Hugging Face hub may wrap network issues into a generic RuntimeError.
	if any(k in msg for k in (
		"temporary failure",
		"connection aborted",
		"connection reset",
		"connection refused",
		"tls",
		"eof occurred",
		"502",
		"503",
		"504",
		"gateway timeout",
		"bad gateway",
		"service unavailable",
		"read timed out",
		"connect timed out",
	)):
		return True

	return False


@contextmanager
def _temp_env(updates: dict[str, str | None]):
	old: dict[str, str | None] = {}
	try:
		for k, v in updates.items():
			old[k] = os.environ.get(k)
			if v is None:
				os.environ.pop(k, None)
			else:
				os.environ[k] = v
		yield
	finally:
		for k, prev in old.items():
			if prev is None:
				os.environ.pop(k, None)
			else:
				os.environ[k] = prev


def _download_model_with_auto_endpoint(
	*,
	download_model,
	model_size: str,
	model_dir: Path,
	data_dir: Path,
) -> dict:
	"""Download faster-whisper model with automatic HF endpoint fallback.

	- Tries endpoints in a deterministic order (official -> mirror)
	- Retries at most 3 times total (across endpoints)
	- Uses a stable HF cache directory under DATA_DIR unless operator overrides
	"""
	endpoints = _candidate_hf_endpoints()
	endpoints_tried: list[str] = []

	# Keep HF cache under DATA_DIR to improve resumability and avoid per-user caches
	# in packaged desktop builds. Respect operator overrides when set.
	hf_home = os.environ.get("HF_HOME")
	hug_cache = os.environ.get("HUGGINGFACE_HUB_CACHE")
	cache_updates: dict[str, str | None] = {}
	if not hf_home and not hug_cache:
		stable_hf_home = (data_dir / "cache" / "huggingface").resolve()
		stable_hf_home.mkdir(parents=True, exist_ok=True)
		cache_updates["HF_HOME"] = str(stable_hf_home)

	last_exc: Exception | None = None
	for attempt in range(1, _ASR_DOWNLOAD_MAX_ATTEMPTS + 1):
		endpoint = endpoints[(attempt - 1) % max(1, len(endpoints))] if endpoints else _HF_DEFAULT_ENDPOINT
		endpoints_tried.append(endpoint)
		updates = {"HF_ENDPOINT": endpoint, **cache_updates}
		try:
			with _temp_env(updates):
				download_model(model_size, output_dir=str(model_dir), cache_dir=None, local_files_only=False)
			return {"ok": True, "attempts": attempt, "endpointsTried": endpoints_tried}
		except Exception as e:
			last_exc = e
			transient = _looks_transient_network_error(e)
			logger.warning(
				"asr model download failed attempt=%s/%s endpoint=%s transient=%s type=%s",
				attempt,
				_ASR_DOWNLOAD_MAX_ATTEMPTS,
				endpoint,
				bool(transient),
				type(e).__name__,
			)

			# Always rotate endpoints and retry up to max attempts.
			# Only apply backoff for likely transient network errors.
			if attempt < _ASR_DOWNLOAD_MAX_ATTEMPTS and transient and not os.environ.get("PYTEST_CURRENT_TEST"):
				# 0.8s, 1.6s, ...
				sleep_s = 0.8 * (2 ** (attempt - 1))
				try:
					time.sleep(sleep_s)
				except Exception:
					pass

	# Failure: raise a structured AsrError with actionable hints.
	err_text = _scrub_error_text(str(last_exc) if last_exc else "unknown")
	if len(err_text) > 300:
		err_text = err_text[:300] + "…"
	raise AsrError(
		"model_missing",
		"failed to download faster-whisper model (auto-tried Hugging Face endpoints)",
		details={
			"type": type(last_exc).__name__ if last_exc else "unknown",
			"error": err_text,
			"modelSize": model_size,
			"attempts": _ASR_DOWNLOAD_MAX_ATTEMPTS,
			"endpointsTried": endpoints_tried,
			"hint": "Network to Hugging Face may be unstable; the app automatically tries official and https://hf-mirror.com. You can also set HF_ENDPOINT or configure a proxy/VPN, or prefetch the model in Settings.",
			"env": _safe_env_hints(),
		},
	)


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
		_download_model_with_auto_endpoint(
			download_model=download_model,
			model_size=model_size,
			model_dir=model_dir,
			data_dir=data_dir,
		)
		ok = _looks_like_model_dir(model_dir)
		logger.info("asr prefetch finished model=%s ok=%s", model_size, bool(ok))
		return {"ok": bool(ok), "alreadyPresent": False, "modelSize": model_size, "modelDir": model_dir_rel}
	except AsrError:
		# Preserve structured error details from the downloader.
		raise
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
	device_index: int | list[int] = 0,
	compute_type: str | None = None,
	vad_filter: bool = True,
	language: str | None = None,
	beam_size: int | None = None,
	best_of: int | None = None,
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

	auto_device_requested = isinstance(device, str) and device.strip().lower() == "auto"
	device_n, compute_n = _select_device_and_compute_type(device=device, compute_type=compute_type)

	# Optional knobs via env (kept here so callers don't need to thread them through).
	# Defaults match faster-whisper defaults.
	num_workers = _parse_int_env(os.environ.get("TRANSCRIBE_NUM_WORKERS"), default=1)
	# Allow overriding the device index via env (useful for desktop setups).
	if device_index == 0:
		device_index = _parse_int_env(os.environ.get("TRANSCRIBE_DEVICE_INDEX"), default=0)

	data_dir = get_data_dir().resolve()
	model_dir = _model_dir_for_size(data_dir=data_dir, model_size=model_size)
	model_dir_rel: str | None = None
	try:
		model_dir_rel = model_dir.relative_to(data_dir).as_posix()
	except Exception:
		model_dir_rel = None

	def _cpu_threads_for_device(device_for_attempt: str) -> int:
		# NOTE: cpu_threads=0 lets the library choose.
		cpu_threads_env = _get_int_env_optional("TRANSCRIBE_CPU_THREADS")
		if cpu_threads_env is not None:
			return int(cpu_threads_env)
		# Derive a conservative default under multi-job concurrency.
		if device_for_attempt != "cpu":
			return 0
		max_concurrent_jobs = _get_int_env_optional("MAX_CONCURRENT_JOBS") or 1
		return _default_cpu_threads_for_concurrency(max_concurrent_jobs=max_concurrent_jobs)

	def _maybe_raise_auto_cuda_fallback(
		*,
		exc: Exception,
		device_for_attempt: str,
		model_size_or_path: str,
		compute_for_attempt: str,
		cpu_threads_for_attempt: int,
	) -> None:
		if not (auto_device_requested and device_for_attempt == "cuda"):
			return
		if not _looks_like_cuda_failure(exc):
			return
		# Ensure we don't keep a broken CUDA model instance around.
		try:
			_invalidate_cached_model(
				model_size_or_path=model_size_or_path,
				device=device_for_attempt,
				device_index=device_index,
				compute_type=compute_for_attempt,
				cpu_threads=cpu_threads_for_attempt,
				num_workers=num_workers,
			)
		except Exception:
			pass
		raise _AutoCudaFallback(exc)

	def _run_attempt(*, device_for_attempt: str, compute_for_attempt: str) -> AsrResult:
		cpu_threads_for_attempt = _cpu_threads_for_device(device_for_attempt)

		# 1) Prefer explicit, user-discoverable model directory under DATA_DIR.
		model = None
		_cache_hit = False
		if _looks_like_model_dir(model_dir):
			try:
				model, _cache_hit = _get_or_create_cached_model(
					WhisperModel=WhisperModel,
					model_size_or_path=str(model_dir),
					device=device_for_attempt,
					device_index=device_index,
					compute_type=compute_for_attempt,
					cpu_threads=cpu_threads_for_attempt,
					num_workers=num_workers,
				)
			except Exception as e:
				_maybe_raise_auto_cuda_fallback(
					exc=e,
					device_for_attempt=device_for_attempt,
					model_size_or_path=str(model_dir),
					compute_for_attempt=compute_for_attempt,
					cpu_threads_for_attempt=cpu_threads_for_attempt,
				)
				err_text = str(e)
				if len(err_text) > 300:
					err_text = err_text[:300] + "…"

				# Common in the field: directory exists but is incomplete/corrupt.
				# Attempt to re-download missing assets into the same dir, then retry.
				if type(e).__name__ in {"NoSuchFile", "FileNotFoundError"}:
					try:
						logger.info("asr model heal starting model=%s dir=%s", model_size, model_dir_rel or "<unknown>")
						_download_model_with_auto_endpoint(
							download_model=download_model,
							model_size=model_size,
							model_dir=model_dir,
							data_dir=data_dir,
						)
						logger.info("asr model heal finished model=%s ok=%s", model_size, _looks_like_model_dir(model_dir))
						# Invalidate cache entry since we just updated the underlying directory.
						_invalidate_cached_model(
							model_size_or_path=str(model_dir),
							device=device_for_attempt,
							device_index=device_index,
							compute_type=compute_for_attempt,
							cpu_threads=cpu_threads_for_attempt,
							num_workers=num_workers,
						)
						model, _cache_hit = _get_or_create_cached_model(
							WhisperModel=WhisperModel,
							model_size_or_path=str(model_dir),
							device=device_for_attempt,
							device_index=device_index,
							compute_type=compute_for_attempt,
							cpu_threads=cpu_threads_for_attempt,
							num_workers=num_workers,
						)
					except Exception as e2:
						_maybe_raise_auto_cuda_fallback(
							exc=e2,
							device_for_attempt=device_for_attempt,
							model_size_or_path=str(model_dir),
							compute_for_attempt=compute_for_attempt,
							cpu_threads_for_attempt=cpu_threads_for_attempt,
						)
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
				_download_model_with_auto_endpoint(
					download_model=download_model,
					model_size=model_size,
					model_dir=model_dir,
					data_dir=data_dir,
				)
				logger.info("asr model download finished model=%s ok=%s", model_size, _looks_like_model_dir(model_dir))
				model, _cache_hit = _get_or_create_cached_model(
					WhisperModel=WhisperModel,
					model_size_or_path=str(model_dir),
					device=device_for_attempt,
					device_index=device_index,
					compute_type=compute_for_attempt,
					cpu_threads=cpu_threads_for_attempt,
					num_workers=num_workers,
				)
			except Exception as e:
				_maybe_raise_auto_cuda_fallback(
					exc=e,
					device_for_attempt=device_for_attempt,
					model_size_or_path=str(model_dir),
					compute_for_attempt=compute_for_attempt,
					cpu_threads_for_attempt=cpu_threads_for_attempt,
				)
				# 3) Last resort: reuse system HF cache (useful when a dev/web run already
				# downloaded the model). This still may fail on clean machines.
				err_type = type(e).__name__
				err_text = str(e)
				download_details: dict | None = None
				if isinstance(e, AsrError):
					download_details = getattr(e, "details", None) or None
					# Prefer the underlying error fields when present.
					try:
						err_type = str((download_details or {}).get("type") or err_type)
						err_text = str((download_details or {}).get("error") or err_text)
					except Exception:
						pass
				if len(err_text) > 300:
					err_text = err_text[:300] + "…"
				fallback_tried = True
				try:
					model, _cache_hit = _get_or_create_cached_model(
						WhisperModel=WhisperModel,
						model_size_or_path=str(model_size),
						device=device_for_attempt,
						device_index=device_index,
						compute_type=compute_for_attempt,
						cpu_threads=cpu_threads_for_attempt,
						num_workers=num_workers,
					)
				except Exception as e2:
					_maybe_raise_auto_cuda_fallback(
						exc=e2,
						device_for_attempt=device_for_attempt,
						model_size_or_path=str(model_size),
						compute_for_attempt=compute_for_attempt,
						cpu_threads_for_attempt=cpu_threads_for_attempt,
					)
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
							"downloadDetails": download_details,
							"env": _safe_env_hints(),
						},
					)

		segments_iter = None
		info = None
		try_vad_values = (vad_filter, False) if vad_filter else (False,)
		for use_vad in try_vad_values:
			try:
				transcribe_kwargs: dict = {
					"vad_filter": bool(use_vad),
				}
				if language:
					transcribe_kwargs["language"] = language
				if isinstance(beam_size, int) and beam_size > 0:
					transcribe_kwargs["beam_size"] = beam_size
				if isinstance(best_of, int) and best_of > 0:
					transcribe_kwargs["best_of"] = best_of
				# Filter kwargs to the installed faster-whisper signature.
				try:
					sig = inspect.signature(model.transcribe)
					params = sig.parameters
					transcribe_kwargs = {k: v for k, v in transcribe_kwargs.items() if k in params}
				except Exception:
					pass

				segments_iter, info = model.transcribe(str(audio_path), **transcribe_kwargs)
				break
			except MemoryError:
				raise AsrError("resource_exhausted", "out of memory during ASR")
			except Exception as e:
				_maybe_raise_auto_cuda_fallback(
					exc=e,
					device_for_attempt=device_for_attempt,
					model_size_or_path=str(model_dir) if _looks_like_model_dir(model_dir) else str(model_size),
					compute_for_attempt=compute_for_attempt,
					cpu_threads_for_attempt=cpu_threads_for_attempt,
				)
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
				raise AsrError(
					"content_error",
					"ASR transcription failed",
					details={"type": err_type, "error": _scrub_error_text(str(e))[:300]},
				)

		if segments_iter is None or info is None:
			raise AsrError("content_error", "ASR transcription failed", details={"type": "unknown"})

		info_language = getattr(info, "language", None)
		if not isinstance(info_language, str) or not info_language:
			info_language = None

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

		return AsrResult(provider="faster-whisper", language=info_language, segments=segments)

	try:
		return _run_attempt(device_for_attempt=device_n, compute_for_attempt=compute_n)
	except _AutoCudaFallback as e:
		# One-shot fallback: device=auto selected CUDA but runtime failed.
		scrubbed = _scrub_error_text(str(e.exc))
		if len(scrubbed) > 200:
			scrubbed = scrubbed[:200] + "…"
		logger.warning(
			"asr cuda failed in auto mode; falling back to cpu type=%s error=%s",
			type(e.exc).__name__,
			scrubbed,
		)
		cpu_dev, cpu_ct = _select_device_and_compute_type(device="cpu", compute_type=compute_type)
		return _run_attempt(device_for_attempt=cpu_dev, compute_for_attempt=cpu_ct)
