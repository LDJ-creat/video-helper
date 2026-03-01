from __future__ import annotations

from pathlib import Path

import pytest

from core.app.pipeline.transcript_store import store_transcript_json


def test_store_transcript_json_writes_and_hashes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
	monkeypatch.setenv("DATA_DIR", str(tmp_path))

	transcript = {"version": 1, "segments": [{"startMs": 0, "endMs": 1, "text": "a"}], "durationMs": 1, "unit": "ms"}
	stored = store_transcript_json(project_id="p1", job_id="j1", transcript=transcript)
	assert stored.abs_path.exists()
	assert stored.rel_path == stored.abs_path.relative_to(tmp_path).as_posix()
	assert len(stored.sha256) == 64
