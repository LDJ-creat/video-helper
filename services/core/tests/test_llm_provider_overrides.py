from __future__ import annotations

import time

from sqlalchemy.orm import Session

from core.db.repositories.llm_settings import upsert_provider_override
from core.db.session import get_sessionmaker, reset_db_engine_for_tests
from core.llm.provider_profile import resolve_builtin_provider


def test_resolve_builtin_provider_applies_override() -> None:
	import os
	import tempfile

	reset_db_engine_for_tests()
	prev_data_dir = os.environ.get("DATA_DIR")

	with tempfile.TemporaryDirectory() as d:
		os.environ["DATA_DIR"] = d
		reset_db_engine_for_tests()

		from core.db.session import init_db

		init_db()
		SessionLocal = get_sessionmaker()
		now_ms = int(time.time() * 1000)

		with SessionLocal() as session:
			before = resolve_builtin_provider(session, provider_id="openrouter")
			assert before is not None
			assert before["displayName"] == "OpenRouter"
			assert before["baseUrl"] == "https://openrouter.ai/api/v1"

			upsert_provider_override(
				session,
				provider_id="openrouter",
				display_name="My OpenRouter",
				base_url="https://proxy.example.com/v1",
				now_ms=now_ms,
			)
			session.commit()

			after = resolve_builtin_provider(session, provider_id="openrouter")
			assert after is not None
			assert after["displayName"] == "My OpenRouter"
			assert after["baseUrl"] == "https://proxy.example.com/v1"

	if prev_data_dir is None:
		os.environ.pop("DATA_DIR", None)
	else:
		os.environ["DATA_DIR"] = prev_data_dir
	reset_db_engine_for_tests()
