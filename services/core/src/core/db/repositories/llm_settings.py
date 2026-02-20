from __future__ import annotations

from sqlalchemy.orm import Session

from core.db.models.llm_settings import LLMActive, LLMCustomModel, LLMCustomProvider, LLMProfileSecret


# ─── Provider secrets ────────────────────────────────────────────────────────


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


# ─── Active selection ─────────────────────────────────────────────────────────


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


# ─── Custom models ────────────────────────────────────────────────────────────


def list_custom_models(session: Session, *, provider_id: str) -> list[dict]:
	pid = (provider_id or "").strip().lower()
	rows = session.query(LLMCustomModel).filter(LLMCustomModel.provider_id == pid).all()
	return [
		{"modelId": r.model_id, "displayName": r.display_name, "createdAtMs": r.created_at_ms}
		for r in rows
	]


def add_custom_model(
	session: Session,
	*,
	provider_id: str,
	model_id: str,
	display_name: str,
	now_ms: int,
) -> None:
	"""Insert a custom model; silently replaces if (provider_id, model_id) already exists."""
	pid = (provider_id or "").strip().lower()
	mid = (model_id or "").strip()
	existing = (
		session.query(LLMCustomModel)
		.filter(LLMCustomModel.provider_id == pid, LLMCustomModel.model_id == mid)
		.first()
	)
	if existing is not None:
		existing.display_name = str(display_name)
		existing.created_at_ms = int(now_ms)
		session.add(existing)
		return
	obj = LLMCustomModel(
		provider_id=pid,
		model_id=mid,
		display_name=str(display_name),
		created_at_ms=int(now_ms),
	)
	session.add(obj)


def delete_custom_model(session: Session, *, provider_id: str, model_id: str) -> bool:
	pid = (provider_id or "").strip().lower()
	mid = (model_id or "").strip()
	row = (
		session.query(LLMCustomModel)
		.filter(LLMCustomModel.provider_id == pid, LLMCustomModel.model_id == mid)
		.first()
	)
	if row is None:
		return False
	session.delete(row)
	return True


# ─── Custom providers ─────────────────────────────────────────────────────────


def list_custom_providers(session: Session) -> list[dict]:
	rows = session.query(LLMCustomProvider).all()
	return [
		{
			"providerId": r.provider_id,
			"displayName": r.display_name,
			"baseUrl": r.base_url,
			"createdAtMs": r.created_at_ms,
		}
		for r in rows
	]


def get_custom_provider(session: Session, *, provider_id: str) -> dict | None:
	pid = (provider_id or "").strip().lower()
	row = session.get(LLMCustomProvider, pid)
	if row is None:
		return None
	return {
		"providerId": row.provider_id,
		"displayName": row.display_name,
		"baseUrl": row.base_url,
		"createdAtMs": row.created_at_ms,
	}


def add_custom_provider(
	session: Session,
	*,
	provider_id: str,
	display_name: str,
	base_url: str,
	now_ms: int,
) -> None:
	pid = (provider_id or "").strip().lower()
	existing = session.get(LLMCustomProvider, pid)
	if existing is not None:
		existing.display_name = str(display_name)
		existing.base_url = str(base_url)
		existing.created_at_ms = int(now_ms)
		session.add(existing)
		return
	obj = LLMCustomProvider(
		provider_id=pid,
		display_name=str(display_name),
		base_url=str(base_url),
		created_at_ms=int(now_ms),
	)
	session.add(obj)


def delete_custom_provider(session: Session, *, provider_id: str) -> bool:
	pid = (provider_id or "").strip().lower()
	row = session.get(LLMCustomProvider, pid)
	if row is None:
		return False
	session.delete(row)
	# Also remove all custom models belonging to this provider
	session.query(LLMCustomModel).filter(LLMCustomModel.provider_id == pid).delete()
	return True
