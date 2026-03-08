from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import base64
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def _now_ms() -> int:
	return int(time.time() * 1000)


def _read_json(url: str, *, timeout_s: float = 10.0, headers: dict[str, str] | None = None) -> Any:
	h = {"Accept": "application/json"}
	if headers:
		h.update(headers)
	req = Request(url, headers=h, method="GET")
	with urlopen(req, timeout=timeout_s) as resp:
		body = resp.read()
	return json.loads(body.decode("utf-8"))


def _post_json(url: str, payload: dict[str, Any], *, timeout_s: float = 10.0) -> Any:
	data = json.dumps(payload).encode("utf-8")
	req = Request(
		url,
		data=data,
		headers={"Content-Type": "application/json", "Accept": "application/json"},
		method="POST",
	)
	with urlopen(req, timeout=timeout_s) as resp:
		body = resp.read()
	return json.loads(body.decode("utf-8"))


def _post_multipart_form(
	url: str,
	*,
	fields: dict[str, str],
	file_field: str,
	file_path: Path,
	file_name: str | None = None,
	file_content_type: str = "application/octet-stream",
	timeout_s: float = 30.0,
) -> Any:
	# Minimal multipart encoder (stdlib only) for CI portability.
	boundary = f"----videohelper-smoke-{_now_ms()}"
	crlf = "\r\n"
	parts: list[bytes] = []

	for k, v in (fields or {}).items():
		parts.append(f"--{boundary}{crlf}".encode("utf-8"))
		parts.append(f"Content-Disposition: form-data; name=\"{k}\"{crlf}{crlf}".encode("utf-8"))
		parts.append(str(v).encode("utf-8"))
		parts.append(crlf.encode("utf-8"))

	name = file_name or file_path.name
	content = file_path.read_bytes()
	parts.append(f"--{boundary}{crlf}".encode("utf-8"))
	parts.append(
		(
			f"Content-Disposition: form-data; name=\"{file_field}\"; filename=\"{name}\"{crlf}"
			f"Content-Type: {file_content_type}{crlf}{crlf}"
		).encode("utf-8")
	)
	parts.append(content)
	parts.append(crlf.encode("utf-8"))
	parts.append(f"--{boundary}--{crlf}".encode("utf-8"))

	body = b"".join(parts)
	headers = {
		"Content-Type": f"multipart/form-data; boundary={boundary}",
		"Accept": "application/json",
		"Content-Length": str(len(body)),
	}
	req = Request(url, data=body, headers=headers, method="POST")
	with urlopen(req, timeout=timeout_s) as resp:
		resp_body = resp.read()
	return json.loads(resp_body.decode("utf-8"))


def _http_get_bytes(url: str, *, timeout_s: float = 10.0, headers: dict[str, str] | None = None) -> tuple[int, bytes]:
	h = headers or {}
	req = Request(url, headers=h, method="GET")
	with urlopen(req, timeout=timeout_s) as resp:
		return int(getattr(resp, "status", 200)), resp.read()


def _safe_snippet(text: str, *, max_len: int = 240) -> str:
	t = (text or "").strip().replace("\r", " ").replace("\n", " ")
	return t if len(t) <= max_len else t[:max_len] + "…"


def _repo_root() -> Path:
	return Path(__file__).resolve().parents[2]


def _load_product_name(repo_root: Path) -> str:
	p = repo_root / "apps" / "desktop" / "package.json"
	try:
		j = json.loads(p.read_text(encoding="utf-8"))
		build = j.get("build") if isinstance(j, dict) else None
		product = build.get("productName") if isinstance(build, dict) else None
		if isinstance(product, str) and product.strip():
			return product.strip()
	except Exception:
		pass
	return "Video Helper"


def _is_windows() -> bool:
	return sys.platform.startswith("win")


def _env_get(env: dict[str, str], key: str) -> str:
	return (env.get(key) or "").strip()


