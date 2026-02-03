from __future__ import annotations

import uuid


def build_highlights(
	*,
	transcript: dict,
	chapters: list[dict],
	max_items_per_chapter: int = 3,
) -> list[dict]:
	"""Build per-chapter highlights.

	Output conforms to core.schemas.results.HighlightDTO shape:
	  {highlightId, chapterId, idx, text, timeMs?}

	MVP heuristic:
	- pick up to N transcript segments per chapter (evenly sampled)
	- fallback to chapter title when transcript is missing
	"""

	max_items_per_chapter = max(1, int(max_items_per_chapter))

	segments = transcript.get("segments")
	if not isinstance(segments, list):
		segments = []

	out: list[dict] = []

	for ch_idx, ch in enumerate(chapters):
		chapter_id = ch.get("chapterId")
		start_ms = ch.get("startMs")
		end_ms = ch.get("endMs")

		if not isinstance(chapter_id, str) or not chapter_id:
			raise ValueError("chapterId must be non-empty")
		if not isinstance(start_ms, int) or not isinstance(end_ms, int) or end_ms <= start_ms:
			raise ValueError("invalid chapter startMs/endMs")

		in_range: list[dict] = []
		for seg in segments:
			if not isinstance(seg, dict):
				continue
			ss = seg.get("startMs")
			ee = seg.get("endMs")
			if not isinstance(ss, int) or not isinstance(ee, int):
				continue
			# overlap test
			if ee <= start_ms or ss >= end_ms:
				continue
			in_range.append(seg)

		items: list[dict] = []
		if in_range:
			# Evenly sample segments so long chapters still get coverage.
			count = min(max_items_per_chapter, len(in_range))
			for i in range(count):
				pos = int(round((i + 1) * (len(in_range) + 1) / (count + 1))) - 1
				pos = max(0, min(len(in_range) - 1, pos))
				seg = in_range[pos]
				text = seg.get("text")
				if not isinstance(text, str) or not text.strip():
					text = f"Chapter {ch_idx + 1}"
				time_ms = seg.get("startMs") if isinstance(seg.get("startMs"), int) else None
				items.append({"text": text.strip(), "timeMs": time_ms})
		else:
			# Fallback: at least one highlight per chapter.
			title = ch.get("title")
			text = title.strip() if isinstance(title, str) and title.strip() else f"Chapter {ch_idx + 1}"
			items.append({"text": text, "timeMs": start_ms})

		for item_idx, item in enumerate(items):
			out.append(
				{
					"highlightId": str(uuid.uuid4()),
					"chapterId": chapter_id,
					"idx": int(item_idx),
					"text": str(item["text"]),
					"timeMs": item.get("timeMs"),
				}
			)

	return out
