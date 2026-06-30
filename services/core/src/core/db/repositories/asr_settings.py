from __future__ import annotations

from sqlalchemy.orm import Session

from core.db.models.asr_settings import AsrActive, AsrProfileSecret


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
		"languageHints": list(obj.language_hints or []),
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
	language_hints: list[str] | None,
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
			language_hints=language_hints,
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
	obj.language_hints = language_hints
	obj.local_model_size = str(local_model_size)
	obj.local_device = str(local_device)
	obj.fallback_to_local = bool(fallback_to_local)
	obj.updated_at_ms = int(now_ms)
	session.add(obj)
