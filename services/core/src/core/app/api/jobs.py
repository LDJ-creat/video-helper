from __future__ import annotations

import asyncio
import time
import uuid
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlsplit, urlunsplit
from urllib.request import Request as UrlRequest
from urllib.request import urlopen

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from starlette.datastructures import UploadFile
from sqlalchemy.orm import Session

from core.contracts.error_codes import ErrorCode
from core.contracts.error_envelope import build_error_envelope
from core.contracts.progress import normalize_progress
from core.contracts.stages import PublicStage, to_public_stage
from core.app.sse.event_bus import GLOBAL_JOB_EVENT_BUS
from core.app.metadata.video_metadata import MetadataError, extract_video_metadata
from core.db.repositories.llm_settings import get_llm_active, get_llm_provider_secret_ciphertext
from core.db.repositories.jobs import get_job_by_id
from core.db.models.job import Job
from core.db.models.project import Project
from core.db.models.result import Result
from core.db.session import get_db_session
from core.llm.active_test import LLMActiveTestError, run_llm_connectivity_test
from core.llm.catalog import find_provider, resolve_runtime_model_name
from core.llm.secrets_crypto import decrypt_api_key
from core.schemas.jobs import CreateJobRequest, JobCreatedDTO, JobDTO, ResumeProjectJobRequest
from core.schemas.logs import JobLogsPageDTO, LogItemDTO
from core.app.logs.job_logs import read_job_logs_page
from core.app.pipeline.llm_plan import build_plan_request, validate_plan
from core.storage.layout import allocate_upload_path
from core.storage.safe_paths import validate_single_dir_name
from core.external.ytdlp import fetch_video_title, probe_url_support


router = APIRouter(tags=["jobs"])


_KNOWN_URL_SOURCE_TYPES: set[str] = {"youtube", "bilibili"}
_UPLOAD_SOURCE_TYPE = "upload"
_GENERIC_URL_SOURCE_TYPE = "url"


def _canonical_source_url(source_type: str, source_url: str) -> str:
	"""Canonicalize external source URLs for project identity.

	We treat a Project as "the video" and a Job as "an analysis run".
	To avoid creating duplicate projects for the same video, we strip
	query/fragment noise and normalize host casing.
	"""

	# NOTE: This value is persisted as Project.source_url and later used by the
	# worker to download the media. Therefore canonicalization MUST preserve
	# any query params required to address the content (e.g., YouTube watch?v=...).
	try:
		parts = urlsplit(source_url)
	except Exception:
		return source_url

	scheme = (parts.scheme or "").lower()
	host = (parts.netloc or "").lower()
	path = parts.path or ""
	query_raw = parts.query or ""

	# Best-effort: resolve bilibili short links to their final URL before canonicalizing.
	# Keep timeout low; failures should not block job creation.
	if source_type == "bilibili" and (host == "b23.tv" or host.endswith(".b23.tv")):
		try:
			req = UrlRequest(
				source_url,
				headers={
					"User-Agent": "video-helper/1.0",
					"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
				},
				method="GET",
			)
			with urlopen(req, timeout=1.5) as resp:
				resolved = resp.geturl() or source_url
			parts = urlsplit(resolved)
			scheme = (parts.scheme or "").lower()
			host = (parts.netloc or "").lower()
			path = parts.path or ""
			query_raw = parts.query or ""
		except Exception:
			pass

	if path != "/":
		path = path.rstrip("/")
	if not path:
		path = "/"

	query = ""
	# Keep only the minimal, content-identifying query params for known sources.
	if source_type == "youtube":
		# Canonicalize all YouTube URLs to: https://www.youtube.com/watch?v=<id>
		# This improves dedupe across youtu.be, shorts, and watch variants.
		yt_host = "www.youtube.com"
		video_id: str | None = None
		if host == "youtu.be" or host.endswith(".youtu.be"):
			video_id = (path or "").strip("/").split("/")[0] or None
		elif host.endswith("youtube.com"):
			p = (path or "").rstrip("/")
			if p == "/watch":
				q = dict(parse_qsl(query_raw, keep_blank_values=True))
				v = (q.get("v") or "").strip()
				video_id = v or None
			elif p.startswith("/shorts/"):
				video_id = p[len("/shorts/") :].split("/")[0] or None
			elif p.startswith("/live/"):
				video_id = p[len("/live/") :].split("/")[0] or None
			elif p.startswith("/embed/"):
				video_id = p[len("/embed/") :].split("/")[0] or None

		if video_id:
			scheme = scheme or "https"
			host = yt_host
			path = "/watch"
			query = urlencode({"v": video_id})
		else:
			# Unknown/unparseable YouTube URL; keep canonical host casing, strip query noise.
			host = yt_host if (host.endswith("youtube.com") or host.endswith("youtu.be")) else host
			query = ""
	elif source_type == "bilibili":
		# Multi-part bilibili videos use ?p=2, which changes the addressed content.
		q = dict(parse_qsl(query_raw, keep_blank_values=True))
		p = (q.get("p") or "").strip()
		if p:
			query = urlencode({"p": p})
		else:
			query = ""
	else:
		# Generic URLs: keep query to avoid losing content-identifying parameters.
		query = query_raw

	if scheme and host:
		return urlunsplit((scheme, host, path, query, ""))
	return source_url


