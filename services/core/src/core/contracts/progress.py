from __future__ import annotations

from dataclasses import dataclass

from .stages import PublicStage, to_public_stage


def normalize_progress(progress: float | int | None) -> float | None:
    """Ensure externally visible progress is either None or within [0, 1]."""

    if progress is None:
        return None

    if isinstance(progress, bool) or not isinstance(progress, (int, float)):
        raise TypeError("progress must be a number in [0, 1] or None")

    value = float(progress)
    if value < 0.0 or value > 1.0:
        raise ValueError("progress must be within [0, 1]")

    return value


@dataclass(frozen=True, slots=True)
class StageProgress:
    stage: PublicStage
    progress: float | None


class ProgressTracker:
    """Best-effort monotonic progress per public stage."""

    def __init__(self) -> None:
        self._last_progress: dict[PublicStage, float] = {}

    def update(self, stage: str | PublicStage, progress: float | int | None) -> StageProgress:
        public_stage = to_public_stage(stage)
        normalized = normalize_progress(progress)

        if normalized is None:
            return StageProgress(stage=public_stage, progress=None)

        prev = self._last_progress.get(public_stage)
        if prev is not None and normalized < prev:
            normalized = prev

        self._last_progress[public_stage] = normalized
        return StageProgress(stage=public_stage, progress=normalized)
