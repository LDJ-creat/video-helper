from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker


def _default_data_dir() -> Path:
	import os

	data_dir = os.environ.get("DATA_DIR")
	if data_dir:
		return Path(data_dir)

	# repo-root/data (repo root is 4 levels above this file: core→src→core→services→repo)
	return Path(__file__).resolve().parents[4] / "data"


def get_data_dir() -> Path:
	"""Resolve the DATA_DIR used for DB and file storage."""
	return _default_data_dir()


def _sqlite_db_path() -> Path:
	return get_data_dir() / "core.sqlite3"


_ENGINE: Engine | None = None
_SESSIONMAKER: sessionmaker[Session] | None = None


def reset_db_engine_for_tests() -> None:
	"""Reset cached engine/sessionmaker.

	Intended for unit tests that need to vary DATA_DIR between runs.
	"""

	global _ENGINE, _SESSIONMAKER
	_ENGINE = None
	_SESSIONMAKER = None


# Backwards-compatible alias used by early story tests.
reset_db_for_tests = reset_db_engine_for_tests


def reset_db_for_tests() -> None:
	"""Reset global engine/sessionmaker.

	The current codebase uses module-level singletons; unit tests can call this
	after setting DATA_DIR to ensure isolation.
	"""

	global _ENGINE, _SESSIONMAKER
	if _ENGINE is not None:
		try:
			_ENGINE.dispose()
		finally:
			_ENGINE = None
	_SESSIONMAKER = None


def get_engine() -> Engine:
	global _ENGINE
	if _ENGINE is None:
		db_path = _sqlite_db_path()
		db_path.parent.mkdir(parents=True, exist_ok=True)

		_ENGINE = create_engine(
			f"sqlite+pysqlite:///{db_path.as_posix()}",
			future=True,
		)
	return _ENGINE


def get_sessionmaker() -> sessionmaker[Session]:
	global _SESSIONMAKER
	if _SESSIONMAKER is None:
		_SESSIONMAKER = sessionmaker(bind=get_engine(), autoflush=False, autocommit=False, future=True)
	return _SESSIONMAKER


def init_db() -> None:
	from core.db.base import Base
	from core.db.models.job import Job  # noqa: F401
	from core.db.models.project import Project  # noqa: F401

	Base.metadata.create_all(bind=get_engine())
	_ensure_sqlite_schema_compat()


def _ensure_sqlite_schema_compat() -> None:
	"""Best-effort schema upgrades for existing sqlite DBs.

	This repo currently uses SQLAlchemy create_all without Alembic migrations.
	To avoid breaking older local DB files, we apply small forward-compatible
	ALTER TABLE patches.
	"""

	engine = get_engine()
	with engine.begin() as conn:
		# projects.created_at_ms was added after the initial bootstrap.
		try:
			cols = [row[1] for row in conn.execute(text("PRAGMA table_info(projects)"))]
		except Exception:
			return

		if "created_at_ms" not in cols:
			conn.execute(
				text(
					"ALTER TABLE projects ADD COLUMN created_at_ms INTEGER NOT NULL DEFAULT 0"
				)
			)
			# Backfill to a sensible value for existing rows.
			conn.execute(text("UPDATE projects SET created_at_ms = updated_at_ms WHERE created_at_ms = 0"))

		# jobs claim/lease fields were added after the initial bootstrap.
		try:
			job_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(jobs)"))]
		except Exception:
			return

		if "claimed_by" not in job_cols:
			conn.execute(text("ALTER TABLE jobs ADD COLUMN claimed_by TEXT"))
		if "claim_token" not in job_cols:
			conn.execute(text("ALTER TABLE jobs ADD COLUMN claim_token TEXT"))
		if "lease_expires_at_ms" not in job_cols:
			conn.execute(text("ALTER TABLE jobs ADD COLUMN lease_expires_at_ms INTEGER"))
		if "started_at_ms" not in job_cols:
			conn.execute(text("ALTER TABLE jobs ADD COLUMN started_at_ms INTEGER"))
		if "finished_at_ms" not in job_cols:
			conn.execute(text("ALTER TABLE jobs ADD COLUMN finished_at_ms INTEGER"))
		if "attempt" not in job_cols:
			conn.execute(text("ALTER TABLE jobs ADD COLUMN attempt INTEGER NOT NULL DEFAULT 0"))


def get_db_session() -> Generator[Session, None, None]:
	SessionLocal = get_sessionmaker()
	session = SessionLocal()
	try:
		yield session
	finally:
		session.close()