def _normalize_title(value: str | None) -> str | None:
	text = (value or "").strip()
	return text or None


def _normalize_output_language(value: str | None) -> str | None:
	text = (value or "").strip()
	if not text:
		return None
	# Keep it small and safe to store/log.
	if len(text) > 32:
		return text[:32]
	return text


def _max_upload_bytes() -> int:
	import os

	raw = os.environ.get("MAX_UPLOAD_MB")
	mb = 500
	if raw:
		try:
			mb = int(raw)
		except ValueError:
			mb = 500
	if mb < 1:
		mb = 1
	return mb * 1024 * 1024


def _is_supported_source_type(value: str) -> bool:
	return value in _KNOWN_URL_SOURCE_TYPES or value in {_UPLOAD_SOURCE_TYPE, _GENERIC_URL_SOURCE_TYPE}


def _infer_source_type_from_url(source_url: str) -> str:
	try:
		parsed = urlparse(source_url)
	except Exception:
		return _GENERIC_URL_SOURCE_TYPE

	host = (parsed.netloc or "").lower()
	if host.endswith("youtube.com") or host == "youtu.be" or host.endswith("youtu.be"):
		return "youtube"
	if host.endswith("bilibili.com") or host == "b23.tv" or host.endswith("b23.tv"):
		return "bilibili"
	return _GENERIC_URL_SOURCE_TYPE


def _is_valid_source_url(source_type: str, source_url: str) -> bool:
	try:
		parsed = urlsplit(source_url)
	except Exception:
		return False

	if parsed.scheme not in {"http", "https"}:
		return False

	host = (parsed.netloc or "").lower()
	if not host:
		return False

	# Generic URL source: accept any http(s) URL and let yt-dlp decide.
	if source_type == _GENERIC_URL_SOURCE_TYPE:
		return True

	if source_type == "youtube":
		if host == "youtu.be" or host.endswith("youtu.be"):
			# Short links carry the id in the path.
			return bool((parsed.path or "").strip("/"))
		if host.endswith("youtube.com"):
			p = (parsed.path or "")
			if p.rstrip("/") == "/watch":
				q = dict(parse_qsl(parsed.query or "", keep_blank_values=True))
				return bool((q.get("v") or "").strip())
			# Accept other stable content paths (shorts/live/embed, etc.).
			return bool(p)
		return False

	if source_type == "bilibili":
		return host.endswith("bilibili.com") or host == "b23.tv" or host.endswith("b23.tv")

	return False


def _is_supported_upload_filename(name: str | None) -> bool:
	if not name:
		return False
	suffix = Path(name).suffix.lower()
	return suffix in {".mp4", ".mkv", ".webm", ".mov"}


def _env_str(name: str) -> str | None:
	import os

	raw = os.environ.get(name)
	if raw is None:
		return None
	raw = raw.strip()
	return raw or None


def _env_int(name: str, default: int) -> int:
	raw = _env_str(name)
	if raw is None:
		return default
	try:
		return int(raw)
	except ValueError:
		return default


def _normalize_model_id(model: str) -> str:
	"""Keep consistent with pipeline LLM normalization."""

	m = (model or "").strip()
	lower = m.lower().replace("_", "-")
	if lower in {"minimax-2.1", "minimax2.1", "minimax 2.1", "minimax-m2.1", "minimax-m2_1"}:
		return "minimaxai/minimax-m2.1"
	return m


