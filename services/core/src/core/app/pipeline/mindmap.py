from __future__ import annotations

import hashlib
import os

from core.app.pipeline.analyze_provider import AnalyzeError, AnalyzeProvider, llm_provider_from_env
from core.contracts.error_codes import ErrorCode


def build_mindmap(*, chapters: list[dict], highlights: list[dict]) -> dict:
	"""Build an MVP mindmap graph.

	Schema (MVP):
	- node: {id, type, label, chapterId?, position?, data?}
	- edge: {id, source, target, label?}

	We intentionally keep it as plain dicts to match Result schema and allow FE evolution.
	"""

	nodes: list[dict] = []
	edges: list[dict] = []

	root_id = "node_root"
	nodes.append({"id": root_id, "type": "root", "label": "Video"})

	# Group highlights by chapter for a simple hierarchy.
	hl_by_ch: dict[str, list[dict]] = {}
	for hl in highlights or []:
		if not isinstance(hl, dict):
			continue
		cid = hl.get("chapterId")
		if isinstance(cid, str) and cid:
			hl_by_ch.setdefault(cid, []).append(hl)

	for idx, ch in enumerate(chapters or []):
		if not isinstance(ch, dict):
			continue
		cid = ch.get("chapterId")
		if not isinstance(cid, str) or not cid:
			raise ValueError("chapterId must be non-empty")

		title = ch.get("title")
		label = title.strip() if isinstance(title, str) and title.strip() else f"Chapter {idx + 1}"

		chapter_node_id = f"node_ch_{cid}"
		nodes.append({"id": chapter_node_id, "type": "chapter", "label": label, "chapterId": cid})
		edges.append({"id": f"edge_root_{cid}", "source": root_id, "target": chapter_node_id})

		for hl_idx, hl in enumerate(hl_by_ch.get(cid, [])[:6]):
			text = hl.get("text")
			if not isinstance(text, str) or not text.strip():
				continue
			hl_node_id = f"node_hl_{cid}_{hl_idx}"
			nodes.append({"id": hl_node_id, "type": "highlight", "label": text.strip(), "chapterId": cid})
			edges.append({"id": f"edge_{chapter_node_id}_{hl_idx}", "source": chapter_node_id, "target": hl_node_id})

	return {"nodes": nodes, "edges": edges}


def _env_bool(name: str, default: bool = False) -> bool:
	raw = (os.environ.get(name) or "").strip().lower()
	if raw in {"1", "true", "yes", "y", "on"}:
		return True
	if raw in {"0", "false", "no", "n", "off"}:
		return False
	return default


def _stable_id(prefix: str, text: str) -> str:
	h = hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()[:10]
	return f"{prefix}_{h}"


def validate_mindmap_graph(mindmap: dict) -> None:
	nodes = mindmap.get("nodes")
	edges = mindmap.get("edges")
	if not isinstance(nodes, list) or not isinstance(edges, list):
		raise AnalyzeError(code=ErrorCode.JOB_STAGE_FAILED, message="Invalid mindmap", details={"reason": "invalid_llm_output", "task": "mindmap"})

	ids: list[str] = []
	for n in nodes:
		if not isinstance(n, dict) or not isinstance(n.get("id"), str) or not n.get("id"):
			raise AnalyzeError(code=ErrorCode.JOB_STAGE_FAILED, message="Invalid mindmap", details={"reason": "invalid_llm_output", "task": "mindmap"})
		ids.append(n["id"])
	if len(ids) != len(set(ids)):
		raise AnalyzeError(code=ErrorCode.JOB_STAGE_FAILED, message="Invalid mindmap", details={"reason": "invalid_llm_output", "task": "mindmap"})

	ids_set = set(ids)
	for e in edges:
		if not isinstance(e, dict):
			raise AnalyzeError(code=ErrorCode.JOB_STAGE_FAILED, message="Invalid mindmap", details={"reason": "invalid_llm_output", "task": "mindmap"})
		s = e.get("source")
		t = e.get("target")
		if not isinstance(s, str) or not isinstance(t, str) or s not in ids_set or t not in ids_set:
			raise AnalyzeError(code=ErrorCode.JOB_STAGE_FAILED, message="Invalid mindmap", details={"reason": "invalid_llm_output", "task": "mindmap"})


