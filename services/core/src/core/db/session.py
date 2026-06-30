from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool


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
		import os

		db_path = _sqlite_db_path()
		db_path.parent.mkdir(parents=True, exist_ok=True)

		# Pytest on Windows can fail to delete TemporaryDirectory sqlite files if a
		# pooled connection keeps the DB file handle open. Use NullPool for tests.
		# (Runtime keeps the default pool.)
		use_null_pool = bool(os.environ.get("PYTEST_CURRENT_TEST"))
		kwargs = {"future": True}
		if use_null_pool:
			kwargs["poolclass"] = NullPool
		
		# Increase SQLite timeout to reduce "database is locked" errors
		kwargs["connect_args"] = {"timeout": 20}

		_ENGINE = create_engine(
			f"sqlite+pysqlite:///{db_path.as_posix()}",
			**kwargs,
		)

		# Enable WAL mode for better concurrency
		@event.listens_for(_ENGINE, "connect")
		def set_sqlite_pragma(dbapi_connection, connection_record):
			cursor = dbapi_connection.cursor()
			cursor.execute("PRAGMA busy_timeout = 20000")
			
			# Check if already in WAL mode to avoid unnecessary exclusive lock
			mode = cursor.execute("PRAGMA journal_mode").fetchone()[0]
			if mode.upper() != "WAL":
				cursor.execute("PRAGMA journal_mode=WAL")
				
			cursor.execute("PRAGMA synchronous=NORMAL")
			cursor.close()

	return _ENGINE


def get_sessionmaker() -> sessionmaker[Session]:
	global _SESSIONMAKER
	if _SESSIONMAKER is None:
		_SESSIONMAKER = sessionmaker(bind=get_engine(), autoflush=False, autocommit=False, future=True)
	return _SESSIONMAKER


