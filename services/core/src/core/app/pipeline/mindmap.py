from __future__ import annotations


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
