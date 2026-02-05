from __future__ import annotations

from sqlalchemy.orm import Session

from core.db.models.llm_settings import LLMActive, LLMProfileSecret


def get_llm_provider_secret_meta(session: Session, *, provider_id: str) -> dict | None:
	row = session.get(LLMProfileSecret, (provider_id or "").strip().lower())
	if row is None:
		return None
	return {"hasKey": True, "secretUpdatedAtMs": int(row.updated_at_ms)}


def upsert_llm_provider_secret_ciphertext(
	session: Session,
	*,
	provider_id: str,
	ciphertext_b64: str,
	now_ms: int,
) -> None:
	pid = (provider_id or "").strip().lower()
	obj = session.get(LLMProfileSecret, pid)
	if obj is None:
		obj = LLMProfileSecret(provider_id=pid, ciphertext=str(ciphertext_b64), updated_at_ms=int(now_ms))
		session.add(obj)
		return
	obj.ciphertext = str(ciphertext_b64)
	obj.updated_at_ms = int(now_ms)
	session.add(obj)


def delete_llm_provider_secret(session: Session, *, provider_id: str) -> bool:
	pid = (provider_id or "").strip().lower()
	obj = session.get(LLMProfileSecret, pid)
	if obj is None:
		return False
	session.delete(obj)
	return True


def get_llm_provider_secret_ciphertext(session: Session, *, provider_id: str) -> str | None:
	pid = (provider_id or "").strip().lower()
	obj = session.get(LLMProfileSecret, pid)
	if obj is None:
		return None
	return str(obj.ciphertext)


def get_llm_active(session: Session) -> dict | None:
	obj = session.get(LLMActive, 1)
	if obj is None:
		return None
	return {
		"providerId": str(obj.provider_id),
		"modelId": str(obj.model_id),
		"updatedAtMs": int(obj.updated_at_ms),
	}


def set_llm_active(session: Session, *, provider_id: str, model_id: str, now_ms: int) -> None:
	obj = session.get(LLMActive, 1)
	if obj is None:
		obj = LLMActive(id=1, provider_id=str(provider_id), model_id=str(model_id), updated_at_ms=int(now_ms))
		session.add(obj)
		return
	obj.provider_id = str(provider_id)
	obj.model_id = str(model_id)
	obj.updated_at_ms = int(now_ms)
	session.add(obj)