def init_db() -> None:
	from core.db.base import Base
	from core.db.models.asset import Asset  # noqa: F401
	from core.db.models.job import Job  # noqa: F401
	from core.db.models.asr_settings import AsrActive, AsrProfileSecret  # noqa: F401
	from core.db.models.llm_settings import LLMActive, LLMProfileSecret, LLMProviderOverride  # noqa: F401
	from core.db.models.project import Project  # noqa: F401
	from core.db.models.project_category import ProjectCategory  # noqa: F401
	from core.db.models.result import Result  # noqa: F401

	Base.metadata.create_all(bind=get_engine())
	_ensure_sqlite_schema_compat()
	_bootstrap_categories()


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
		if "transcript" not in job_cols:
			conn.execute(text("ALTER TABLE jobs ADD COLUMN transcript TEXT"))
		if "audio_ref" not in job_cols:
			conn.execute(text("ALTER TABLE jobs ADD COLUMN audio_ref TEXT"))
		if "transcript_ref" not in job_cols:
			conn.execute(text("ALTER TABLE jobs ADD COLUMN transcript_ref TEXT"))
		if "transcript_meta" not in job_cols:
			conn.execute(text("ALTER TABLE jobs ADD COLUMN transcript_meta TEXT"))
		if "output_language" not in job_cols:
			conn.execute(text("ALTER TABLE jobs ADD COLUMN output_language TEXT"))
		if "llm_mode" not in job_cols:
			conn.execute(text("ALTER TABLE jobs ADD COLUMN llm_mode TEXT"))
		if "external_plan" not in job_cols:
			conn.execute(text("ALTER TABLE jobs ADD COLUMN external_plan TEXT"))

		# results.updated_at_ms was added for editing APIs (note/mindmap/keyframes).
		try:
			result_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(results)"))]
		except Exception:
			return

		if "updated_at_ms" not in result_cols:
			conn.execute(text("ALTER TABLE results ADD COLUMN updated_at_ms INTEGER NOT NULL DEFAULT 0"))
			conn.execute(text("UPDATE results SET updated_at_ms = created_at_ms WHERE updated_at_ms = 0"))

		# vNext schema (方案A): only content_blocks + mindmap + note_json + asset_refs.
		# Older DBs had NOT NULL chapters/highlights/note columns; if we stop writing
		# them, inserts will fail. Rebuild the table to drop legacy columns.
		needs_rebuild = any(
			c in result_cols
			for c in (
				"chapters",
				"highlights",
				"note",  # old column name
			)
		)
		if needs_rebuild:
			conn.execute(text("ALTER TABLE results RENAME TO results_old"))
			conn.execute(
				text(
					"""
					CREATE TABLE results (
						result_id TEXT PRIMARY KEY,
						project_id TEXT NOT NULL,
						schema_version TEXT NOT NULL,
						pipeline_version TEXT NOT NULL,
						created_at_ms INTEGER NOT NULL,
						updated_at_ms INTEGER NOT NULL,
						content_blocks TEXT NOT NULL DEFAULT '[]',
						mindmap TEXT NOT NULL DEFAULT '{}',
						note_json TEXT NOT NULL DEFAULT '{}',
						asset_refs TEXT NOT NULL DEFAULT '[]'
					)
					"""
				)
			)

			old_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(results_old)"))]
			content_blocks_expr = "content_blocks" if "content_blocks" in old_cols else "'[]'"
			mindmap_expr = "mindmap" if "mindmap" in old_cols else "'{}'"
			# Prefer note_json if present, else fall back to legacy note.
			note_expr = "note_json" if "note_json" in old_cols else ("note" if "note" in old_cols else "'{}'")
			asset_refs_expr = "asset_refs" if "asset_refs" in old_cols else "'[]'"

			conn.execute(
				text(
					f"""
					INSERT INTO results (
						result_id, project_id, schema_version, pipeline_version,
						created_at_ms, updated_at_ms,
						content_blocks, mindmap, note_json, asset_refs
					)
					SELECT
						result_id, project_id, schema_version, pipeline_version,
						created_at_ms, updated_at_ms,
						{content_blocks_expr}, {mindmap_expr}, {note_expr}, {asset_refs_expr}
					FROM results_old
					"""
				)
			)
			conn.execute(text("DROP TABLE results_old"))
			result_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(results)"))]

		# Ensure required vNext columns exist for non-legacy DBs.
		if "content_blocks" not in result_cols:
			conn.execute(text("ALTER TABLE results ADD COLUMN content_blocks TEXT NOT NULL DEFAULT '[]'"))
		if "note_json" not in result_cols:
			# If old DB already had note column but not note_json, we keep it via rebuild above.
			conn.execute(text("ALTER TABLE results ADD COLUMN note_json TEXT NOT NULL DEFAULT '{}'"))

		# project_categories table + projects.category_id
		from core.db.constants.categories import (
			DEFAULT_CATEGORY_ID,
			DEFAULT_CATEGORY_NAME,
			DEFAULT_CATEGORY_SLUG,
		)

		tables = [
			row[0]
			for row in conn.execute(
				text("SELECT name FROM sqlite_master WHERE type='table'")
			).all()
		]
		if "project_categories" not in tables:
			conn.execute(
				text(
					"""
					CREATE TABLE project_categories (
						category_id TEXT PRIMARY KEY,
						name TEXT NOT NULL UNIQUE,
						slug TEXT NOT NULL UNIQUE,
						is_system INTEGER NOT NULL DEFAULT 0,
						created_at_ms INTEGER NOT NULL,
						updated_at_ms INTEGER NOT NULL
					)
					"""
				)
			)

		try:
			proj_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(projects)"))]
		except Exception:
			return

		if "category_id" not in proj_cols:
			conn.execute(text("ALTER TABLE projects ADD COLUMN category_id TEXT"))

		now_ms = int(__import__("time").time() * 1000)
		existing_default = conn.execute(
			text("SELECT category_id FROM project_categories WHERE category_id = :id"),
			{"id": DEFAULT_CATEGORY_ID},
		).first()
		if existing_default is None:
			conn.execute(
				text(
					"""
					INSERT INTO project_categories (
						category_id, name, slug, is_system, created_at_ms, updated_at_ms
					) VALUES (:id, :name, :slug, 1, :now, :now)
					"""
				),
				{
					"id": DEFAULT_CATEGORY_ID,
					"name": DEFAULT_CATEGORY_NAME,
					"slug": DEFAULT_CATEGORY_SLUG,
					"now": now_ms,
				},
			)

		conn.execute(
			text(
				"UPDATE projects SET category_id = :default_id WHERE category_id IS NULL"
			),
			{"default_id": DEFAULT_CATEGORY_ID},
		)


def _bootstrap_categories() -> None:
	from core.db.repositories.categories import backfill_projects_default_category, ensure_default_category

	SessionLocal = get_sessionmaker()
	with SessionLocal() as session:
		ensure_default_category(session)
		backfill_projects_default_category(session)
		session.commit()


def get_db_session() -> Generator[Session, None, None]:
	SessionLocal = get_sessionmaker()
	session = SessionLocal()
	try:
		yield session
	finally:
		session.close()
