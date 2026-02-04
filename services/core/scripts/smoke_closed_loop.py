from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import httpx


def _load_env_file(path: Path) -> None:
	"""Minimal dotenv loader.

	Loads KEY=VALUE pairs into os.environ (does not override existing vars).
	"""

	if not path.exists():
		return

	try:
		for raw in path.read_text(encoding="utf-8").splitlines():
			line = raw.strip()
			if not line or line.startswith("#"):
				continue
			if "=" not in line:
				continue
			key, value = line.split("=", 1)
			key = key.strip()
			value = value.strip().strip('"').strip("'")
			if not key:
				continue
			os.environ.setdefault(key, value)
	except OSError:
		return


def _now_ms() -> int:
	return int(time.time() * 1000)


def _safe_snippet(text: str, *, max_len: int = 200) -> str:
	text = (text or "").strip().replace("\r", " ").replace("\n", " ")
	if len(text) > max_len:
		return text[:max_len] + "…"
	return text


def _is_job_done(status: str | None) -> bool:
	return (status or "") in {"succeeded", "failed", "canceled"}


def create_job(*, client: httpx.Client, api_base: str, source_type: str, source_url: str, title: str) -> dict:
	resp = client.post(
		f"{api_base}/api/v1/jobs",
		json={"sourceType": source_type, "sourceUrl": source_url, "title": title},
		headers={"Accept": "application/json"},
	)
	resp.raise_for_status()
	data = resp.json()
	if not isinstance(data, dict) or not data.get("jobId") or not data.get("projectId"):
		raise RuntimeError(f"Create job returned unexpected JSON: {_safe_snippet(resp.text)}")
	return data


def get_job(*, client: httpx.Client, api_base: str, job_id: str) -> dict:
	resp = client.get(f"{api_base}/api/v1/jobs/{job_id}", headers={"Accept": "application/json"})
	resp.raise_for_status()
	data = resp.json()
	if not isinstance(data, dict):
		raise RuntimeError("Job GET returned non-object JSON")
	return data


def wait_for_job_done(*, client: httpx.Client, api_base: str, job_id: str, timeout_s: int) -> dict:
	deadline = time.time() + timeout_s
	last_line = None
	seen_stages: set[str] = set()
	while time.time() < deadline:
		job = get_job(client=client, api_base=api_base, job_id=job_id)
		status = job.get("status")
		stage = job.get("stage")
		progress = job.get("progress")
		if isinstance(stage, str) and stage:
			seen_stages.add(stage)
		line = f"status={status} stage={stage} progress={progress}"
		if line != last_line:
			print(f"[smoke] {line}")
			last_line = line

		if _is_job_done(str(status) if status is not None else None):
			job["_smokeSeenStages"] = sorted(seen_stages)
			return job

		time.sleep(1)

	raise TimeoutError(f"Timed out waiting for job {job_id}")


def get_latest_result(*, client: httpx.Client, api_base: str, project_id: str) -> dict:
	resp = client.get(
		f"{api_base}/api/v1/projects/{project_id}/results/latest",
		headers={"Accept": "application/json"},
	)
	resp.raise_for_status()
	data = resp.json()
	if not isinstance(data, dict):
		raise RuntimeError("latest result returned non-object JSON")
	return data


def get_asset(*, client: httpx.Client, api_base: str, asset_id: str) -> dict:
	resp = client.get(f"{api_base}/api/v1/assets/{asset_id}", headers={"Accept": "application/json"})
	resp.raise_for_status()
	data = resp.json()
	if not isinstance(data, dict):
		raise RuntimeError("asset returned non-object JSON")
	return data


def fetch_asset_range(*, client: httpx.Client, api_base: str, content_url: str) -> None:
	url = content_url
	if content_url.startswith("/"):
		url = api_base.rstrip("/") + content_url

	resp = client.get(url, headers={"Range": "bytes=0-1023"})
	if resp.status_code not in (200, 206):
		raise RuntimeError(f"asset content unexpected httpStatus={resp.status_code}")
	if not resp.content:
		raise RuntimeError("asset content empty")


