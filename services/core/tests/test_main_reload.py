from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_entry_module():
	module_path = Path(__file__).resolve().parents[1] / "main.py"
	spec = importlib.util.spec_from_file_location("video_helper_core_entry_main", module_path)
	assert spec is not None and spec.loader is not None
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module


def test_should_disable_reload_for_frozen_build(monkeypatch) -> None:
	entry = _load_entry_module()
	monkeypatch.delenv("CORE_RELOAD", raising=False)
	monkeypatch.delenv("DATA_DIR", raising=False)
	monkeypatch.setattr(entry.sys, "frozen", True, raising=False)

	assert entry._should_enable_reload() is False


def test_core_reload_override_still_applies(monkeypatch) -> None:
	entry = _load_entry_module()
	monkeypatch.setenv("CORE_RELOAD", "1")
	monkeypatch.setattr(entry.sys, "frozen", True, raising=False)

	assert entry._should_enable_reload() is True