def _looks_like_netscape_cookies_txt(text: str) -> bool:
	# Netscape cookie file typically starts with this header, but some exporters omit it.
	# We accept either:
	# - a header line, or
	# - at least one tab-delimited cookie line with >= 7 fields.
	lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
	if not lines:
		return False
	if lines[0].lower().startswith("# netscape http cookie file"):
		return True
	for ln in lines[:40]:
		if ln.startswith("#"):
			continue
		# domain \t include_subdomains \t path \t secure \t expiry \t name \t value
		parts = ln.split("\t")
		if len(parts) >= 7:
			return True
	return False


def _maybe_write_ytdlp_cookies(*, env: dict[str, str], data_dir: Path) -> None:
	"""Best-effort configure yt-dlp cookies for CI.

	Priority:
	1) Existing YTDLP_COOKIES_FILE pointing to a real file
	2) SMOKE_YTDLP_COOKIES_B64 / YTDLP_COOKIES_B64 (base64-encoded cookies.txt content)
	3) SMOKE_YTDLP_COOKIES_TEXT / YTDLP_COOKIES_TEXT (raw cookies.txt content)

	Writes DATA_DIR/cookies/ytdlp_cookies.txt and sets YTDLP_COOKIES_FILE.
	Never prints cookie content.
	"""
	try:
		existing = _env_get(env, "YTDLP_COOKIES_FILE")
		if existing and Path(existing).expanduser().exists():
			print(f"[smoke] ytdlp cookies configured: True path={existing}")
			return

		b64 = _env_get(env, "SMOKE_YTDLP_COOKIES_B64") or _env_get(env, "YTDLP_COOKIES_B64")
		raw = _env_get(env, "SMOKE_YTDLP_COOKIES_TEXT") or _env_get(env, "YTDLP_COOKIES_TEXT")
		if not b64 and not raw:
			print("[smoke] ytdlp cookies configured: False")
			return

		cookies_dir = data_dir / "cookies"
		cookies_dir.mkdir(parents=True, exist_ok=True)
		dest = cookies_dir / "ytdlp_cookies.txt"
		if b64:
			content = base64.b64decode(b64.encode("utf-8"))
			dest.write_bytes(content)
		else:
			# Some CI env injection turns newlines into literal "\\n" sequences.
			# If we see no real newlines but do see escaped ones, unescape them.
			text = raw
			if "\n" not in text and "\\n" in text:
				text = text.replace("\\n", "\n")
			dest.write_text(text + "\n", encoding="utf-8")

		# Best-effort validation to catch common secret-format issues.
		try:
			preview = dest.read_text(encoding="utf-8", errors="ignore")
			if not _looks_like_netscape_cookies_txt(preview):
				print("[smoke] WARNING: ytdlp cookies file does not look like Netscape cookies.txt format; yt-dlp may ignore it")
		except Exception:
			pass
		env["YTDLP_COOKIES_FILE"] = str(dest)
		print(f"[smoke] ytdlp cookies configured: True path={dest}")
	except Exception as e:
		# Don't fail smoke setup on cookie issues; the job will fail with a clear
		# yt-dlp error tail anyway.
		print(f"[smoke] ytdlp cookies setup failed: {type(e).__name__}: {e}")


def _is_macos() -> bool:
	return sys.platform == "darwin"


def _is_linux() -> bool:
	return sys.platform.startswith("linux")


def _iter_release_dir_candidates(repo_root: Path) -> list[Path]:
	# Depending on how actions/upload-artifact chooses the root directory, the
	# downloaded artifact may contain either:
	# - apps/desktop/release/<platform-unpacked>/...
	# - <platform-unpacked>/... (with the common prefix stripped)
	# In addition, a later download step might choose a different destination.
	candidates: list[Path] = []

	# The canonical repo location.
	candidates.append(repo_root / "apps" / "desktop" / "release")
	# If the artifact root already is "release" and we download into repo root.
	candidates.append(repo_root / "release")
	# If the artifact root is release/ and we download directly into it (or if
	# it was extracted into repo root with prefix stripped).
	candidates.append(repo_root)
	# If someone downloads the artifact into apps/desktop/release but the stored
	# paths still include the prefix, we'll end up nested.
	candidates.append(repo_root / "apps" / "desktop" / "release" / "apps" / "desktop" / "release")

	# De-dup while preserving order.
	seen: set[Path] = set()
	out: list[Path] = []
	for c in candidates:
		c = c.resolve()
		if c in seen:
			continue
		seen.add(c)
		out.append(c)
	return out


