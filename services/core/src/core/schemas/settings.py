from __future__ import annotations

from pydantic import BaseModel


class AnalyzeSettingsDTO(BaseModel):
	provider: str
	baseUrl: str | None = None
	model: str | None = None
	timeoutS: int
	allowRulesFallback: bool
	debug: bool