def main() -> int:
	parser = argparse.ArgumentParser(description="Closed-loop smoke: jobs -> latest result -> asset content")
	parser.add_argument("--api-base", default="http://127.0.0.1:8000")
	parser.add_argument("--timeout-sec", type=int, default=1200)
	parser.add_argument("--source-type", default="bilibili")
	parser.add_argument(
		"--url",
		default="https://www.bilibili.com/video/BV1jgifB7EAp/?spm_id_from=333.337.search-card.all.click&vd_source=8e03b1a6cd89d2b50af0c43b7de269ff",
	)
	parser.add_argument("--title", default="smoke-closed-loop")
	parser.add_argument("--job-id", default="")
	parser.add_argument("--project-id", default="")	
	parser.add_argument("--summary-out", default="")
	args = parser.parse_args()

	core_root = Path(__file__).resolve().parents[1]
	_load_env_file(core_root / ".env")

	src_dir = core_root / "src"
	if str(src_dir) not in sys.path:
		sys.path.insert(0, str(src_dir))

	from core.app.smoke.closed_loop import SmokeValidationError, validate_asset_dto, validate_result_dto  # noqa: E402

	api_base = str(args.api_base).rstrip("/")
	timeout_s = int(args.timeout_sec)

	summary_out = (args.summary_out or "").strip()
	start_ms = _now_ms()
	print(f"[smoke] start tsMs={start_ms}")

	try:
		with httpx.Client(timeout=60.0) as client:
			job_id = (args.job_id or "").strip()
			project_id = (args.project_id or "").strip()

			if not job_id:
				created = create_job(
					client=client,
					api_base=api_base,
					source_type=str(args.source_type),
					source_url=str(args.url),
					title=str(args.title),
				)
				job_id = str(created["jobId"])
				project_id = str(created["projectId"])
				print(f"[smoke] job created jobId={job_id} projectId={project_id}")
			else:
				print(f"[smoke] using jobId={job_id}")
				if not project_id:
					job = get_job(client=client, api_base=api_base, job_id=job_id)
					project_id = str(job.get("projectId") or "").strip()

			final_job = wait_for_job_done(client=client, api_base=api_base, job_id=job_id, timeout_s=timeout_s)
			if final_job.get("status") != "succeeded":
				err = final_job.get("error")
				raise RuntimeError(f"job failed status={final_job.get('status')} error={json.dumps(err, ensure_ascii=False) if err else None}")

			seen_stages = final_job.get("_smokeSeenStages")
			if not (isinstance(seen_stages, list) and "assemble_result" in seen_stages):
				raise RuntimeError(f"job did not reach assemble_result (seenStages={seen_stages})")

			if not project_id:
				raise RuntimeError("missing projectId")

			result = get_latest_result(client=client, api_base=api_base, project_id=project_id)
			validated = validate_result_dto(result)
			asset_id = validated["assetRefs"][0]["assetId"]

			asset = get_asset(client=client, api_base=api_base, asset_id=asset_id)
			asset_valid = validate_asset_dto(asset, expected_asset_id=asset_id)

			fetch_asset_range(client=client, api_base=api_base, content_url=str(asset_valid["contentUrl"]))

			elapsed_ms = _now_ms() - start_ms
			if summary_out:
				try:
					Path(summary_out).write_text(
						json.dumps(
							{
								"ok": True,
								"jobId": job_id,
								"projectId": project_id,
								"assetId": asset_id,
								"elapsedMs": elapsed_ms,
							},
							ensure_ascii=False,
						),
						encoding="utf-8",
					)
				except Exception:
					pass
			print(f"[ok] closed-loop smoke OK elapsedMs={elapsed_ms} jobId={job_id} projectId={project_id} assetId={asset_id}")
			return 0

	except SmokeValidationError as e:
		print("[smoke] FAILED validation")
		print(str(e))
		if summary_out:
			try:
				Path(summary_out).write_text(json.dumps({"ok": False, "kind": "validation", "error": str(e)}, ensure_ascii=False), encoding="utf-8")
			except Exception:
				pass
		return 10
	except httpx.HTTPStatusError as e:
		status = getattr(e.response, "status_code", None)
		body = _safe_snippet(getattr(e.response, "text", ""))
		print("[smoke] FAILED http")
		print(f"httpStatus={status} bodySnippet={body}")
		if summary_out:
			try:
				Path(summary_out).write_text(json.dumps({"ok": False, "kind": "http", "httpStatus": status, "bodySnippet": body}, ensure_ascii=False), encoding="utf-8")
			except Exception:
				pass
		return 11
	except httpx.RequestError as e:
		print("[smoke] FAILED request")
		print(f"error={type(e).__name__}")
		if summary_out:
			try:
				Path(summary_out).write_text(json.dumps({"ok": False, "kind": "request", "error": type(e).__name__}, ensure_ascii=False), encoding="utf-8")
			except Exception:
				pass
		return 12
	except Exception as e:
		print("[smoke] FAILED")
		print(f"error={type(e).__name__}: {e}")
		if summary_out:
			try:
				Path(summary_out).write_text(json.dumps({"ok": False, "kind": "exception", "error": f"{type(e).__name__}: {e}"}, ensure_ascii=False), encoding="utf-8")
			except Exception:
				pass
		return 13


if __name__ == "__main__":
	raise SystemExit(main())
