from __future__ import annotations

from dataclasses import dataclass

from core.contracts.error_codes import ErrorCode


@dataclass(frozen=True)
class Chapter:
    chapter_id: str
    start_ms: int
    end_ms: int
    title: str
    summary: str

    def to_dict(self) -> dict:
        return {
            "chapterId": self.chapter_id,
            "startMs": self.start_ms,
            "endMs": self.end_ms,
            "title": self.title,
            "summary": self.summary,
        }


def build_chapters_from_transcript(transcript: dict) -> dict:
    segments = transcript.get("segments")
    if not isinstance(segments, list) or not segments:
        raise ValueError("transcript.segments must be a non-empty list")

    duration_ms = transcript.get("durationMs")
    if not isinstance(duration_ms, int) or duration_ms <= 0:
        # best-effort derive from last segment
        last = segments[-1]
        duration_ms = int(last.get("endMs") or 0)
        if duration_ms <= 0:
            duration_ms = 60_000

    # MVP: 3 chapters evenly spaced.
    count = 3
    step = max(1, duration_ms // count)

    chapters: list[Chapter] = []
    for idx in range(count):
        start = idx * step
        end = duration_ms if idx == count - 1 else (idx + 1) * step
        if end <= start:
            continue
        chapters.append(
            Chapter(
                chapter_id=f"ch_{idx + 1}",
                start_ms=int(start),
                end_ms=int(end),
                title=f"Chapter {idx + 1}",
                summary="",
            )
        )

    validate_chapters([c.to_dict() for c in chapters])

    return {
        "version": 1,
        "chapters": [c.to_dict() for c in chapters],
        "unit": "ms",
    }


def validate_chapters(chapters: list[dict]) -> None:
    if not chapters:
        raise ValueError("chapters must be non-empty")

    last_end = -1
    last_start = -1
    seen_ids: set[str] = set()

    for idx, ch in enumerate(chapters):
        cid = ch.get("chapterId")
        if not isinstance(cid, str) or not cid:
            raise ValueError("chapterId must be non-empty")
        if cid in seen_ids:
            raise ValueError("chapterId must be unique")
        seen_ids.add(cid)

        start = ch.get("startMs")
        end = ch.get("endMs")
        if not isinstance(start, int) or not isinstance(end, int):
            raise ValueError("startMs/endMs must be int")
        if start < 0 or end < 0:
            raise ValueError("startMs/endMs must be >= 0")
        if start >= end:
            raise ValueError("startMs must be < endMs")

        # stable order: ensure monotonic increasing by startMs
        if idx > 0 and start < last_start:
            raise ValueError("chapters must be sorted by startMs")
        # non-overlap
        if idx > 0 and start < last_end:
            raise ValueError("chapters must not overlap")

        last_start = start
        last_end = end


def build_chapter_error(*, message: str, details: dict | None = None) -> dict:
    return {
        "code": ErrorCode.JOB_STAGE_FAILED,
        "message": message,
        "details": details or {},
    }