def build_mindmap_llm(*, chapters: list[dict], highlights: list[dict], provider: AnalyzeProvider) -> dict:
	"""Generate a mindmap via LLM as chapter topics, then build a renderable graph.

	Internal LLM schema:
	{
	  "chapters": [
	    {"chapterId": "ch_1", "topics": [{"label": "..."}, ...]},
	    ...
	  ]
	}
	"""

	# Group highlights by chapter for prompt compactness.
	hl_by_ch: dict[str, list[str]] = {}
	for hl in highlights or []:
		if not isinstance(hl, dict):
			continue
		cid = hl.get("chapterId")
		text = hl.get("text")
		if isinstance(cid, str) and cid and isinstance(text, str) and text.strip():
			hl_by_ch.setdefault(cid, []).append(text.strip())

	chapter_ids: list[str] = []
	chapter_payload: list[dict] = []
	for idx, ch in enumerate(chapters or []):
		if not isinstance(ch, dict):
			continue
		cid = ch.get("chapterId")
		if not isinstance(cid, str) or not cid:
			raise ValueError("chapterId must be non-empty")
		chapter_ids.append(cid)
		title = ch.get("title")
		chapter_payload.append(
			{
				"chapterId": cid,
				"idx": int(ch.get("idx") if isinstance(ch.get("idx"), int) else idx),
				"title": title if isinstance(title, str) else "",
				"highlights": (hl_by_ch.get(cid) or [])[:6],
			}
		)

	system = (
		"You create a mindmap plan. Return ONLY a JSON object. "
		"Schema: {chapters: [{chapterId: string, topics: [{label: string}]}]}. "
		"Constraints: chapterId must match input; keep topics concise." 
	)
	user = {"task": "mindmap", "chapters": chapter_payload, "maxTopicsPerChapter": 4}

	res = provider.generate_json(
		"mindmap",
		{
			"messages": [
				{"role": "system", "content": system},
				{"role": "user", "content": json_dumps_compact(user)},
			],
		},
	)

	chapters_out = res.get("chapters") if isinstance(res, dict) else None
	if not isinstance(chapters_out, list):
		details = {"reason": "invalid_llm_output", "task": "mindmap"}
		if isinstance(res, dict):
			details["outputKeys"] = sorted([str(k) for k in res.keys()])
		else:
			details["outputType"] = type(res).__name__
		raise AnalyzeError(code=ErrorCode.JOB_STAGE_FAILED, message="Invalid LLM output", details=details)

	# Build deterministic graph
	nodes: list[dict] = []
	edges: list[dict] = []
	root_id = "node_root"
	nodes.append({"id": root_id, "type": "root", "label": "Video"})

	# Index topics by chapterId
	topics_by_cid: dict[str, list[str]] = {cid: [] for cid in chapter_ids}
	for ch in chapters_out:
		if not isinstance(ch, dict):
			continue
		cid = ch.get("chapterId")
		topics = ch.get("topics")
		if not isinstance(cid, str) or cid not in topics_by_cid:
			raise AnalyzeError(code=ErrorCode.JOB_STAGE_FAILED, message="Invalid LLM output", details={"reason": "invalid_llm_output", "task": "mindmap", "badField": "chapterId"})
		if not isinstance(topics, list):
			raise AnalyzeError(code=ErrorCode.JOB_STAGE_FAILED, message="Invalid LLM output", details={"reason": "invalid_llm_output", "task": "mindmap", "badField": "topics"})
		labels: list[str] = []
		seen: set[str] = set()
		for t in topics[:4]:
			if not isinstance(t, dict):
				continue
			lab = t.get("label")
			if isinstance(lab, str) and lab.strip():
				val = lab.strip()
				key = val.lower()
				if key in seen:
					continue
				seen.add(key)
				labels.append(val)
		topics_by_cid[cid] = labels

	for idx, ch in enumerate(chapters or []):
		if not isinstance(ch, dict):
			continue
		cid = ch.get("chapterId")
		if not isinstance(cid, str) or not cid:
			continue
		title = ch.get("title")
		label = title.strip() if isinstance(title, str) and title.strip() else f"Chapter {idx + 1}"
		chapter_node_id = f"node_ch_{cid}"
		nodes.append({"id": chapter_node_id, "type": "chapter", "label": label, "chapterId": cid})
		edges.append({"id": f"edge_root_{cid}", "source": root_id, "target": chapter_node_id})

		for t_idx, topic in enumerate(topics_by_cid.get(cid) or []):
			topic_id = _stable_id(f"node_topic_{cid}", topic)
			nodes.append({"id": topic_id, "type": "topic", "label": topic, "chapterId": cid})
			edges.append({"id": _stable_id(f"edge_{chapter_node_id}_{t_idx}", topic_id), "source": chapter_node_id, "target": topic_id})

	mm = {"nodes": nodes, "edges": edges}
	validate_mindmap_graph(mm)
	return mm


def generate_mindmap(*, chapters: list[dict], highlights: list[dict], llm_transport: object | None = None) -> dict:
	provider_kind = (os.environ.get("ANALYZE_PROVIDER") or "").strip().lower()
	allow_fallback = _env_bool("ANALYZE_ALLOW_RULES_FALLBACK", False)

	if provider_kind != "llm":
		return build_mindmap(chapters=chapters, highlights=highlights)

	try:
		provider = llm_provider_from_env(transport=llm_transport)  # type: ignore[arg-type]
		return build_mindmap_llm(chapters=chapters, highlights=highlights, provider=provider)
	except AnalyzeError:
		if allow_fallback:
			return build_mindmap(chapters=chapters, highlights=highlights)
		raise


def json_dumps_compact(obj: object) -> str:
	import json

	return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
