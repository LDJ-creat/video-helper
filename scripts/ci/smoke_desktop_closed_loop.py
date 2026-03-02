from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
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


def closed_loop_validate(*, api_base: str, source_type: str, source_url: str, timeout_s: int) -> dict[str, Any]:
	api_base = api_base.rstrip("/")
	start_ms = _now_ms()
	print(f"[smoke] closed-loop start tsMs={start_ms}")

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
	if not (isinstance(title, str) and title.strip()):
		raise RuntimeError("project title is empty (expected auto-title from video name)")
	print(f"[smoke] project title={_safe_snippet(title, max_len=120)}")

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
	if backend is not None:
		_chmod_x(backend)
		# Also ensure bundled ffmpeg/yt-dlp (if present) remain executable.
		internal_dir = backend.parent / "_internal"
		if internal_dir.exists():
			for name in ("ffmpeg", "ffprobe", "yt-dlp"):
				_chmod_x(internal_dir / name)


def main() -> int:
	parser = argparse.ArgumentParser(description="CI smoke: launch desktop (unpacked) and run closed-loop validation")
	parser.add_argument("--api-base", default="http://127.0.0.1:8000")
	parser.add_argument("--frontend-base", default="http://127.0.0.1:3000")
	parser.add_argument("--timeout-sec", type=int, default=1800)
	parser.add_argument("--source-type", default="youtube")
	parser.add_argument("--url", default="https://www.youtube.com/watch?v=uN6r-rWLACc")
	parser.add_argument("--out", default="")
	args = parser.parse_args()

	repo_root = _repo_root()
	out_dir = Path(args.out).resolve() if (args.out or "").strip() else (repo_root / "_ci" / "smoke")
	out_dir.mkdir(parents=True, exist_ok=True)

	exe = find_unpacked_desktop_executable(repo_root)
	_best_effort_fix_unpacked_permissions(exe)
	print(f"[smoke] desktop exe: {exe}")

	child_env = dict(os.environ)
	child_env.setdefault("PYTHONUTF8", "1")
	child_env.setdefault("TRANSCRIBE_MODEL_SIZE", "tiny")
	child_env.setdefault("TRANSCRIBE_DEVICE", "cpu")
	child_env.setdefault("TRANSCRIBE_COMPUTE_TYPE", "int8")
	child_env.setdefault("LLM_TIMEOUT_S", "180")
	child_env.setdefault("LLM_PREFLIGHT_TIMEOUT_S", "60")
	child_env.setdefault("LLM_MAX_ATTEMPTS", "3")
	child_env.setdefault("LLM_PLAN_MAX_SEGMENTS", "40")
	child_env.setdefault("LLM_PLAN_MAX_CHARS", "8000")
	# Keep desktop stable in CI.
	child_env.setdefault("VH_DEBUG", "1")

	# Linux CI often requires disabling Chromium sandbox.
	app_args: list[str] = []
	if _is_linux():
		# On headless runners, GPU init frequently fails; disable it.
		app_args = ["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage"]

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
		summary = closed_loop_validate(
			api_base=str(args.api_base),
			source_type=str(args.source_type),
			source_url=str(args.url),
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
