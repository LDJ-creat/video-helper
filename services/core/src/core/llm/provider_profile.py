from __future__ import annotations

from sqlalchemy.orm import Session

from core.db.repositories.llm_settings import get_provider_override
from core.llm.catalog import find_provider


def resolve_builtin_provider(session: Session, *, provider_id: str) -> dict | None:
	"""Merge static catalog defaults with optional user overrides from SQLite."""

	static = find_provider(provider_id)
	if static is None:
		return None

	display_name = static.display_name
	base_url = static.base_url
	override = get_provider_override(session, provider_id=static.provider_id)
	if override is not None:
		odn = (override.get("displayName") or "").strip()
		ourl = (override.get("baseUrl") or "").strip()
		if odn:
			display_name = odn
		if ourl:
			base_url = ourl

	return {
		"providerId": static.provider_id,
		"displayName": display_name,
		"baseUrl": base_url,
		"listingKind": static.listing_kind,
		"isCustom": False,
	}


def get_resolved_builtin_base_url(session: Session, *, provider_id: str) -> str | None:
	profile = resolve_builtin_provider(session, provider_id=provider_id)
	if profile is None:
		return None
	url = (profile.get("baseUrl") or "").strip()
	return url or None