async def _llm_preflight_or_error(request: Request, session: Session) -> JSONResponse | None:
	"""Verify LLM connectivity before accepting a job.

	Rules:
	- If SQLite `llm_active` exists: LLM is considered selected -> preflight required.
	- Else: preflight uses env `LLM_API_BASE`/`LLM_API_KEY` when present.

	On failure, returns an error envelope response and job creation is aborted.
	"""

	active = get_llm_active(session)
	if isinstance(active, dict):
		provider_id = (active.get("providerId") or "").strip().lower()
		model_id = (active.get("modelId") or "").strip()
		provider = find_provider(provider_id)
		if provider is None:
			return JSONResponse(
				status_code=400,
				content=build_error_envelope(
					code=ErrorCode.VALIDATION_ERROR,
					message="Invalid LLM settings",
					details={"reason": "unknown_provider", "providerId": provider_id},
					request_id=getattr(request.state, "request_id", None),
				),
			)

		runtime_model = resolve_runtime_model_name(provider_id=provider.provider_id, model_id=model_id)
		if not runtime_model:
			return JSONResponse(
				status_code=400,
				content=build_error_envelope(
					code=ErrorCode.VALIDATION_ERROR,
					message="Invalid LLM settings",
					details={"reason": "model_not_found", "providerId": provider.provider_id, "modelId": model_id},
					request_id=getattr(request.state, "request_id", None),
				),
			)

		ciphertext = get_llm_provider_secret_ciphertext(session, provider_id=provider.provider_id)
		if not ciphertext:
			return JSONResponse(
				status_code=400,
				content=build_error_envelope(
					code=ErrorCode.VALIDATION_ERROR,
					message="LLM credentials missing",
					details={"reason": "missing_credentials"},
					request_id=getattr(request.state, "request_id", None),
				),
			)

		try:
			api_key = decrypt_api_key(ciphertext)
		except Exception:
			return JSONResponse(
				status_code=400,
				content=build_error_envelope(
					code=ErrorCode.VALIDATION_ERROR,
					message="Invalid LLM credentials",
					details={"reason": "invalid_credentials"},
					request_id=getattr(request.state, "request_id", None),
				),
			)

		base_url = provider.base_url
		model = runtime_model
	else:
		base_url = _env_str("LLM_API_BASE")
		api_key = _env_str("LLM_API_KEY")
		model = _normalize_model_id(_env_str("LLM_MODEL") or "minimaxai/minimax-m2.1")
		if not base_url or not api_key:
			return JSONResponse(
				status_code=400,
				content=build_error_envelope(
					code=ErrorCode.VALIDATION_ERROR,
					message="LLM credentials missing",
					details={"reason": "missing_credentials", "suggest": "Set LLM_API_BASE and LLM_API_KEY"},
					request_id=getattr(request.state, "request_id", None),
				),
			)

	# Keep job creation fast even if operator sets a large timeout for full requests.
	env_timeout_s = float(max(1, _env_int("LLM_TIMEOUT_S", 180)))
	# Some providers have slow first-byte latency; allow override for smoke/ops.
	preflight_cap_s = float(max(1, _env_int("LLM_PREFLIGHT_TIMEOUT_S", 30)))
	timeout_s = min(preflight_cap_s, env_timeout_s)

	try:
		await asyncio.to_thread(
			run_llm_connectivity_test,
			base_url=base_url,
			api_key=api_key,
			model=model,
			timeout_s=timeout_s,
		)
		return None
	except LLMActiveTestError as e:
		return JSONResponse(
			status_code=400,
			content=build_error_envelope(
				code=ErrorCode.VALIDATION_ERROR,
				message="LLM preflight failed",
				details={"reason": e.reason},
				request_id=getattr(request.state, "request_id", None),
			),
		)


