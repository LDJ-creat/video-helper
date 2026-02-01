from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any

from .progress import normalize_progress
from .stages import PublicStage, to_public_stage


class SseEventType(str, Enum):
    HEARTBEAT = "heartbeat"
    PROGRESS = "progress"
    LOG = "log"
    STATE = "state"


@dataclass(frozen=True, slots=True)
class SseEventPayload:
    # Required
    eventId: str
    tsMs: int
    jobId: str
    projectId: str
    stage: str

    # Optional
    progress: float | None = None
    message: str | None = None


def build_payload(
    *,
    event_id: str,
    job_id: str,
    project_id: str,
    stage: str | PublicStage,
    progress: float | int | None = None,
    message: str | None = None,
    ts_ms: int | None = None,
) -> SseEventPayload:
    ts = int(time.time() * 1000) if ts_ms is None else int(ts_ms)
    public_stage = to_public_stage(stage)
    normalized = normalize_progress(progress)

    return SseEventPayload(
        eventId=str(event_id),
        tsMs=ts,
        jobId=str(job_id),
        projectId=str(project_id),
        stage=public_stage.value,
        progress=normalized,
        message=message,
    )


def encode_sse_data(payload: SseEventPayload) -> str:
    """JSON encode with frozen camelCase keys and no extra fields."""

    data: dict[str, Any] = asdict(payload)
    # Drop null optionals for compactness (contract allows omission)
    if data.get("progress") is None:
        data.pop("progress", None)
    if data.get("message") is None:
        data.pop("message", None)

    return json.dumps(data, separators=(",", ":"), ensure_ascii=False)


def format_sse_event(*, event_type: SseEventType, event_id: str, payload: SseEventPayload) -> str:
    data = encode_sse_data(payload)
    return f"event: {event_type.value}\nid: {event_id}\ndata: {data}\n\n"
