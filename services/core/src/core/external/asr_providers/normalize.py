from __future__ import annotations

from typing import Any

from core.external.asr_faster_whisper import AsrSegment


def segments_from_dashscope_transcription(data: dict[str, Any]) -> tuple[list[AsrSegment], str | None]:
	segments: list[AsrSegment] = []
	language: str | None = None
	transcripts = data.get("transcripts")
	if not isinstance(transcripts, list):
		return segments, language
	for ch in transcripts:
		if not isinstance(ch, dict):
			continue
		sentences = ch.get("sentences")
		if not isinstance(sentences, list):
			continue
		for sent in sentences:
			if not isinstance(sent, dict):
				continue
			text = sent.get("text")
			if not isinstance(text, str):
				continue
			text = text.strip()
			if not text:
				continue
			try:
				start_ms = max(0, int(sent.get("begin_time", 0)))
				end_ms = max(start_ms + 1, int(sent.get("end_time", start_ms + 1)))
			except (TypeError, ValueError):
				continue
			segments.append(AsrSegment(start_ms=start_ms, end_ms=end_ms, text=text))
	return segments, language


def segments_from_openai_verbose(data: dict[str, Any]) -> tuple[list[AsrSegment], str | None]:
	segments: list[AsrSegment] = []
	language = data.get("language")
	if not isinstance(language, str):
		language = None
	raw_segments = data.get("segments")
	if not isinstance(raw_segments, list):
		return segments, language
	for seg in raw_segments:
		if not isinstance(seg, dict):
			continue
		text = seg.get("text")
		if not isinstance(text, str):
			continue
		text = text.strip()
		if not text:
			continue
		try:
			start_ms = max(0, int(float(seg.get("start", 0)) * 1000))
			end_ms = max(start_ms + 1, int(float(seg.get("end", 0)) * 1000))
		except (TypeError, ValueError):
			continue
		segments.append(AsrSegment(start_ms=start_ms, end_ms=end_ms, text=text))
	return segments, language


def segments_from_volcengine_result(data: dict[str, Any]) -> tuple[list[AsrSegment], str | None]:
	segments: list[AsrSegment] = []
	result = data.get("result")
	if not isinstance(result, dict):
		return segments, None
	utterances = result.get("utterances")
	if not isinstance(utterances, list):
		text = result.get("text")
		if isinstance(text, str) and text.strip():
			segments.append(AsrSegment(start_ms=0, end_ms=1, text=text.strip()))
		return segments, None
	for utt in utterances:
		if not isinstance(utt, dict):
			continue
		text = utt.get("text")
		if not isinstance(text, str):
			continue
		text = text.strip()
		if not text:
			continue
		try:
			start_ms = max(0, int(utt.get("start_time", 0)))
			end_ms = max(start_ms + 1, int(utt.get("end_time", start_ms + 1)))
		except (TypeError, ValueError):
			continue
		segments.append(AsrSegment(start_ms=start_ms, end_ms=end_ms, text=text))
	return segments, None
