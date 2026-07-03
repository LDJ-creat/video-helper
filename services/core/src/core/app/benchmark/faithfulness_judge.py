from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Protocol


class FaithfulnessJudgeProvider(Protocol):
	def generate_json(self, task_name: str, input_dict: dict, *, max_tokens: int | None = None) -> dict: ...


def _env_int(name: str, default: int) -> int:
	raw = os.environ.get(name)
	if raw is None:
		return default
	try:
		return int(raw)
	except ValueError:
		return default


def _env_float(name: str, default: float) -> float:
	raw = os.environ.get(name)
	if raw is None:
		return default
	try:
		return float(raw)
	except ValueError:
		return default


def load_transcript_segments(*, data_dir: Path, project_id: str, job_id: str) -> list[dict[str, Any]]:
	path = data_dir.resolve() / project_id / "artifacts" / job_id / "transcript.json"
	if path.exists():
		try:
			obj = json.loads(path.read_text(encoding="utf-8"))
			if isinstance(obj, dict) and isinstance(obj.get("segments"), list):
				return [s for s in obj["segments"] if isinstance(s, dict)]
		except (OSError, json.JSONDecodeError):
			pass
	return []


def extract_transcript_window(*, segments: list[Mapping[str, Any]], start_ms: int, end_ms: int) -> str:
	parts: list[str] = []
	for seg in segments:
		if not isinstance(seg, dict):
			continue
		s = seg.get("startMs")
		e = seg.get("endMs")
		text = seg.get("text")
		if not isinstance(s, int) or not isinstance(e, int) or not isinstance(text, str):
			continue
		if e < start_ms or s > end_ms:
			continue
		parts.append(text.strip())
	return "\n".join(p for p in parts if p)


def collect_highlights(result: Mapping[str, Any]) -> list[dict[str, Any]]:
	out: list[dict[str, Any]] = []
	blocks = result.get("contentBlocks")
	if not isinstance(blocks, list):
		return out
	for block in blocks:
		if not isinstance(block, dict):
			continue
		block_id = block.get("blockId")
		highlights = block.get("highlights")
		if not isinstance(highlights, list):
			continue
		for h in highlights:
			if not isinstance(h, dict):
				continue
			text = h.get("text")
			start_ms = h.get("startMs")
			end_ms = h.get("endMs")
			if not isinstance(text, str) or not isinstance(start_ms, int) or not isinstance(end_ms, int):
				continue
			out.append(
				{
					"highlightId": h.get("highlightId"),
					"blockId": block_id,
					"text": text,
					"startMs": start_ms,
					"endMs": end_ms,
				}
			)
	return out


def sample_highlights_deterministic(
	highlights: list[dict[str, Any]],
	*,
	job_id: str,
	profile: str | None,
	sample_size: int,
	full: bool,
) -> list[dict[str, Any]]:
	if full or sample_size <= 0 or len(highlights) <= sample_size:
		return list(highlights)
	seed_src = f"{job_id}:{profile or 'default'}"
	seed = int(hashlib.sha256(seed_src.encode("utf-8")).hexdigest()[:8], 16)
	order = list(range(len(highlights)))
	order.sort(key=lambda i: int(hashlib.sha256(f"{seed}:{i}".encode()).hexdigest(), 16))
	chosen = sorted(order[:sample_size])
	return [highlights[i] for i in chosen]


def _judge_one(
	*,
	provider: FaithfulnessJudgeProvider,
	highlight: Mapping[str, Any],
	evidence_window: str,
) -> dict[str, Any]:
	system = (
		"You judge whether a video highlight summary is faithful to transcript evidence. "
		"Return ONLY JSON: supported(boolean), score(number 0..1), evidenceQuote(string), reason(string). "
		"supported=true only if the highlight is directly supported by the evidence window."
	)
	payload = {
		"highlight": str(highlight.get("text") or ""),
		"timeRange": {"startMs": highlight.get("startMs"), "endMs": highlight.get("endMs")},
		"evidenceWindow": evidence_window,
	}
	messages = [
		{"role": "system", "content": system},
		{"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
	]
	try:
		res = provider.generate_json("benchmark_faithfulness_judge", {"messages": messages}, max_tokens=512)
	except Exception as exc:
		return {"supported": False, "score": 0.0, "error": str(exc)}

	if not isinstance(res, dict):
		return {"supported": False, "score": 0.0, "error": "invalid_llm_output"}

	supported = bool(res.get("supported"))
	score_raw = res.get("score")
	score = float(score_raw) if isinstance(score_raw, (int, float)) else (1.0 if supported else 0.0)
	score = max(0.0, min(1.0, score))
	quote = res.get("evidenceQuote") if isinstance(res.get("evidenceQuote"), str) else ""
	reason = res.get("reason") if isinstance(res.get("reason"), str) else ""
	return {
		"supported": supported,
		"score": round(score, 4),
		"evidenceQuote": quote,
		"reason": reason,
		"highlightId": highlight.get("highlightId"),
		"blockId": highlight.get("blockId"),
	}


def judge_highlight_faithfulness(
	*,
	result: Mapping[str, Any],
	segments: list[dict[str, Any]],
	provider: FaithfulnessJudgeProvider,
	job_id: str,
	profile: str | None = None,
	sample_size: int | None = None,
	full: bool = False,
	supported_rate_min: float | None = None,
	mean_score_min: float | None = None,
) -> dict[str, Any]:
	highlights = collect_highlights(result)
	if not highlights:
		return {
			"passed": True,
			"enabled": True,
			"sampleSize": 0,
			"supportedRate": None,
			"meanScore": None,
			"samples": [],
			"skipped": True,
			"reason": "no_highlights",
		}

	n = sample_size if sample_size is not None else _env_int("BENCHMARK_JUDGE_SAMPLE_SIZE", 10)
	chosen = sample_highlights_deterministic(highlights, job_id=job_id, profile=profile, sample_size=n, full=full)
	samples: list[dict[str, Any]] = []
	for h in chosen:
		window = extract_transcript_window(
			segments=segments,
			start_ms=int(h["startMs"]),
			end_ms=int(h["endMs"]),
		)
		samples.append(_judge_one(provider=provider, highlight=h, evidence_window=window))

	supported_count = sum(1 for s in samples if s.get("supported") is True)
	scores = [float(s["score"]) for s in samples if isinstance(s.get("score"), (int, float))]
	supported_rate = round(supported_count / len(samples), 4) if samples else None
	mean_score = round(sum(scores) / len(scores), 4) if scores else None

	rate_min = supported_rate_min if supported_rate_min is not None else _env_float("BENCHMARK_JUDGE_SUPPORTED_RATE_MIN", 0.8)
	score_min = mean_score_min if mean_score_min is not None else _env_float("BENCHMARK_JUDGE_MEAN_SCORE_MIN", 0.75)
	passed = True
	if supported_rate is not None and supported_rate < rate_min:
		passed = False
	if mean_score is not None and mean_score < score_min:
		passed = False

	return {
		"passed": passed,
		"enabled": True,
		"sampleSize": len(samples),
		"supportedRate": supported_rate,
		"meanScore": mean_score,
		"samples": samples,
	}