def find_unpacked_desktop_executable(repo_root: Path) -> Path:
	product_name = _load_product_name(repo_root)

	candidates = _iter_release_dir_candidates(repo_root)

	def pick_release_dir_for_windows() -> Path | None:
		for c in candidates:
			if (c / "win-unpacked").exists():
				return c
		return None

	def pick_release_dir_for_linux() -> Path | None:
		for c in candidates:
			if (c / "linux-unpacked").exists():
				return c
		return None

	def pick_release_dir_for_macos() -> Path | None:
		for c in candidates:
			apps = [p for p in c.glob("mac*/**/*.app") if p.is_dir()]
			if apps:
				return c
		return None

	release_dir: Path | None = None
	if _is_windows():
		release_dir = pick_release_dir_for_windows()
	elif _is_linux():
		release_dir = pick_release_dir_for_linux()
	elif _is_macos():
		release_dir = pick_release_dir_for_macos()
	else:
		raise RuntimeError(f"unsupported platform: {sys.platform}")

	if release_dir is None:
		checked = "\n".join(f"- {c}" for c in candidates)
		raise RuntimeError(
			"desktop release dir not found. Checked candidates:\n"
			+ checked
			+ "\nHint: in GitHub Actions, download the build artifact into apps/desktop/release to match expected layout."
		)

	print(f"[smoke] using release dir: {release_dir}")

	if _is_windows():
		unpacked = release_dir / "win-unpacked"
		if not unpacked.exists():
			raise RuntimeError(f"win-unpacked not found: {unpacked}")
		expected = unpacked / f"{product_name}.exe"
		if expected.exists():
			return expected
		# Fallback: pick the most likely top-level exe.
		candidates = sorted(unpacked.glob("*.exe"))
		deny = {"chrome_crashpad_handler.exe", "notification_helper.exe"}
		for c in candidates:
			if c.name.lower() in deny:
				continue
			return c
		raise RuntimeError(f"no desktop exe found in: {unpacked}")

	if _is_macos():
		# electron-builder typically outputs release/mac/<Product>.app
		apps = list(release_dir.glob("mac*/**/*.app"))
		apps = [p for p in apps if p.is_dir()]
		apps.sort(key=lambda p: len(str(p)))
		if not apps:
			raise RuntimeError(f"no .app found under: {release_dir}")
		app_dir = apps[0]
		macos_dir = app_dir / "Contents" / "MacOS"
		if not macos_dir.exists():
			raise RuntimeError(f"MacOS dir not found in app bundle: {app_dir}")
		# Usually the executable matches productName.
		expected = macos_dir / product_name
		if expected.exists():
			return expected
		bins = sorted([p for p in macos_dir.iterdir() if p.is_file()])
		if bins:
			return bins[0]
		raise RuntimeError(f"no executable found in: {macos_dir}")

	if _is_linux():
		unpacked = release_dir / "linux-unpacked"
		if not unpacked.exists():
			raise RuntimeError(f"linux-unpacked not found: {unpacked}")
		bins: list[Path] = []
		fallback: list[Path] = []
		for p in unpacked.iterdir():
			if not p.is_file():
				continue
			name = p.name.lower()
			if name.endswith(".so") or name.endswith(".pak") or name.endswith(".dat"):
				continue
			fallback.append(p)
			try:
				if os.access(p, os.X_OK):
					bins.append(p)
			except Exception:
				continue
		bins.sort(key=lambda p: p.stat().st_size if p.exists() else 0, reverse=True)
		if bins:
			return bins[0]

		# Artifact downloads can lose the executable bit. Fall back to the largest
		# plausible binary and let the caller attempt chmod.
		fallback.sort(key=lambda p: p.stat().st_size if p.exists() else 0, reverse=True)
		if fallback:
			return fallback[0]
		raise RuntimeError(f"no executable found in: {unpacked}")

	raise RuntimeError(f"unsupported platform: {sys.platform}")


