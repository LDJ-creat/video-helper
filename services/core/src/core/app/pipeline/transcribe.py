from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class TranscriptSegment:
    start_ms: int
    end_ms: int
    text: str

    def to_dict(self) -> dict:
        return {"startMs": self.start_ms, "endMs": self.end_ms, "text": self.text}


def build_placeholder_transcript(*, duration_ms: int, segment_ms: int = 5_000) -> dict:
    """MVP transcript generator.

    Produces deterministic, ms-based segments suitable for downstream segmentation.
    """

    duration_ms = max(1, int(duration_ms))
    segment_ms = max(250, int(segment_ms))

    segments: list[TranscriptSegment] = []
    count = int(math.ceil(duration_ms / segment_ms))

    for idx in range(count):
        start = idx * segment_ms
        end = min(duration_ms, (idx + 1) * segment_ms)
        if end <= start:
            continue
        segments.append(
            TranscriptSegment(
                start_ms=start,
                end_ms=end,
                text=f"Segment {idx + 1}",
            )
        )

    return {
        "version": 1,
        "segments": [s.to_dict() for s in segments],
        "durationMs": duration_ms,
        "unit": "ms",
    }