@router.post("/jobs", response_model=JobCreatedDTO)
async def create_job(request: Request, session: Session = Depends(get_db_session)):
	content_type = (request.headers.get("content-type") or "").lower()

	if content_type.startswith("application/json"):
		try:
			payload = await request.json()
		except Exception:
			return JSONResponse(
				status_code=400,
				content=build_error_envelope(
					code=ErrorCode.VALIDATION_ERROR,
					message="Invalid JSON body",
					request_id=getattr(request.state, "request_id", None),
				),
			)

		if isinstance(payload, dict):
			for forbidden_key in ("sourceFilePath", "source_file_path", "sourcePath", "source_path"):
				if forbidden_key in payload:
					return JSONResponse(
						status_code=400,
						content=build_error_envelope(
							code=ErrorCode.VALIDATION_ERROR,
							message="Local file path is not allowed",
							details={"field": forbidden_key},
							request_id=getattr(request.state, "request_id", None),
						),
					)

		try:
			req = CreateJobRequest.model_validate(payload)
		except Exception:
			return JSONResponse(
				status_code=400,
				content=build_error_envelope(
					code=ErrorCode.VALIDATION_ERROR,
					message="Invalid request",
					request_id=getattr(request.state, "request_id", None),
				),
			)

		source_type_raw = (req.sourceType or "").strip().lower()
		source_type_from_client = bool(source_type_raw)
		source_type = source_type_raw or _infer_source_type_from_url(req.sourceUrl)
		llm_mode = (req.llmMode or "backend").strip().lower()
		if llm_mode not in {"backend", "external"}:
			return JSONResponse(
				status_code=400,
				content=build_error_envelope(
					code=ErrorCode.VALIDATION_ERROR,
					message="Invalid llmMode",
					details={"llmMode": req.llmMode},
					request_id=getattr(request.state, "request_id", None),
				),
			)
		if source_type == _UPLOAD_SOURCE_TYPE:
			return JSONResponse(
				status_code=400,
				content=build_error_envelope(
					code=ErrorCode.UNSUPPORTED_SOURCE_TYPE,
					message="Unsupported sourceType",
					details={"sourceType": req.sourceType},
					request_id=getattr(request.state, "request_id", None),
				),
			)
		if source_type_from_client and not _is_supported_source_type(source_type):
			return JSONResponse(
				status_code=400,
				content=build_error_envelope(
					code=ErrorCode.UNSUPPORTED_SOURCE_TYPE,
					message="Unsupported sourceType",
					details={"sourceType": req.sourceType},
					request_id=getattr(request.state, "request_id", None),
				),
			)

		if not _is_valid_source_url(source_type, req.sourceUrl):
			return JSONResponse(
				status_code=400,
				content=build_error_envelope(
					code=ErrorCode.INVALID_SOURCE_URL,
					message="Invalid sourceUrl",
					details={"sourceUrl": req.sourceUrl, "sourceType": source_type},
					request_id=getattr(request.state, "request_id", None),
				),
			)

		# New UX: when client omits sourceType, we best-effort validate if yt-dlp supports the URL.
		# If probe is inconclusive (blocked/timeout), we still accept and let the worker handle it.
		if not source_type_from_client:
			supported, details = probe_url_support(url=req.sourceUrl, timeout_s=float(max(1, _env_int("YTDLP_PROBE_TIMEOUT_S", 6))))
			if supported is False:
				return JSONResponse(
					status_code=400,
					content=build_error_envelope(
						code=ErrorCode.INVALID_SOURCE_URL,
						message="Unsupported video URL",
						details={"reason": "unsupported_by_ytdlp", **(details or {})},
						request_id=getattr(request.state, "request_id", None),
					),
				)

		if llm_mode != "external":
			preflight = await _llm_preflight_or_error(request, session)
			if preflight is not None:
				return preflight

		now_ms = _now_ms()
		canonical_url = _canonical_source_url(source_type, req.sourceUrl)

		# Reuse existing project for the same external video.
		existing: Project | None = (
			session.query(Project)
			.filter(Project.source_type == source_type)
			.filter(
				(Project.source_url == canonical_url)
				| (Project.source_url.like(canonical_url + "%"))
			)
			.order_by(Project.updated_at_ms.desc())
			.first()
		)

		existing_result_id: str | None = None
		if existing is not None and isinstance(getattr(existing, "latest_result_id", None), str):
			candidate = (existing.latest_result_id or "").strip()
			if candidate:
				existing_result_id = candidate

		project_id = existing.project_id if existing is not None else str(uuid.uuid4())
		job_id = str(uuid.uuid4())

		title = _normalize_title(req.title)
		output_language = _normalize_output_language(req.outputLanguage)
		# Avoid extra work for duplicates: if project already has a result, we will block the job
		# and let the user decide to view existing output or reanalyze.
		if existing_result_id is None:
			# For new/unanalyzed projects, try to infer a title.
			if title is None and existing is not None:
				title = _normalize_title(getattr(existing, "title", None))
			if title is None:
				timeout_s = float(max(1, _env_int("YTDLP_TITLE_TIMEOUT_S", 8)))
				# Avoid blocking the event loop with subprocess.
				title = await asyncio.to_thread(fetch_video_title, url=req.sourceUrl, timeout_s=timeout_s)

		if existing is None:
			project = Project(
				project_id=project_id,
				title=title,
				source_type=source_type,
				source_url=canonical_url,
				source_path=None,
				duration_ms=None,
				format=None,
				latest_result_id=None,
				created_at_ms=now_ms,
				updated_at_ms=now_ms,
			)
			session.add(project)
		else:
			# Keep stored URL canonical and fill missing title opportunistically.
			changed = False
			if isinstance(canonical_url, str) and canonical_url and existing.source_url != canonical_url:
				existing.source_url = canonical_url
				changed = True
			if (not _normalize_title(existing.title)) and title is not None:
				existing.title = title
				changed = True
			if changed:
				existing.updated_at_ms = now_ms
				session.add(existing)

		# Duplicate guard: if we already have a renderable result, create a blocked job and let the
		# frontend ask the user whether to view it or reanalyze.
		if existing is not None and existing_result_id is not None:
			job = Job(
				job_id=job_id,
				project_id=project_id,
				type="analyze_video",
				status="blocked",
				stage="ingest",
				progress=None,
				error={
					"message": "Project already analyzed",
					"details": {
						"reason": "already_analyzed",
						"latestResultId": existing_result_id,
						"sourceType": source_type,
						"canonicalUrl": canonical_url,
					},
				},
				attempt=0,
				output_language=output_language,
				llm_mode=llm_mode,
				created_at_ms=now_ms,
				updated_at_ms=now_ms,
			)
			session.add(job)
			session.commit()
			GLOBAL_JOB_EVENT_BUS.emit_state(job_id=job_id, project_id=project_id, stage=job.stage, message="status=blocked")
			return JobCreatedDTO(jobId=job_id, projectId=project_id, status="blocked", createdAtMs=now_ms)

		job = Job(
			job_id=job_id,
			project_id=project_id,
			type="analyze_video",
			status="queued",
			stage="ingest",
			progress=None,
			error=None,
			attempt=0,
			output_language=output_language,
			llm_mode=llm_mode,
			created_at_ms=now_ms,
			updated_at_ms=now_ms,
		)
		session.add(job)
		session.commit()

		GLOBAL_JOB_EVENT_BUS.emit_state(job_id=job_id, project_id=project_id, stage=job.stage, message="status=queued")

		return JobCreatedDTO(jobId=job_id, projectId=project_id, status="queued", createdAtMs=now_ms)

	if content_type.startswith("multipart/form-data"):
		form = await request.form()
		source_type = str(form.get("sourceType") or "").strip().lower()
		llm_mode = str(form.get("llmMode") or "").strip().lower() or "backend"
		if llm_mode not in {"backend", "external"}:
			return JSONResponse(
				status_code=400,
				content=build_error_envelope(
					code=ErrorCode.VALIDATION_ERROR,
					message="Invalid llmMode",
					details={"llmMode": llm_mode},
					request_id=getattr(request.state, "request_id", None),
				),
			)
		if source_type != _UPLOAD_SOURCE_TYPE:
			return JSONResponse(
				status_code=400,
				content=build_error_envelope(
					code=ErrorCode.UNSUPPORTED_SOURCE_TYPE,
					message="Unsupported sourceType",
					details={"sourceType": source_type},
					request_id=getattr(request.state, "request_id", None),
				),
			)

		file = form.get("file")
		if not isinstance(file, UploadFile):
			return JSONResponse(
				status_code=400,
				content=build_error_envelope(
					code=ErrorCode.VALIDATION_ERROR,
					message="Missing file",
					request_id=getattr(request.state, "request_id", None),
				),
			)

		if not _is_supported_upload_filename(file.filename):
			return JSONResponse(
				status_code=400,
				content=build_error_envelope(
					code=ErrorCode.VALIDATION_ERROR,
					message="Unsupported file type",
					details={"filename": file.filename},
					request_id=getattr(request.state, "request_id", None),
				),
			)

		if llm_mode != "external":
			preflight = await _llm_preflight_or_error(request, session)
			if preflight is not None:
				return preflight

		now_ms = _now_ms()
		project_id = str(uuid.uuid4())
		job_id = str(uuid.uuid4())

		abs_path, rel_path = allocate_upload_path(project_id=project_id, job_id=job_id, original_filename=file.filename)
		max_bytes = _max_upload_bytes()
		size = 0
		try:
			with abs_path.open("wb") as out:
				while True:
					chunk = await file.read(1024 * 1024)
					if not chunk:
						break
					size += len(chunk)
					if size > max_bytes:
						raise MetadataError("file_unreadable", "File too large")
					out.write(chunk)
		finally:
			await file.close()

		try:
			meta = extract_video_metadata(abs_path)
		except MetadataError as e:
			try:
				abs_path.unlink(missing_ok=True)
			except Exception:
				pass

			code = ErrorCode.VALIDATION_ERROR
			if e.kind == "dependency_missing":
				code = ErrorCode.FFMPEG_MISSING
			return JSONResponse(
				status_code=400,
				content=build_error_envelope(
					code=code,
					message="Video metadata extraction failed",
					details={"reason": e.kind},
					request_id=getattr(request.state, "request_id", None),
				),
			)

		title_raw = form.get("title")
		title = _normalize_title(str(title_raw)) if title_raw not in (None, "") else None
		if title is None and file.filename:
			try:
				title = Path(str(file.filename)).stem.strip() or None
			except Exception:
				title = None

		project = Project(
			project_id=project_id,
			title=title,
			source_type=_UPLOAD_SOURCE_TYPE,
			source_url=None,
			source_path=rel_path,
			duration_ms=meta.duration_ms,
			format=meta.format,
			latest_result_id=None,
			created_at_ms=now_ms,
			updated_at_ms=now_ms,
		)
		job = Job(
			job_id=job_id,
			project_id=project_id,
			type="analyze_video",
			status="queued",
			stage="ingest",
			progress=None,
			error=None,
			attempt=0,
			output_language=_normalize_output_language(str(form.get("outputLanguage") or "")),
			llm_mode=llm_mode,
			created_at_ms=now_ms,
			updated_at_ms=now_ms,
		)
		session.add(project)
		session.add(job)
		session.commit()

		GLOBAL_JOB_EVENT_BUS.emit_state(job_id=job_id, project_id=project_id, stage=job.stage, message="status=queued")
		return JobCreatedDTO(jobId=job_id, projectId=project_id, status="queued", createdAtMs=now_ms)

	return JSONResponse(
		status_code=415,
		content=build_error_envelope(
			code=ErrorCode.VALIDATION_ERROR,
			message="Unsupported Content-Type",
			details={"contentType": request.headers.get("content-type")},
			request_id=getattr(request.state, "request_id", None),
		),
	)


