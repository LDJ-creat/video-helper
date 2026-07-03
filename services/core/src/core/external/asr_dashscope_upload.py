from __future__ import annotations

from pathlib import Path

import httpx

UPLOAD_POLICY_URL = "https://dashscope.aliyuncs.com/api/v1/uploads"


def upload_audio_to_dashscope_temp_oss(
	client: httpx.Client,
	*,
	api_key: str,
	model: str,
	file_path: Path,
) -> str:
	resp = client.get(
		UPLOAD_POLICY_URL,
		headers={"Authorization": f"Bearer {api_key}"},
		params={"action": "getPolicy", "model": model},
	)
	if resp.status_code != 200:
		raise RuntimeError(f"getPolicy failed ({resp.status_code}): {resp.text}")
	data = resp.json().get("data")
	if not isinstance(data, dict):
		raise RuntimeError(f"unexpected getPolicy response: {resp.text}")

	file_name = file_path.name
	key = f"{data['upload_dir']}/{file_name}"
	with file_path.open("rb") as fh:
		files = {
			"OSSAccessKeyId": (None, data["oss_access_key_id"]),
			"Signature": (None, data["signature"]),
			"policy": (None, data["policy"]),
			"x-oss-object-acl": (None, data["x_oss_object_acl"]),
			"x-oss-forbid-overwrite": (None, data["x_oss_forbid_overwrite"]),
			"key": (None, key),
			"success_action_status": (None, "200"),
			"file": (file_name, fh),
		}
		upload_resp = client.post(data["upload_host"], files=files)
	if upload_resp.status_code != 200:
		raise RuntimeError(f"OSS upload failed ({upload_resp.status_code}): {upload_resp.text}")
	return f"oss://{key}"