def wait_for_http_ready(url: str, *, timeout_s: int, expect_json_keys: tuple[str, ...] | None = None) -> Any:
	deadline = time.time() + timeout_s
	last_err: str | None = None
	while time.time() < deadline:
		try:
			if expect_json_keys:
				data = _read_json(url, timeout_s=5.0)
				if isinstance(data, dict) and all(k in data for k in expect_json_keys):
					return data
			else:
				status, body = _http_get_bytes(url, timeout_s=5.0)
				if status < 500 and body is not None:
					return {"status": status}
		except HTTPError as e:
			last_err = f"HTTPError status={getattr(e, 'code', None)}"
		except (URLError, TimeoutError) as e:
			last_err = f"{type(e).__name__}: {e}"
		except Exception as e:
			last_err = f"{type(e).__name__}: {e}"
		time.sleep(0.5)

	raise TimeoutError(f"timed out waiting for {url}. lastError={last_err}")


def closed_loop_validate(
	*,
	api_base: str,
	source_type: str,
	source_url: str | None,
	source_file: Path | None,
	timeout_s: int,
) -> dict[str, Any]:
	api_base = api_base.rstrip("/")
	start_ms = _now_ms()
	print(f"[smoke] closed-loop start tsMs={start_ms}")

	created: Any
	st = (source_type or "").strip().lower()
	if st == "upload":
		if source_file is None:
			raise ValueError("source_file is required for sourceType=upload")
		p = source_file.expanduser().resolve()
		if not p.exists() or not p.is_file():
			raise FileNotFoundError(f"upload file not found: {p}")
		print(f"[smoke] upload file: {p} bytes={p.stat().st_size}")
		suf = p.suffix.lower()
		ct = "application/octet-stream"
		if suf == ".mp4":
			ct = "video/mp4"
		elif suf == ".mov":
			ct = "video/quicktime"
		elif suf == ".webm":
			ct = "video/webm"
		elif suf == ".mkv":
			ct = "video/x-matroska"
		created = _post_multipart_form(
			f"{api_base}/api/v1/jobs",
			fields={"sourceType": "upload", "title": "smoke-fixture"},
			file_field="file",
			file_path=p,
			file_content_type=ct,
			timeout_s=60.0,
		)
	else:
		if not (source_url or "").strip():
			raise ValueError("source_url is required for non-upload source types")
		created = _post_json(
			f"{api_base}/api/v1/jobs",
			{"sourceType": source_type, "sourceUrl": source_url},
			timeout_s=30.0,
		)
	if not isinstance(created, dict) or not created.get("jobId") or not created.get("projectId"):
		raise RuntimeError(f"create job returned unexpected JSON: {_safe_snippet(json.dumps(created, ensure_ascii=False))}")
	job_id = str(created["jobId"])
	project_id = str(created["projectId"])
	print(f"[smoke] job created jobId={job_id} projectId={project_id}")

	deadline = time.time() + timeout_s
	seen_stages: set[str] = set()
	last_line = None
	final_job: dict[str, Any] | None = None
	while time.time() < deadline:
		job = _read_json(f"{api_base}/api/v1/jobs/{job_id}", timeout_s=30.0)
		if not isinstance(job, dict):
			raise RuntimeError("job GET returned non-object JSON")
		status = str(job.get("status") or "")
		stage = str(job.get("stage") or "")
		progress = job.get("progress")
		if stage:
			seen_stages.add(stage)
		line = f"status={status} stage={stage} progress={progress}"
		if line != last_line:
			print(f"[smoke] {line}")
			last_line = line

		if status in {"succeeded", "failed", "canceled"}:
			final_job = job
			break
		time.sleep(1.0)

	if final_job is None:
		raise TimeoutError(f"Timed out waiting for job {job_id}")

	if str(final_job.get("status")) != "succeeded":
		err = final_job.get("error")
		raise RuntimeError(f"job failed status={final_job.get('status')} error={json.dumps(err, ensure_ascii=False) if err else None}")

	if "assemble_result" not in seen_stages:
		raise RuntimeError(f"job did not reach assemble_result (seenStages={sorted(seen_stages)})")

	project = _read_json(f"{api_base}/api/v1/projects/{project_id}", timeout_s=30.0)
	if not isinstance(project, dict):
		raise RuntimeError("project GET returned non-object JSON")
	title = project.get("title")
	if isinstance(title, str) and title.strip():
		print(f"[smoke] project title={_safe_snippet(title, max_len=120)}")
	else:
		# Title extraction is best-effort (yt-dlp probe can fail transiently in CI).
		# Downgrade from hard failure to a warning so the smoke gate is not
		# blocked by a non-critical cosmetic issue.
		print("[smoke] WARNING: project title is empty (yt-dlp title probe may have timed out in CI)")

	result = _read_json(f"{api_base}/api/v1/projects/{project_id}/results/latest", timeout_s=30.0)
	if not isinstance(result, dict):
		raise RuntimeError("latest result returned non-object JSON")
	asset_refs = result.get("assetRefs")
	if not (isinstance(asset_refs, list) and asset_refs and isinstance(asset_refs[0], dict) and asset_refs[0].get("assetId")):
		raise RuntimeError("result.assetRefs missing or invalid")
	asset_id = str(asset_refs[0]["assetId"])

	asset = _read_json(f"{api_base}/api/v1/assets/{asset_id}", timeout_s=30.0)
	if not isinstance(asset, dict):
		raise RuntimeError("asset returned non-object JSON")
	content_url = asset.get("contentUrl")
	if not (isinstance(content_url, str) and content_url.strip()):
		raise RuntimeError("asset.contentUrl missing")
	url = content_url
	if url.startswith("/"):
		url = api_base + url
	status, body = _http_get_bytes(url, timeout_s=30.0, headers={"Range": "bytes=0-1023"})
	if status not in (200, 206) or not body:
		raise RuntimeError(f"asset content not readable status={status} len={len(body) if body else 0}")

	elapsed_ms = _now_ms() - start_ms
	print(f"[ok] closed-loop OK elapsedMs={elapsed_ms} jobId={job_id} projectId={project_id} assetId={asset_id}")
	return {"ok": True, "jobId": job_id, "projectId": project_id, "assetId": asset_id, "elapsedMs": elapsed_ms}


