from __future__ import annotations

from sqlalchemy.orm import Session

from core.db.models.asset import Asset


def get_asset_by_id(session: Session, asset_id: str) -> Asset | None:
    return session.get(Asset, asset_id)
