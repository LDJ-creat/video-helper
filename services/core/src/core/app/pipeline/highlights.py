from __future__ import annotations

import os

from core.app.pipeline.analyze_provider import AnalyzeError, AnalyzeProvider, llm_provider_for_jobs
from core.contracts.error_codes import ErrorCode


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
					"highlightId": f"h_{chapter_id}_{int(item_idx)}",
					"chapterId": chapter_id,
					"idx": int(item_idx),
					"text": str(item["text"]),
					"timeMs": item.get("timeMs"),
				}
			)

	return out


def _env_bool(name: str, default: bool = False) -> bool:
	raw = (os.environ.get(name) or "").strip().lower()
	if raw in {"1", "true", "yes", "y", "on"}:
		return True
	if raw in {"0", "false", "no", "n", "off"}:
		return False
	return default


def _chapter_transcript_text(*, transcript: dict, start_ms: int, end_ms: int, max_chars: int) -> str:
	segments = transcript.get("segments")
	if not isinstance(segments, list):
		return ""

	parts: list[str] = []
	for seg in segments:
		if not isinstance(seg, dict):
			continue
		ss = seg.get("startMs")
		ee = seg.get("endMs")
		if not isinstance(ss, int) or not isinstance(ee, int):
			continue
		if ee <= start_ms or ss >= end_ms:
			continue
		text = seg.get("text")
		if isinstance(text, str) and text.strip():
			parts.append(text.strip())
		if sum(len(p) + 1 for p in parts) >= max_chars:
			break

	out = " ".join(parts).strip()
	if len(out) > max_chars:
		out = out[:max_chars].rstrip()
	return out


def build_highlights_llm(*, transcript: dict, chapters: list[dict], provider: AnalyzeProvider) -> list[dict]:
	"""Generate per-chapter highlights using an LLM provider.

	Internal output schema (LLM):
	{
	  "chapters": [
	    {"chapterId": "ch_1", "items": [{"text": "...", "timeMs": 1234 | null}, ...]},
	    ...
	  ]
	}
	"""

	chapter_ids: list[str] = []
	chapter_payload: list[dict] = []
	for idx, ch in enumerate(chapters):
		cid = ch.get("chapterId")
		start_ms = ch.get("startMs")
		end_ms = ch.get("endMs")
		if not isinstance(cid, str) or not cid:
			raise ValueError("chapterId must be non-empty")
		if not isinstance(start_ms, int) or not isinstance(end_ms, int) or end_ms <= start_ms:
			raise ValueError("invalid chapter startMs/endMs")
		chapter_ids.append(cid)
		chapter_payload.append(
			{
				"chapterId": cid,
				"idx": int(ch.get("idx") if isinstance(ch.get("idx"), int) else idx),
				"title": ch.get("title") if isinstance(ch.get("title"), str) else "",
				"startMs": start_ms,
				"endMs": end_ms,
				"transcript": _chapter_transcript_text(transcript=transcript, start_ms=start_ms, end_ms=end_ms, max_chars=2500),
			}
		)

	system = (
		"You are a video highlights generator. Return ONLY a JSON object. "
		"Schema: {chapters: [{chapterId: string, items: [{text: string, timeMs?: integer|null}]}]}. "
		"Constraints: chapterId must match one of the provided chapters exactly; no extra keys." 
	)
	user = {
		"task": "highlights",
		"maxItemsPerChapter": 3,
		"chapters": chapter_payload,
	}

	res = provider.generate_json(
		"highlights",
		{
			"messages": [
				{"role": "system", "content": system},
				{"role": "user", "content": json_dumps_compact(user)},
			],
		},
	)

	chapters_out = res.get("chapters") if isinstance(res, dict) else None
	if not isinstance(chapters_out, list):
		details = {"reason": "invalid_llm_output", "task": "highlights"}
		if isinstance(res, dict):
			details["outputKeys"] = sorted([str(k) for k in res.keys()])
		else:
			details["outputType"] = type(res).__name__
		raise AnalyzeError(code=ErrorCode.JOB_STAGE_FAILED, message="Invalid LLM output", details=details)

	by_id: dict[str, list[dict]] = {cid: [] for cid in chapter_ids}
	for item in chapters_out:
		if not isinstance(item, dict):
			continue
		cid = item.get("chapterId")
		items = item.get("items")
		if not isinstance(cid, str) or cid not in by_id:
			raise AnalyzeError(code=ErrorCode.JOB_STAGE_FAILED, message="Invalid LLM output", details={"reason": "invalid_llm_output", "task": "highlights", "badField": "chapterId"})
		if not isinstance(items, list):
			raise AnalyzeError(code=ErrorCode.JOB_STAGE_FAILED, message="Invalid LLM output", details={"reason": "invalid_llm_output", "task": "highlights", "badField": "items"})
		for it in items[:3]:
			if not isinstance(it, dict):
				continue
			text = it.get("text")
			if not isinstance(text, str) or not text.strip():
				continue
			time_ms = it.get("timeMs")
			by_id[cid].append({"text": text.strip(), "timeMs": time_ms})

	# Enforce timeMs within chapter range; if invalid, set to None.
	ranges: dict[str, tuple[int, int]] = {}
	for ch in chapters:
		cid = ch.get("chapterId")
		if isinstance(cid, str) and isinstance(ch.get("startMs"), int) and isinstance(ch.get("endMs"), int):
			ranges[cid] = (int(ch["startMs"]), int(ch["endMs"]))

	out: list[dict] = []
	for cid in chapter_ids:
		items = by_id.get(cid) or []
		if not items:
			# Last-resort: keep pipeline moving; caller may choose to fail instead.
			items = [{"text": cid, "timeMs": None}]
		start_ms, end_ms = ranges.get(cid, (0, 0))
		for idx, it in enumerate(items):
			tm = it.get("timeMs")
			if isinstance(tm, int) and (tm < start_ms or tm >= end_ms):
				tm = None
			elif tm is None:
				tm = None
			elif not isinstance(tm, int):
				tm = None
			out.append({"highlightId": f"h_{cid}_{int(idx)}", "chapterId": cid, "idx": int(idx), "text": it["text"], "timeMs": tm})

	return out


def generate_highlights(*, transcript: dict, chapters: list[dict], llm_transport: object | None = None) -> list[dict]:
	allow_fallback_env = _env_bool("ANALYZE_ALLOW_RULES_FALLBACK", False)

	try:
		provider = llm_provider_for_jobs(transport=llm_transport)  # type: ignore[arg-type]
		if provider is None:
			return build_highlights(transcript=transcript, chapters=chapters)
		return build_highlights_llm(transcript=transcript, chapters=chapters, provider=provider)
	except AnalyzeError:
		if allow_fallback_env:
			return build_highlights(transcript=transcript, chapters=chapters)
		raise


def json_dumps_compact(obj: object) -> str:
	import json

	return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
