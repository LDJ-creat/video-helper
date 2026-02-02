from __future__ import annotations

from sqlalchemy.orm import Session

from core.db.models.result import Result


def get_result_by_id(session: Session, result_id: str) -> Result | None:
    return session.get(Result, result_id)
