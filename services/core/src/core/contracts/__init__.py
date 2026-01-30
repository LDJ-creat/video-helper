"""Frozen external contracts (DTO/enums) shared across API/SSE.

Keep these modules dependency-free and stable: other stories import them.
"""

__all__ = [
	"error_codes",
	"error_envelope",
	"primitives",
	"progress",
	"stages",
]
