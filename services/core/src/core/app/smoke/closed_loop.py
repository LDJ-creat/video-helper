from __future__ import annotations

from collections.abc import Mapping


class SmokeValidationError(ValueError):
	pass


def _is_list(value) -> bool:
	return isinstance(value, list)


def _as_dict(value, *, name: str) -> dict:
	if not isinstance(value, dict):
		raise SmokeValidationError(f"{name} must be an object")
	return value


def validate_result_dto(payload: Mapping) -> dict:
	"""Validate ResultDTO shape (contracts-level), return normalized dict.

	This is intentionally strict enough for smoke, but avoids coupling to
	implementation details (e.g. additional fields).
	"""

	result = _as_dict(dict(payload), name="result")

	for key in ("resultId", "projectId", "schemaVersion", "pipelineVersion", "createdAtMs", "contentBlocks", "mindmap", "assetRefs"):
		if key not in result:
			raise SmokeValidationError(f"result.{key} missing")

	content_blocks = result.get("contentBlocks")
	asset_refs = result.get("assetRefs")
	mindmap = result.get("mindmap")

	if not _is_list(content_blocks) or len(content_blocks) < 1:
		raise SmokeValidationError("result.contentBlocks must be a non-empty array")
	if not _is_list(asset_refs) or len(asset_refs) < 1:
		raise SmokeValidationError("result.assetRefs must be a non-empty array")

	mindmap_d = _as_dict(mindmap, name="result.mindmap")
	nodes = mindmap_d.get("nodes")
	edges = mindmap_d.get("edges")
	if not _is_list(nodes) or len(nodes) < 1:
		raise SmokeValidationError("result.mindmap.nodes must be a non-empty array")
	if not _is_list(edges):
		raise SmokeValidationError("result.mindmap.edges must be an array")

	first_asset = asset_refs[0]
	if not isinstance(first_asset, dict):
		raise SmokeValidationError("result.assetRefs[0] must be an object")
	asset_id = first_asset.get("assetId")
	if not isinstance(asset_id, str) or not asset_id:
		raise SmokeValidationError("result.assetRefs[0].assetId must be a non-empty string")

	return result


def validate_asset_dto(payload: Mapping, *, expected_asset_id: str | None = None) -> dict:
	asset = _as_dict(dict(payload), name="asset")
	for key in ("assetId", "projectId", "kind", "origin", "mimeType", "contentUrl", "createdAtMs"):
		if key not in asset:
			raise SmokeValidationError(f"asset.{key} missing")

	asset_id = asset.get("assetId")
	if not isinstance(asset_id, str) or not asset_id:
		raise SmokeValidationError("asset.assetId must be a non-empty string")
	if expected_asset_id and asset_id != expected_asset_id:
		raise SmokeValidationError("asset.assetId mismatch")

	content_url = asset.get("contentUrl")
	if not isinstance(content_url, str) or not content_url:
		raise SmokeValidationError("asset.contentUrl must be a non-empty string")

	return asset
