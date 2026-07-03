from __future__ import annotations

from sqlalchemy.orm import Session

from core.db.models.asr_settings import AsrActive, AsrCustomModel, AsrProfileSecret


def get_asr_provider_secret_meta(session: Session, *, provider_id: str) -> dict | None:
	row = session.get(AsrProfileSecret, (provider_id or "").strip().lower())
	if row is None:
		return None
	return {"hasKey": True, "secretUpdatedAtMs": int(row.updated_at_ms)}


def upsert_asr_provider_secret_ciphertext(
	session: Session,
	*,
	provider_id: str,
	ciphertext_b64: str,
	now_ms: int,
) -> None:
	pid = (provider_id or "").strip().lower()
	obj = session.get(AsrProfileSecret, pid)
	if obj is None:
		obj = AsrProfileSecret(provider_id=pid, ciphertext=str(ciphertext_b64), updated_at_ms=int(now_ms))
		session.add(obj)
		return
	obj.ciphertext = str(ciphertext_b64)
	obj.updated_at_ms = int(now_ms)
	session.add(obj)


def delete_asr_provider_secret(session: Session, *, provider_id: str) -> bool:
	pid = (provider_id or "").strip().lower()
	obj = session.get(AsrProfileSecret, pid)
	if obj is None:
		return False
	session.delete(obj)
	return True


def get_asr_provider_secret_ciphertext(session: Session, *, provider_id: str) -> str | None:
	pid = (provider_id or "").strip().lower()
	obj = session.get(AsrProfileSecret, pid)
	if obj is None:
		return None
	return str(obj.ciphertext)


def get_asr_active(session: Session) -> dict | None:
	obj = session.get(AsrActive, 1)
	if obj is None:
		return None
	return {
		"cloudEnabled": bool(obj.cloud_enabled),
		"providerId": str(obj.provider_id),
		"modelId": str(obj.model_id),
		"localModelSize": str(obj.local_model_size),
		"localDevice": str(obj.local_device),
		"fallbackToLocal": bool(obj.fallback_to_local),
		"updatedAtMs": int(obj.updated_at_ms),
	}


def set_asr_active(
	session: Session,
	*,
	cloud_enabled: bool,
	provider_id: str,
	model_id: str,
	local_model_size: str,
	local_device: str,
	fallback_to_local: bool,
	now_ms: int,
) -> None:
	obj = session.get(AsrActive, 1)
	if obj is None:
		obj = AsrActive(
			id=1,
			cloud_enabled=bool(cloud_enabled),
			provider_id=str(provider_id),
			model_id=str(model_id),
			local_model_size=str(local_model_size),
			local_device=str(local_device),
			fallback_to_local=bool(fallback_to_local),
			updated_at_ms=int(now_ms),
		)
		session.add(obj)
		return
	obj.cloud_enabled = bool(cloud_enabled)
	obj.provider_id = str(provider_id)
	obj.model_id = str(model_id)
	obj.local_model_size = str(local_model_size)
	obj.local_device = str(local_device)
	obj.fallback_to_local = bool(fallback_to_local)
	obj.updated_at_ms = int(now_ms)
	session.add(obj)


def list_custom_asr_models(session: Session, *, provider_id: str) -> list[dict]:
	pid = (provider_id or "").strip().lower()
	rows = session.query(AsrCustomModel).filter(AsrCustomModel.provider_id == pid).all()
	return [
		{"modelId": r.model_id, "displayName": r.display_name, "createdAtMs": r.created_at_ms}
		for r in rows
	]


def add_custom_asr_model(
	session: Session,
	*,
	provider_id: str,
	model_id: str,
	display_name: str,
	now_ms: int,
) -> None:
	pid = (provider_id or "").strip().lower()
	mid = (model_id or "").strip()
	existing = (
		session.query(AsrCustomModel)
		.filter(AsrCustomModel.provider_id == pid, AsrCustomModel.model_id == mid)
		.first()
	)
	if existing is not None:
		existing.display_name = str(display_name)
		existing.created_at_ms = int(now_ms)
		session.add(existing)
		return
	obj = AsrCustomModel(
		provider_id=pid,
		model_id=mid,
		display_name=str(display_name),
		created_at_ms=int(now_ms),
	)
	session.add(obj)


def delete_custom_asr_model(session: Session, *, provider_id: str, model_id: str) -> bool:
	pid = (provider_id or "").strip().lower()
	mid = (model_id or "").strip()
	row = (
		session.query(AsrCustomModel)
		.filter(AsrCustomModel.provider_id == pid, AsrCustomModel.model_id == mid)
		.first()
	)
	if row is None:
		return False
	session.delete(row)
	return True
