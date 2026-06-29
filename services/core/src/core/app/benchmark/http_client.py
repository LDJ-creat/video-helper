from __future__ import annotations

import json
from typing import Any

import httpx


def _now_ms() -> int:
	import time

	return int(time.time() * 1000)


def post_json_job(*, client: httpx.Client, api_base: str, source_type: str, source_url: str, title: str | None = None) -> dict[str, Any]:
	payload: dict[str, Any] = {"sourceType": source_type, "sourceUrl": source_url}
	if isinstance(title, str) and title.strip():
		payload["title"] = title.strip()
	resp = client.post(f"{api_base.rstrip('/')}/api/v1/jobs", json=payload, headers={"Accept": "application/json"})
	resp.raise_for_status()
	data = resp.json()
	if not isinstance(data, dict) or not data.get("jobId") or not data.get("projectId"):
		raise RuntimeError(f"unexpected create job response: {resp.text[:200]}")
	return data


def post_upload_job(*, client: httpx.Client, api_base: str, file_path: str, filename: str | None = None) -> dict[str, Any]:
	from pathlib import Path

	path = Path(file_path)
	if not path.is_file():
		raise FileNotFoundError(file_path)
	name = filename or path.name
	boundary = f"----videohelper-benchmark-{_now_ms()}"
	crlf = "\r\n"
	parts: list[bytes] = []

	def _field(k: str, v: str) -> None:
		parts.append(f"--{boundary}{crlf}".encode())
		parts.append(f'Content-Disposition: form-data; name="{k}"{crlf}{crlf}'.encode())
		parts.append(v.encode())
		parts.append(crlf.encode())

	_field("sourceType", "upload")
	content = path.read_bytes()
	parts.append(f"--{boundary}{crlf}".encode())
	parts.append(
		(
			f'Content-Disposition: form-data; name="file"; filename="{name}"{crlf}'
			f"Content-Type: application/octet-stream{crlf}{crlf}"
		).encode()
	)
	parts.append(content)
	parts.append(crlf.encode())
	parts.append(f"--{boundary}--{crlf}".encode())

	body = b"".join(parts)
	resp = client.post(
		f"{api_base.rstrip('/')}/api/v1/jobs",
		content=body,
		headers={
			"Content-Type": f"multipart/form-data; boundary={boundary}",
			"Accept": "application/json",
		},
	)
	resp.raise_for_status()
	data = resp.json()
	if not isinstance(data, dict) or not data.get("jobId") or not data.get("projectId"):
		raise RuntimeError(f"unexpected upload job response: {resp.text[:200]}")
	return data


def get_job(*, client: httpx.Client, api_base: str, job_id: str) -> dict[str, Any]:
	resp = client.get(f"{api_base.rstrip('/')}/api/v1/jobs/{job_id}", headers={"Accept": "application/json"})
	resp.raise_for_status()
	data = resp.json()
	if not isinstance(data, dict):
		raise RuntimeError("job GET returned non-object")
	return data


def get_latest_result(*, client: httpx.Client, api_base: str, project_id: str) -> dict[str, Any]:
	resp = client.get(
		f"{api_base.rstrip('/')}/api/v1/projects/{project_id}/results/latest",
		headers={"Accept": "application/json"},
	)
	resp.raise_for_status()
	data = resp.json()
	if not isinstance(data, dict):
		raise RuntimeError("latest result returned non-object")
	return data


def wait_for_job_done(*, client: httpx.Client, api_base: str, job_id: str, timeout_s: int) -> dict[str, Any]:
	import time

	deadline = time.time() + timeout_s
	last_line = None
	while time.time() < deadline:
		job = get_job(client=client, api_base=api_base, job_id=job_id)
		status = str(job.get("status") or "")
		line = f"status={status} stage={job.get('stage')} progress={job.get('progress')}"
		if line != last_line:
			print(f"[benchmark] {line}")
			last_line = line
		if status in {"succeeded", "failed", "canceled"}:
			return job
		time.sleep(1)
	raise TimeoutError(f"timed out waiting for job {job_id}")
