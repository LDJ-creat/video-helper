from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Mapping

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



def get_effective_analyze_settings() -> AnalyzeSettings:
	"""Resolve effective analyze settings (non-sensitive) from env only.

The legacy settings.json mechanism is deprecated and intentionally ignored.
API keys are intentionally excluded.
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
