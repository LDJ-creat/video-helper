from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, TypedDict

from .primitives import TsMs


# ---- Frozen external response schema (200-only) ----


class DependencyCheck(TypedDict):
    ok: bool
    version: str | None
    message: str | None
    actions: list[str]


class HealthResponse(TypedDict):
    status: Literal["ok", "degraded"]
    ready: bool
    tsMs: TsMs
    dependencies: dict[str, DependencyCheck]


# ---- Internal helpers to keep payload stable & camelCase ----


@dataclass(frozen=True, slots=True)
class DependencyProbe:
    ok: bool
    version: str | None = None
    message: str | None = None
    actions: list[str] = field(default_factory=list)

    def to_payload(self) -> DependencyCheck:
        return {
            "ok": self.ok,
            "version": self.version,
            "message": self.message,
            "actions": list(self.actions),
        }