def _safe_public_stage(value: str | None) -> PublicStage:
	if not value:
		return PublicStage.INGEST
	try:
		return to_public_stage(value)
	except ValueError:
		return PublicStage.INGEST


def _safe_progress(value: float | int | None) -> float | None:
	try:
		return normalize_progress(value)
	except (TypeError, ValueError):
		return None


def _now_ms() -> int:
	return int(time.time() * 1000)


@router.get("/jobs/{jobId}", response_model=JobDTO)
def get_job(jobId: str, request: Request, session: Session = Depends(get_db_session)):
	try:
		uuid.UUID(jobId)
	except ValueError:
		return JSONResponse(
			status_code=400,
			content=build_error_envelope(
				code=ErrorCode.VALIDATION_ERROR,
				message="Invalid jobId",
				details={"jobId": jobId},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	job = get_job_by_id(session, jobId)
	if job is None:
		return JSONResponse(
			status_code=404,
			content=build_error_envelope(
				code=ErrorCode.JOB_NOT_FOUND,
				message="Job does not exist",
				details={"jobId": jobId},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	return JobDTO(
		jobId=job.job_id,
		projectId=job.project_id,
		type=job.type,
		status=job.status,
		stage=_safe_public_stage(job.stage),
		progress=_safe_progress(job.progress),
		error=job.error,
		updatedAtMs=job.updated_at_ms,
	)


@router.get("/jobs/{jobId}/plan-request")
def get_job_plan_request(jobId: str, request: Request, session: Session = Depends(get_db_session)):
	"""Return the prompt/messages payload for external plan generation.

	This is used when a job is created with llmMode=external.
	"""

	try:
		uuid.UUID(jobId)
	except ValueError:
		return JSONResponse(
			status_code=400,
			content=build_error_envelope(
				code=ErrorCode.VALIDATION_ERROR,
				message="Invalid jobId",
				details={"jobId": jobId},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	job = get_job_by_id(session, jobId)
	if job is None:
		return JSONResponse(
			status_code=404,
			content=build_error_envelope(
				code=ErrorCode.JOB_NOT_FOUND,
				message="Job does not exist",
				details={"jobId": jobId},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	llm_mode = (getattr(job, "llm_mode", None) or "backend").strip().lower()
	if llm_mode != "external":
		return JSONResponse(
			status_code=400,
			content=build_error_envelope(
				code=ErrorCode.VALIDATION_ERROR,
				message="Job is not configured for external LLM",
				details={"llmMode": llm_mode},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	if job.transcript is None:
		return JSONResponse(
			status_code=409,
			content=build_error_envelope(
				code=ErrorCode.VALIDATION_ERROR,
				message="Transcript not ready",
				details={"reason": "transcript_not_ready"},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	plan_request = build_plan_request(transcript=job.transcript or {}, output_language=getattr(job, "output_language", None))
	return {
		"jobId": job.job_id,
		"projectId": job.project_id,
		"llmMode": "external",
		"planRequest": plan_request,
		"submitUrl": f"/api/v1/jobs/{job.job_id}/plan",
	}


@router.post("/jobs/{jobId}/plan")
async def submit_job_plan(jobId: str, request: Request, session: Session = Depends(get_db_session)):
	"""Submit an externally generated plan JSON for a blocked job."""

	try:
		uuid.UUID(jobId)
	except ValueError:
		return JSONResponse(
			status_code=400,
			content=build_error_envelope(
				code=ErrorCode.VALIDATION_ERROR,
				message="Invalid jobId",
				details={"jobId": jobId},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	job = get_job_by_id(session, jobId)
	if job is None:
		return JSONResponse(
			status_code=404,
			content=build_error_envelope(
				code=ErrorCode.JOB_NOT_FOUND,
				message="Job does not exist",
				details={"jobId": jobId},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	llm_mode = (getattr(job, "llm_mode", None) or "backend").strip().lower()
	if llm_mode != "external":
		return JSONResponse(
			status_code=400,
			content=build_error_envelope(
				code=ErrorCode.VALIDATION_ERROR,
				message="Job is not configured for external LLM",
				details={"llmMode": llm_mode},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	if job.status == "running":
		return JSONResponse(
			status_code=409,
			content=build_error_envelope(
				code=ErrorCode.VALIDATION_ERROR,
				message="Job is running; cannot accept external plan right now",
				details={"status": job.status},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	content_type = (request.headers.get("content-type") or "").lower()
	if not content_type.startswith("application/json"):
		return JSONResponse(
			status_code=415,
			content=build_error_envelope(
				code=ErrorCode.VALIDATION_ERROR,
				message="Unsupported Content-Type",
				details={"contentType": request.headers.get("content-type")},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	try:
		payload = await request.json()
	except Exception:
		return JSONResponse(
			status_code=400,
			content=build_error_envelope(
				code=ErrorCode.VALIDATION_ERROR,
				message="Invalid JSON body",
				request_id=getattr(request.state, "request_id", None),
			),
		)

	if not isinstance(payload, dict):
		return JSONResponse(
			status_code=400,
			content=build_error_envelope(
				code=ErrorCode.VALIDATION_ERROR,
				message="Invalid plan payload",
				details={"reason": "plan_not_object"},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	try:
		normalized = validate_plan(payload)
	except Exception as e:
		return JSONResponse(
			status_code=400,
			content=build_error_envelope(
				code=ErrorCode.VALIDATION_ERROR,
				message="Invalid plan",
				details={"reason": "invalid_plan", "error": str(e)},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	now_ms = _now_ms()
	job.external_plan = normalized
	job.status = "queued"
	job.stage = "plan"
	job.progress = max(job.progress or 0.0, 0.6)
	job.error = None
	job.claimed_by = None
	job.claim_token = None
	job.lease_expires_at_ms = None
	job.updated_at_ms = now_ms
	session.add(job)
	session.commit()

	# Best-effort notify watchers.
	try:
		GLOBAL_JOB_EVENT_BUS.emit_state(job_id=job.job_id, project_id=job.project_id, stage="plan", message="plan=submitted")
		GLOBAL_JOB_EVENT_BUS.emit_state(job_id=job.job_id, project_id=job.project_id, stage="plan", message="status=queued")
		GLOBAL_JOB_EVENT_BUS.emit_progress(job_id=job.job_id, project_id=job.project_id, stage="plan", progress=float(job.progress or 0.6), message="progress=0.6")
	except Exception:
		pass

	return {"jobId": job.job_id, "status": job.status}


@router.get("/jobs/{jobId}/logs", response_model=JobLogsPageDTO)
def get_job_logs(
	jobId: str,
	request: Request,
	limit: int = 200,
	cursor: str | None = None,
	session: Session = Depends(get_db_session),
):
	if limit < 1 or limit > 500:
		return JSONResponse(
			status_code=400,
			content=build_error_envelope(
				code=ErrorCode.VALIDATION_ERROR,
				message="Invalid limit",
				details={"limit": limit},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	try:
		uuid.UUID(jobId)
	except ValueError:
		return JSONResponse(
			status_code=400,
			content=build_error_envelope(
				code=ErrorCode.VALIDATION_ERROR,
				message="Invalid jobId",
				details={"jobId": jobId},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	job = get_job_by_id(session, jobId)
	if job is None:
		return JSONResponse(
			status_code=404,
			content=build_error_envelope(
				code=ErrorCode.JOB_NOT_FOUND,
				message="Job does not exist",
				details={"jobId": jobId},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	try:
		page = read_job_logs_page(
			job_id=job.job_id,
			limit=limit,
			cursor=cursor,
			default_stage=job.stage,
		)
	except ValueError:
		return JSONResponse(
			status_code=400,
			content=build_error_envelope(
				code=ErrorCode.VALIDATION_ERROR,
				message="Invalid cursor",
				details={"cursor": cursor},
				request_id=getattr(request.state, "request_id", None),
			),
		)
	except RuntimeError:
		return JSONResponse(
			status_code=500,
			content=build_error_envelope(
				code=ErrorCode.JOB_LOGS_UNAVAILABLE,
				message="Job logs unavailable",
				details={"jobId": jobId},
				request_id=getattr(request.state, "request_id", None),
			),
		)
	return JobLogsPageDTO(
		items=[
			LogItemDTO(
				tsMs=item.ts_ms,
				level=item.level,
				message=item.message,
				stage=_safe_public_stage(item.stage),
			)
			for item in page.items
		],
		nextCursor=page.next_cursor,
	)


@router.post("/jobs/{jobId}/cancel")
def cancel_job(jobId: str, request: Request, session: Session = Depends(get_db_session)):
	try:
		uuid.UUID(jobId)
	except ValueError:
		return JSONResponse(
			status_code=400,
			content=build_error_envelope(
				code=ErrorCode.VALIDATION_ERROR,
				message="Invalid jobId",
				details={"jobId": jobId},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	job = get_job_by_id(session, jobId)
	if job is None:
		return JSONResponse(
			status_code=404,
			content=build_error_envelope(
				code=ErrorCode.JOB_NOT_FOUND,
				message="Job does not exist",
				details={"jobId": jobId},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	if job.status not in {"queued", "running", "blocked"}:
		return JSONResponse(
			status_code=409,
			content=build_error_envelope(
				code=ErrorCode.JOB_NOT_CANCELLABLE,
				message="Job is not cancellable in its current status",
				details={"jobId": jobId, "status": job.status},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	job.status = "canceled"
	job.claimed_by = None
	job.claim_token = None
	job.lease_expires_at_ms = None
	job.updated_at_ms = _now_ms()
	session.add(job)
	session.commit()

	GLOBAL_JOB_EVENT_BUS.emit_state(
		job_id=job.job_id,
		project_id=job.project_id,
		stage=job.stage,
		message="status=canceled",
	)

	return {"ok": True}


@router.post("/jobs/{jobId}/retry", response_model=JobDTO)
def retry_job(jobId: str, request: Request, session: Session = Depends(get_db_session)):
	try:
		uuid.UUID(jobId)
	except ValueError:
		return JSONResponse(
			status_code=400,
			content=build_error_envelope(
				code=ErrorCode.VALIDATION_ERROR,
				message="Invalid jobId",
				details={"jobId": jobId},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	job = get_job_by_id(session, jobId)
	if job is None:
		return JSONResponse(
			status_code=404,
			content=build_error_envelope(
				code=ErrorCode.JOB_NOT_FOUND,
				message="Job does not exist",
				details={"jobId": jobId},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	if job.status not in {"failed", "canceled", "blocked"}:
		return JSONResponse(
			status_code=409,
			content=build_error_envelope(
				code=ErrorCode.JOB_NOT_RETRIABLE,
				message="Job is not retriable in its current status",
				details={"jobId": jobId, "status": job.status},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	# Resume the same jobId to maximize artifact reuse (downloads/chunk_summaries/etc.).
	now_ms = _now_ms()
	job.status = "queued"
	job.error = None
	job.claimed_by = None
	job.claim_token = None
	job.lease_expires_at_ms = None
	job.finished_at_ms = None
	job.updated_at_ms = now_ms
	# If this was an external-plan blocked job without a submitted plan, allow backend LLM to proceed.
	if (getattr(job, "llm_mode", None) or "backend").strip().lower() == "external" and not isinstance(getattr(job, "external_plan", None), dict):
		job.llm_mode = "backend"
		job.external_plan = None
		job.stage = "plan"
		job.progress = max(job.progress or 0.0, 0.6)
	session.add(job)
	session.commit()

	GLOBAL_JOB_EVENT_BUS.emit_state(
		job_id=job.job_id,
		project_id=job.project_id,
		stage=job.stage,
		message="status=queued",
	)

	return JobDTO(
		jobId=job.job_id,
		projectId=job.project_id,
		type=job.type,
		status=job.status,
		stage=_safe_public_stage(job.stage),
		progress=_safe_progress(job.progress),
		error=job.error,
		updatedAtMs=job.updated_at_ms,
	)


@router.post("/projects/{projectId}/jobs/resume", response_model=JobDTO)
def resume_project_job(projectId: str, request: Request, payload: ResumeProjectJobRequest | None = None, session: Session = Depends(get_db_session)):
	"""Resume a failed/canceled/blocked job for a project.

	This endpoint re-queues an existing job (same jobId) so the worker can
	reuse artifacts produced before the failure.
	"""

	# Validate projectId early (single-dir-name also aligns with DATA_DIR layout).
	try:
		validate_single_dir_name(projectId)
	except Exception:
		return JSONResponse(
			status_code=400,
			content=build_error_envelope(
				code=ErrorCode.VALIDATION_ERROR,
				message="Invalid projectId",
				details={"projectId": projectId},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	project = session.get(Project, projectId)
	if project is None:
		return JSONResponse(
			status_code=404,
			content=build_error_envelope(
				code=ErrorCode.PROJECT_NOT_FOUND,
				message="Project does not exist",
				details={"projectId": projectId},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	requested_job_id = None
	if payload is not None and isinstance(getattr(payload, "jobId", None), str) and payload.jobId:
		requested_job_id = payload.jobId

	job: Job | None = None
	if requested_job_id:
		try:
			uuid.UUID(requested_job_id)
		except ValueError:
			return JSONResponse(
				status_code=400,
				content=build_error_envelope(
					code=ErrorCode.VALIDATION_ERROR,
					message="Invalid jobId",
					details={"jobId": requested_job_id},
					request_id=getattr(request.state, "request_id", None),
				),
			)
		job = get_job_by_id(session, requested_job_id)
		if job is not None and job.project_id != projectId:
			job = None
	else:
		from sqlalchemy import select
		row = (
			session.execute(
				select(Job)
				.where(Job.project_id == projectId)
				.where(Job.status.in_(["failed", "canceled", "blocked"]))
				.order_by(Job.updated_at_ms.desc())
				.limit(1)
			)
			.scalars()
			.first()
		)
		job = row

	if job is None:
		return JSONResponse(
			status_code=404,
			content=build_error_envelope(
				code=ErrorCode.JOB_NOT_FOUND,
				message="No resumable job found for this project",
				details={"projectId": projectId, "jobId": requested_job_id},
				request_id=getattr(request.state, "request_id", None),
			),
		)

	# Best-effort: if we have a persisted Result snapshot, recover plan into external_plan so resume can
	# skip LLM plan generation (useful when failure happened in keyframes/assemble_result).
	try:
		if not isinstance(getattr(job, "external_plan", None), dict) and isinstance(getattr(project, "latest_result_id", None), str):
			result = session.get(Result, project.latest_result_id)
			if result is not None:
				plan_candidate = {
					"schemaVersion": getattr(result, "schema_version", None) or "2026-02-06",
					"contentBlocks": getattr(result, "content_blocks", None) or [],
					"mindmap": getattr(result, "mindmap", None) or {"nodes": [], "edges": []},
				}
				job.external_plan = validate_plan(plan_candidate)
				job.llm_mode = "external"
	except Exception:
		# Ignore plan recovery failures; worker can regenerate if needed.
		pass

	now_ms = _now_ms()
	job.status = "queued"
	job.error = None
	job.claimed_by = None
	job.claim_token = None
	job.lease_expires_at_ms = None
	job.finished_at_ms = None
	job.updated_at_ms = now_ms

	# If this was a blocked external-plan job with no plan, allow backend to proceed.
	if (getattr(job, "llm_mode", None) or "backend").strip().lower() == "external" and not isinstance(getattr(job, "external_plan", None), dict):
		job.llm_mode = "backend"
		job.external_plan = None
		job.stage = "plan"
		job.progress = max(job.progress or 0.0, 0.6)

	session.add(job)
	session.commit()

	GLOBAL_JOB_EVENT_BUS.emit_state(
		job_id=job.job_id,
		project_id=job.project_id,
		stage=job.stage,
		message="status=queued",
	)

	return JobDTO(
		jobId=job.job_id,
		projectId=job.project_id,
		type=job.type,
		status=job.status,
		stage=_safe_public_stage(job.stage),
		progress=_safe_progress(job.progress),
		error=job.error,
		updatedAtMs=job.updated_at_ms,
	)
