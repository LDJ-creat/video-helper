from __future__ import annotations

from enum import Enum
from types import MappingProxyType


class PublicStage(str, Enum):
    """Externally visible stable stage names.

    MUST remain stable once published.
    """

    INGEST = "ingest"
    TRANSCRIBE = "transcribe"
    ANALYZE = "analyze"
    ASSEMBLE_RESULT = "assemble_result"
    EXTRACT_KEYFRAMES = "extract_keyframes"


PUBLIC_STAGES: tuple[PublicStage, ...] = tuple(PublicStage)


_INTERNAL_STAGE_TO_PUBLIC: dict[str, PublicStage] = {
    # Identity mapping for already-public stages
    s.value: s for s in PublicStage
}

# Examples of finer-grained internal stages mapping to public stages.
_INTERNAL_STAGE_TO_PUBLIC.update(
    {
        "download": PublicStage.INGEST,
        "fetch_source": PublicStage.INGEST,
        "upload": PublicStage.INGEST,
        "decode": PublicStage.INGEST,
        "speech_to_text": PublicStage.TRANSCRIBE,
        "plan": PublicStage.ANALYZE,
        "highlights": PublicStage.ANALYZE,
        "mindmap": PublicStage.ANALYZE,
        "keyframes": PublicStage.EXTRACT_KEYFRAMES,
    }
)

# Exported frozen mapping table for other modules/docs.
INTERNAL_STAGE_TO_PUBLIC_STAGE = MappingProxyType(_INTERNAL_STAGE_TO_PUBLIC)


def to_public_stage(internal_stage: str | PublicStage) -> PublicStage:
    """Map internal stage identifier to a stable external stage."""

    if isinstance(internal_stage, PublicStage):
        return internal_stage

    internal_stage = internal_stage.strip()
    if not internal_stage:
        raise ValueError("internal_stage must be non-empty")

    # Exact match first
    mapped = _INTERNAL_STAGE_TO_PUBLIC.get(internal_stage)
    if mapped is not None:
        return mapped

    # Prefix match (best-effort): e.g. "ingest:download" → "ingest"
    for public in PublicStage:
        if internal_stage.startswith(public.value + ":"):
            return public

    raise ValueError(f"Unknown internal_stage: {internal_stage}")