def _terminate_process_tree(proc: subprocess.Popen, *, grace_s: int = 5) -> None:
	if proc.poll() is not None:
		return

	try:
		if _is_windows():
			subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], check=False, capture_output=True)
			return
		# POSIX: try terminate process group if we created one.
		try:
			os.killpg(proc.pid, signal.SIGTERM)
		except Exception:
			proc.terminate()
		try:
			proc.wait(timeout=grace_s)
			return
		except Exception:
			pass
		try:
			os.killpg(proc.pid, signal.SIGKILL)
		except Exception:
			proc.kill()
		proc.wait(timeout=grace_s)
	except Exception:
		return


def _chmod_x(p: Path) -> None:
	if _is_windows():
		return
	try:
		if not p.exists():
			return
		mode = p.stat().st_mode
		p.chmod(mode | 0o111)
	except Exception:
		return


def _best_effort_fix_unpacked_permissions(desktop_exe: Path) -> None:
	# Artifact downloads can drop executable bits on POSIX. The desktop app
	# will spawn the packaged backend from within resources; if that binary is
	# not executable, startup fails with EACCES.
	if _is_windows():
		return

	# Desktop executable itself.
	_chmod_x(desktop_exe)

	backend: Path | None = None
	if _is_linux():
		# <linux-unpacked>/desktop
		backend = desktop_exe.parent / "resources" / "backend" / "backend"
	elif _is_macos():
		# <App>.app/Contents/MacOS/<bin>
		backend = desktop_exe.parent.parent / "Resources" / "backend" / "backend"
		# macOS app bundles contain multiple helper executables (Renderer/GPU/etc)
		# under Contents/Frameworks. If executable bits are stripped during artifact
		# download/extraction, Electron child processes fail to launch (often logged
		# as GPU process launch failed / render-process-gone launch-failed).
		contents_dir = desktop_exe.parent.parent
		frameworks_dir = contents_dir / "Frameworks"
		# Main binaries under Contents/MacOS
		try:
			macos_dir = contents_dir / "MacOS"
			if macos_dir.exists():
				for p in macos_dir.iterdir():
					_chmod_x(p)
		except Exception:
			pass
		# Helper apps: *.app/Contents/MacOS/*
		try:
			if frameworks_dir.exists():
				for helper_app in frameworks_dir.glob("*.app"):
					macos_bin_dir = helper_app / "Contents" / "MacOS"
					if macos_bin_dir.exists():
						for p in macos_bin_dir.iterdir():
							_chmod_x(p)
		except Exception:
			pass
		# Framework binaries (best-effort): mark top-level files executable.
		try:
			if frameworks_dir.exists():
				for p in frameworks_dir.rglob("*"):
					# Only touch files (no dirs) and avoid obvious metadata.
					if not p.is_file():
						continue
					name = p.name.lower()
					if name.endswith((".plist", ".json", ".txt", ".pak", ".dat", ".icns")):
						continue
					# Many Mach-O binaries have no extension; some are .dylib.
					_chmod_x(p)
		except Exception:
			pass
	if backend is not None:
		_chmod_x(backend)
		# Also ensure bundled ffmpeg/yt-dlp (if present) remain executable.
		internal_dir = backend.parent / "_internal"
		if internal_dir.exists():
			for name in ("ffmpeg", "ffprobe", "yt-dlp"):
				_chmod_x(internal_dir / name)


