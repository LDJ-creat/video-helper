from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from core.db.session import get_data_dir


def _env_str(name: str) -> str | None:
	raw = os.environ.get(name)
	if raw is None:
		return None
	raw = raw.strip()
	return raw or None


def _env_int(name: str, default: int) -> int:
	raw = _env_str(name)
	if raw is None:
		return default
	try:
		return int(raw)
	except ValueError:
		return default


def _env_bool(name: str, default: bool = False) -> bool:
	raw = (os.environ.get(name) or "").strip().lower()
	if raw in {"1", "true", "yes", "y", "on"}:
		return True
	if raw in {"0", "false", "no", "n", "off"}:
		return False
	return default


class SettingsFileError(RuntimeError):
	"""Raised when persisted settings exist but are invalid/unreadable."""


@dataclass(frozen=True)
class AnalyzeSettings:
	"""Effective analyze settings (non-sensitive).

	Key rule: API keys are NOT stored here and must never be persisted.
	"""

	provider: str
	base_url: str | None
	model: str | None
	timeout_s: int
	allow_rules_fallback: bool
	debug: bool

	def to_public_payload(self) -> dict[str, Any]:
		return {
			"provider": self.provider,
			"baseUrl": self.base_url,
			"model": self.model,
			"timeoutS": self.timeout_s,
			"allowRulesFallback": self.allow_rules_fallback,
			"debug": self.debug,
		}


def _settings_file_path(data_dir: Path | None = None) -> Path:
	return (data_dir or get_data_dir()) / "settings.json"


def _coerce_str(val: Any) -> str | None:
	if val is None:
		return None
	if isinstance(val, str):
		s = val.strip()
		return s or None
	return str(val).strip() or None


def _coerce_int(val: Any) -> int | None:
	if val is None:
		return None
	if isinstance(val, bool):
		return None
	if isinstance(val, int):
		return int(val)
	if isinstance(val, float):
		return int(val)
	if isinstance(val, str):
		s = val.strip()
		if not s:
			return None
		try:
			return int(s)
		except ValueError:
			return None
	return None


def _coerce_bool(val: Any) -> bool | None:
	if val is None:
		return None
	if isinstance(val, bool):
		return val
	if isinstance(val, int):
		return bool(val)
	if isinstance(val, str):
		s = val.strip().lower()
		if s in {"1", "true", "yes", "y", "on"}:
			return True
		if s in {"0", "false", "no", "n", "off"}:
			return False
	return None


def load_persisted_settings_raw(*, data_dir: Path | None = None) -> dict[str, Any] | None:
	"""Load settings.json if it exists.

	Returns parsed dict on success, None if file does not exist.
	Raises SettingsFileError if the file exists but cannot be parsed.
	"""

	path = _settings_file_path(data_dir)
	if not path.exists():
		return None
	try:
		text = path.read_text(encoding="utf-8")
		obj = json.loads(text or "{}")
	except Exception as e:
		raise SettingsFileError(f"Invalid settings file: {path.name}") from e
	if not isinstance(obj, dict):
		raise SettingsFileError(f"Invalid settings file: {path.name}")
	return obj


def get_effective_analyze_settings(*, data_dir: Path | None = None) -> AnalyzeSettings:
	"""Resolve effective analyze settings (non-sensitive) from:

	1) env defaults
	2) DATA_DIR/settings.json overrides (if present)

	Note: API keys are intentionally excluded.
	"""

	provider = (_env_str("ANALYZE_PROVIDER") or "").lower()
	if provider not in {"llm", "rules", ""}:
		# Keep unknown values visible to the operator via API, but treat as-is.
		provider = provider
	if provider == "":
		provider = "rules"

	base_url = _env_str("LLM_API_BASE")
	model = _env_str("LLM_MODEL")
	timeout_s = max(1, int(_env_int("LLM_TIMEOUT_S", 60)))
	allow_rules_fallback = _env_bool("ANALYZE_ALLOW_RULES_FALLBACK", False)
	debug = _env_bool("LLM_DEBUG", False)

	raw = load_persisted_settings_raw(data_dir=data_dir)
	if raw and isinstance(raw.get("analyze"), Mapping):
		an = raw["analyze"]
		p = _coerce_str(an.get("provider"))
		if p is not None:
			provider = p.lower()

		bu = _coerce_str(an.get("baseUrl") if "baseUrl" in an else an.get("base_url"))
		if bu is not None:
			base_url = bu

		m = _coerce_str(an.get("model"))
		if m is not None:
			model = m

		ts = _coerce_int(an.get("timeoutS") if "timeoutS" in an else an.get("timeout_s"))
		if ts is not None:
			timeout_s = max(1, int(ts))

		arf = _coerce_bool(an.get("allowRulesFallback") if "allowRulesFallback" in an else an.get("allow_rules_fallback"))
		if arf is not None:
			allow_rules_fallback = bool(arf)

		db = _coerce_bool(an.get("debug"))
		if db is not None:
			debug = bool(db)

	return AnalyzeSettings(
		provider=provider,
		base_url=base_url,
		model=model,
		timeout_s=timeout_s,
		allow_rules_fallback=allow_rules_fallback,
		debug=debug,
	)


def resolve_llm_api_key(*, headers: Mapping[str, str] | None = None) -> str | None:
	"""Resolve LLM API key from runtime-only sources.

	Precedence:
	- request headers (X-LLM-API-KEY)
	- env (LLM_API_KEY)

	Never persisted; never returned by settings endpoints.
	"""

	if headers is not None:
		for k in ("x-llm-api-key", "x_llm_api_key"):
			v = headers.get(k) or headers.get(k.upper())
			if isinstance(v, str) and v.strip():
				return v.strip()
	return _env_str("LLM_API_KEY")