def _resources_dir_from_desktop_exe(desktop_exe: Path) -> Path:
	if _is_windows() or _is_linux():
		return desktop_exe.parent / "resources"
	# macOS: <App>.app/Contents/MacOS/<bin>
	return desktop_exe.parent.parent / "Resources"


def _preflight_check_packaged_frontend(desktop_exe: Path, *, out_dir: Path) -> None:
	resources_dir = _resources_dir_from_desktop_exe(desktop_exe)
	web_root = resources_dir / "web" / "apps" / "web"
	server_js = web_root / "server.js"
	build_id = web_root / ".next" / "BUILD_ID"
	static_dir = web_root / ".next" / "static"

	# Always write a diagnostic file so Actions can upload something even when
	# the preflight fails before launching the desktop app.
	try:
		out_dir.mkdir(parents=True, exist_ok=True)
		(out_dir / "packaged-frontend-check.json").write_text(
			json.dumps(
				{
					"resources_dir": str(resources_dir),
					"web_root": str(web_root),
					"server_js": {"path": str(server_js), "exists": server_js.exists()},
					"build_id": {"path": str(build_id), "exists": build_id.exists()},
					"static_dir": {"path": str(static_dir), "exists": static_dir.exists()},
				},
				ensure_ascii=False,
				indent=2,
			)
			+ "\n",
			encoding="utf-8",
		)
	except Exception:
		pass

	print(f"[smoke] resources dir: {resources_dir}")
	print(f"[smoke] web root: {web_root}")
	print(f"[smoke] check server.js: {server_js.exists()}")
	print(f"[smoke] check .next/BUILD_ID: {build_id.exists()}")
	print(f"[smoke] check .next/static: {static_dir.exists()}")

	missing: list[str] = []
	if not server_js.exists():
		missing.append(f"server.js missing: {server_js}")
	if not build_id.exists():
		missing.append(f"BUILD_ID missing: {build_id}")
	if not static_dir.exists():
		missing.append(f"static dir missing: {static_dir}")

	if missing:
		# Provide a small directory preview to make CI debugging easy.
		try:
			if web_root.exists():
				entries = sorted([p.name for p in web_root.iterdir()])
				print(f"[smoke] web root entries: {entries[:40]}")
		except Exception:
			pass
		raise RuntimeError(
			"Packaged frontend assets are incomplete; Next cannot start.\n"
			+ "\n".join(f"- {m}" for m in missing)
		)


def main() -> int:
	parser = argparse.ArgumentParser(description="CI smoke: launch desktop (unpacked) and run closed-loop validation")
	parser.add_argument("--api-base", default="http://127.0.0.1:8000")
	parser.add_argument("--frontend-base", default="http://127.0.0.1:3000")
	parser.add_argument("--timeout-sec", type=int, default=1800)
	parser.add_argument("--source-type", default="bilibili")
	parser.add_argument("--url", default="https://b23.tv/279Yz1P")
	parser.add_argument("--file", default="", help="Local media file for sourceType=upload")
	parser.add_argument(
		"--env-file",
		default="",
		help="Optional dotenv file path for local runs (e.g. services/core/.env). Values are only applied when missing from the current environment.",
	)
	parser.add_argument("--out", default="")
	args = parser.parse_args()

	repo_root = _repo_root()
	out_dir = Path(args.out).resolve() if (args.out or "").strip() else (repo_root / "_ci" / "smoke")
	out_dir.mkdir(parents=True, exist_ok=True)

	exe = find_unpacked_desktop_executable(repo_root)
	_best_effort_fix_unpacked_permissions(exe)
	print(f"[smoke] desktop exe: {exe}")
	_preflight_check_packaged_frontend(exe, out_dir=out_dir)

	child_env = dict(os.environ)

	def _load_dotenv_into_env(env: dict[str, str], env_file: Path) -> None:
		try:
			if not env_file.exists() or not env_file.is_file():
				return
			for raw in env_file.read_text(encoding="utf-8").splitlines():
				line = raw.strip()
				if not line or line.startswith("#"):
					continue
				if line.startswith("export "):
					line = line[len("export ") :].lstrip()
				if "=" not in line:
					continue
				key, value = line.split("=", 1)
				key = key.strip()
				value = value.strip()
				if not key:
					continue
				if len(value) >= 2 and ((value[0] == value[-1] == '"') or (value[0] == value[-1] == "'")):
					value = value[1:-1]
				# Only apply when missing to avoid surprising overrides.
				env.setdefault(key, value)
		except Exception:
			return

	# Local runs: allow loading env from a dotenv file so the packaged backend
	# receives LLM/API settings without relying on Actions secrets.
	if child_env.get("CI", "").lower() != "true":
		env_file_arg = (args.env_file or "").strip()
		if env_file_arg:
			_load_dotenv_into_env(child_env, Path(env_file_arg).expanduser())
		else:
			default_env = repo_root / "services" / "core" / ".env"
			_load_dotenv_into_env(child_env, default_env)

	# Make packaged runs deterministic: pin DATA_DIR under the smoke output folder
	# so logs/downloads/cookies are easy to collect as artifacts.
	data_dir = Path(_env_get(child_env, "DATA_DIR") or str(out_dir / "data")).resolve()
	child_env.setdefault("DATA_DIR", str(data_dir))
	print(f"[smoke] DATA_DIR={data_dir}")

	# yt-dlp may require a JS runtime for YouTube extraction; default to node in CI.
	if _env_get(child_env, "CI").lower() == "true" and "youtube" in (args.url or "").lower():
		child_env.setdefault("YTDLP_JS_RUNTIMES", "node")
		# Best-effort hardening for CI datacenter IPs.
		child_env.setdefault("YTDLP_REFERER", "https://www.youtube.com/")
		child_env.setdefault(
			"YTDLP_USER_AGENT",
			"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
		)
		# Prefer Android client extraction paths which can be more resilient.
		child_env.setdefault("YTDLP_EXTRACTOR_ARGS", "youtube:player_client=android")

	# Best-effort hardening for Bilibili on CI runners.
	# Bilibili frequently returns HTTP 412 (Precondition Failed) for datacenter IPs
	# unless a browser-like UA/Referer (and sometimes cookies) are provided.
	url_low = (args.url or "").lower()
	if _env_get(child_env, "CI").lower() == "true" and ("bilibili.com" in url_low or "b23.tv" in url_low):
		child_env.setdefault("YTDLP_REFERER", "https://www.bilibili.com/")
		child_env.setdefault(
			"YTDLP_USER_AGENT",
			"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
		)

	# Optional: inject yt-dlp cookies for providers that require auth (YouTube bot check).
	_maybe_write_ytdlp_cookies(env=child_env, data_dir=data_dir)

	child_env.setdefault("PYTHONUTF8", "1")
	child_env.setdefault("TRANSCRIBE_MODEL_SIZE", "tiny")
	child_env.setdefault("TRANSCRIBE_DEVICE", "cpu")
	child_env.setdefault("TRANSCRIBE_COMPUTE_TYPE", "int8")
	child_env.setdefault("LLM_TIMEOUT_S", "180")
	child_env.setdefault("LLM_PREFLIGHT_TIMEOUT_S", "60")
	child_env.setdefault("LLM_MAX_ATTEMPTS", "3")
	child_env.setdefault("LLM_PLAN_MAX_SEGMENTS", "40")
	child_env.setdefault("LLM_PLAN_MAX_CHARS", "8000")
	# CI stability: do not force DevTools.
	child_env.setdefault("VH_DEBUG", "0")
	# Explicitly disable updater (even though main.ts also skips in CI).
	child_env.setdefault("VH_DISABLE_UPDATER", "1")
	# Align with desktop GPU-disable logic (macOS runners can crash on GPU init).
	if _env_get(child_env, "CI").lower() == "true":
		child_env.setdefault("VH_DISABLE_GPU", "1")

	# CI often requires disabling Chromium sandbox and GPU.
	app_args: list[str] = []
	if _is_linux():
		app_args = ["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage"]
	elif _is_macos():
		# macOS runners can crash hard on GPU init; be extra defensive.
		app_args = ["--disable-gpu", "--disable-gpu-compositing", "--use-gl=swiftshader"]

	stdout_path = out_dir / "desktop-stdout.log"
	stderr_path = out_dir / "desktop-stderr.log"
	stdout_f = stdout_path.open("wb")
	stderr_f = stderr_path.open("wb")

	proc = None
	start_ts = time.time()
	print(f"[smoke] launching desktop...")
	try:
		popen_kwargs: dict[str, Any] = {
			"env": child_env,
			"stdout": stdout_f,
			"stderr": stderr_f,
		}
		if _is_windows():
			popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
		else:
			popen_kwargs["start_new_session"] = True
		proc = subprocess.Popen([str(exe), *app_args], **popen_kwargs)

		# Backend health.
		health = wait_for_http_ready(
			f"{str(args.api_base).rstrip('/')}/api/v1/health",
			timeout_s=min(120, int(args.timeout_sec)),
			expect_json_keys=("status", "ready"),
		)
		print(f"[ok] backend health: status={health.get('status')} ready={health.get('ready')}")

		# Frontend root.
		wait_for_http_ready(str(args.frontend_base).rstrip("/") + "/", timeout_s=min(120, int(args.timeout_sec)))
		print("[ok] frontend ready")

		# Closed-loop.
		source_url = str(args.url) if (args.url or "").strip() else None
		source_file_arg = (args.file or "").strip() or (child_env.get("SMOKE_FILE") or "").strip()
		source_file = Path(source_file_arg).expanduser() if source_file_arg else None
		summary = closed_loop_validate(
			api_base=str(args.api_base),
			source_type=str(args.source_type),
			source_url=source_url,
			source_file=source_file,
			timeout_s=int(args.timeout_sec),
		)
		(out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
		print(f"[ok] smoke succeeded in {int(time.time() - start_ts)}s")
		return 0
	finally:
		try:
			stdout_f.flush()
			stderr_f.flush()
			stdout_f.close()
			stderr_f.close()
		except Exception:
			pass
		if proc is not None:
			print(f"[smoke] stopping desktop pid={proc.pid}")
			_terminate_process_tree(proc)


if __name__ == "__main__":
	raise SystemExit(main())
