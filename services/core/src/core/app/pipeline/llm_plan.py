from __future__ import annotations

import os
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from core.app.pipeline.analyze_provider import AnalyzeError, AnalyzeProvider, llm_provider_for_jobs
from core.contracts.error_codes import ErrorCode


class PlanKeyframe(BaseModel):
    timeMs: int
    caption: str | None = None
    assetId: str | None = None
    contentUrl: str | None = None


class PlanHighlight(BaseModel):
    highlightId: str
    idx: int
    text: str
    startMs: int
    endMs: int
    # Legacy-compatible: many parts of the app/tests still use a single `keyframe`.
    keyframe: PlanKeyframe | None = None
    # Forward-compatible: allow a list as well; we normalize to keep `keyframe` in sync.
    keyframes: list[PlanKeyframe] = Field(default_factory=list)


class PlanContentBlock(BaseModel):
    blockId: str
    idx: int
    title: str = ""
    startMs: int
    endMs: int
    highlights: list[PlanHighlight] = Field(default_factory=list)


class PlanMindmapNode(BaseModel):
    id: str
    type: str = "topic"  # root | topic | detail
    label: str = ""
    level: int = 1  # 0=root, 1=topic, 2=detail
    data: dict = Field(default_factory=dict)


class PlanMindmapEdge(BaseModel):
    id: str
    source: str
    target: str
    label: str | None = None


class PlanMindmap(BaseModel):
    nodes: list[PlanMindmapNode] = Field(default_factory=list)
    edges: list[PlanMindmapEdge] = Field(default_factory=list)


class PlanOutput(BaseModel):
    schemaVersion: str
    contentBlocks: list[PlanContentBlock]
    mindmap: PlanMindmap


def _as_int(v: object) -> int | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v)
    if isinstance(v, str):
        vv = v.strip()
        if vv.isdigit() or (vv.startswith("-") and vv[1:].isdigit()):
            try:
                return int(vv)
            except ValueError:
                return None
    return None


def _normalize_plan_payload(plan: dict) -> dict:
    """Best-effort normalization for real-world LLM output.

    Some providers return near-miss keys like `id`, `timeRange`, or highlight point `timeMs`.
    We normalize into the strict PlanOutput schema and then validate.
    """

    if not isinstance(plan, dict):
        return plan

    # Canonicalize top-level keys.
    if "contentBlocks" not in plan and isinstance(plan.get("content_blocks"), list):
        plan["contentBlocks"] = plan.get("content_blocks")

    if "schemaVersion" not in plan or not isinstance(plan.get("schemaVersion"), str):
        plan["schemaVersion"] = "2026-02-06"

    blocks = plan.get("contentBlocks")
    if not isinstance(blocks, list):
        return plan

    # When blocks overlap slightly, strict validation fails. For real-world LLM output,
    # we merge overlapping blocks (keeping all highlights) and re-index blocks/highlights.
    # We also remap mindmap targetBlockId references from merged-away blocks to the kept one.
    block_id_aliases: dict[str, str] = {}

    # Normalize blocks.
    for b_i, b in enumerate(blocks):
        if not isinstance(b, dict):
            continue

        # blockId / idx
        if not isinstance(b.get("blockId"), str) or not b.get("blockId"):
            bid_raw = b.get("id")
            bid_int = _as_int(bid_raw)
            b["blockId"] = f"b{bid_int}" if bid_int is not None else f"b{b_i}"
        if not isinstance(b.get("idx"), int):
            idx_int = _as_int(b.get("idx"))
            if idx_int is None:
                idx_int = _as_int(b.get("id"))
            b["idx"] = int(idx_int) if idx_int is not None else int(b_i)

        # time range
        if (not isinstance(b.get("startMs"), int)) or (not isinstance(b.get("endMs"), int)):
            tr = b.get("timeRange")
            if isinstance(tr, dict):
                s = _as_int(tr.get("startMs"))
                e = _as_int(tr.get("endMs"))
                if s is not None:
                    b["startMs"] = int(s)
                if e is not None:
                    b["endMs"] = int(e)

        # highlights
        hls = b.get("highlights")
        if hls is None:
            b["highlights"] = []
            hls = b["highlights"]
        if not isinstance(hls, list):
            b["highlights"] = []
            hls = b["highlights"]

        b_start = _as_int(b.get("startMs")) or 0
        b_end = _as_int(b.get("endMs")) or (b_start + 1)

        for h_i, h in enumerate(hls):
            if not isinstance(h, dict):
                continue

            if not isinstance(h.get("highlightId"), str) or not h.get("highlightId"):
                hid_int = _as_int(h.get("id"))
                h["highlightId"] = f"h{b_i}_{hid_int}" if hid_int is not None else f"h{b_i}_{h_i}"
            if not isinstance(h.get("idx"), int):
                h["idx"] = int(_as_int(h.get("idx")) or _as_int(h.get("id")) or h_i)

            # text
            if not isinstance(h.get("text"), str):
                for alt in ("quote", "content", "summary", "title"):
                    if isinstance(h.get(alt), str) and h.get(alt):
                        h["text"] = h.get(alt)
                        break
                else:
                    h["text"] = ""

            # startMs/endMs + keyframes
            hs = _as_int(h.get("startMs"))
            he = _as_int(h.get("endMs"))

            # Normalize keyframe(s): keep legacy `keyframe` and optional `keyframes`.
            candidates: list[dict] = []

            kf_single = h.get("keyframe")
            if isinstance(kf_single, dict):
                candidates.append(kf_single)

            kfs = h.get("keyframes")
            if isinstance(kfs, list):
                candidates.extend([kf for kf in kfs if isinstance(kf, dict)])

            # If no explicit keyframe object but highlight provides a point time, synthesize a keyframe.
            if not candidates and "timeMs" in h:
                tm = _as_int(h.get("timeMs"))
                if tm is not None:
                    candidates.append({"timeMs": int(tm)})

            valid_kfs: list[dict] = []
            for kf in candidates:
                tm = _as_int(kf.get("timeMs"))
                if tm is None:
                    continue
                upper = max(b_start, int(b_end) - 1)
                tm2 = max(b_start, min(int(tm), upper))
                kf2: dict = {"timeMs": int(tm2)}
                for opt in ("assetId", "contentUrl", "caption"):
                    if opt in kf and (kf.get(opt) is None or isinstance(kf.get(opt), (str, int))):
                        kf2[opt] = kf.get(opt)
                valid_kfs.append(kf2)

            if valid_kfs:
                h["keyframe"] = valid_kfs[0]
                h["keyframes"] = valid_kfs
            else:
                h.pop("keyframe", None)
                h["keyframes"] = []

            # If still missing a highlight range, synthesize it around first keyframe time.
            if hs is None or he is None:
                tm = None
                kf = h.get("keyframe")
                if isinstance(kf, dict):
                    tm = _as_int(kf.get("timeMs"))
                
                if tm is None:
                    tm = _as_int(h.get("timeMs"))
                if tm is None:
                    tm = b_start
                hs = max(b_start, int(tm) - 500)
                he = min(b_end, int(tm) + 500)
                if he <= hs:
                    he = min(b_end, hs + 1)
                h["startMs"] = int(hs)
                h["endMs"] = int(he)
            else:
                h["startMs"] = int(hs)
                h["endMs"] = int(he)

            # Clamp highlight range into its block to satisfy strict validation.
            hs2 = int(_as_int(h.get("startMs")) or b_start)
            he2 = int(_as_int(h.get("endMs")) or (hs2 + 1))
            hs2 = max(b_start, hs2)
            he2 = min(b_end, he2)
            if he2 <= hs2:
                hs2 = int(b_start)
                he2 = min(int(b_end), hs2 + 1)
                if he2 <= hs2:
                    he2 = hs2 + 1
            h["startMs"] = int(hs2)
            h["endMs"] = int(he2)

    # Merge overlapping blocks by time (best-effort).
    dict_blocks: list[dict] = [b for b in blocks if isinstance(b, dict)]
    dict_blocks_sorted = sorted(
        dict_blocks,
        key=lambda b: int(_as_int(b.get("startMs")) or 0),
    )

    merged: list[dict] = []
    for b in dict_blocks_sorted:
        b_start = int(_as_int(b.get("startMs")) or 0)
        b_end = int(_as_int(b.get("endMs")) or (b_start + 1))
        if b_end <= b_start:
            b_end = b_start + 1
        b["startMs"] = int(b_start)
        b["endMs"] = int(b_end)

        if not merged:
            merged.append(b)
            continue

        last = merged[-1]
        last_start = int(_as_int(last.get("startMs")) or 0)
        last_end = int(_as_int(last.get("endMs")) or (last_start + 1))
        last["startMs"] = int(last_start)
        last["endMs"] = int(last_end)

        # Overlap -> merge into the previous block.
        if b_start < last_end:
            last["endMs"] = max(int(last_end), int(b_end))

            # Prefer existing title; fill if empty.
            if (not isinstance(last.get("title"), str)) or (not last.get("title")):
                if isinstance(b.get("title"), str):
                    last["title"] = b.get("title")

            # Merge highlights.
            lh = last.get("highlights")
            bh = b.get("highlights")
            if not isinstance(lh, list):
                lh = []
                last["highlights"] = lh
            if isinstance(bh, list):
                lh.extend([h for h in bh if isinstance(h, dict)])

            # Track blockId alias for mindmap remapping.
            last_id = last.get("blockId")
            b_id = b.get("blockId")
            if isinstance(last_id, str) and last_id and isinstance(b_id, str) and b_id and b_id != last_id:
                block_id_aliases[b_id] = last_id
        else:
            merged.append(b)

    # Re-index blocks + highlights for strict validation.
    for b_i, b in enumerate(merged):
        b["idx"] = int(b_i)

        hls = b.get("highlights")
        if not isinstance(hls, list):
            b["highlights"] = []
            continue
        hdicts = [h for h in hls if isinstance(h, dict)]
        for h_i, h in enumerate(hdicts):
            h["idx"] = int(h_i)
        b["highlights"] = hdicts

    plan["contentBlocks"] = merged

    # Normalize mindmap nodes: type/level inference, anchor id normalization.
    mindmap = plan.get("mindmap")
    if isinstance(mindmap, dict):
        nodes = mindmap.get("nodes")
        if isinstance(nodes, list):
            had_explicit_type = any(
                isinstance(n, dict) and isinstance(n.get("type"), str) and n.get("type")
                for n in nodes
            )
            for n in nodes:
                if not isinstance(n, dict):
                    continue

                # Ensure data dict exists.
                data = n.get("data")
                if not isinstance(data, dict):
                    n["data"] = {}
                    data = n["data"]

                # Normalize anchor ids.
                tb = data.get("targetBlockId")
                if isinstance(tb, int):
                    data["targetBlockId"] = f"b{tb}"
                elif isinstance(tb, str) and tb in block_id_aliases:
                    data["targetBlockId"] = block_id_aliases[tb]
                th = data.get("targetHighlightId")
                if isinstance(th, int):
                    data["targetHighlightId"] = str(th)

                # Infer type/level if missing or inconsistent.
                node_type = n.get("type")
                node_level = n.get("level")
                has_block = isinstance(data.get("targetBlockId"), str) and data.get("targetBlockId")
                has_highlight = isinstance(data.get("targetHighlightId"), str) and data.get("targetHighlightId")

                if node_type not in ("root", "topic", "detail"):
                    # Infer from data anchors.
                    if has_highlight:
                        node_type = "detail"
                    elif has_block:
                        node_type = "topic"
                    else:
                        node_type = "root"
                    n["type"] = node_type

                type_to_level = {"root": 0, "topic": 1, "detail": 2}
                if not isinstance(node_level, int) or node_level not in (0, 1, 2):
                    n["level"] = type_to_level.get(node_type, 1)

                # Ensure id is a string.
                if not isinstance(n.get("id"), str) or not n.get("id"):
                    n["id"] = f"n{nodes.index(n)}"

                # Ensure label is a string.
                if not isinstance(n.get("label"), str):
                    n["label"] = str(n.get("label", ""))

            # Near-miss normalization: when the model didn't provide explicit types at all,
            # we auto-insert a root node to make the graph renderable.
            # If the caller DID provide explicit types but forgot/removed root, keep it strict
            # and let validate_plan fail (tests rely on this).
            has_root = any(isinstance(n, dict) and n.get("type") == "root" for n in nodes)
            if nodes and (not has_root) and (not had_explicit_type):
                existing_ids = {n.get("id") for n in nodes if isinstance(n, dict) and isinstance(n.get("id"), str)}
                root_id = "n0"
                if root_id in existing_ids:
                    root_id = "n_root"
                if root_id in existing_ids:
                    i = 1
                    while f"n_root{i}" in existing_ids:
                        i += 1
                    root_id = f"n_root{i}"

                root_node = {"id": root_id, "type": "root", "label": "Video", "level": 0, "data": {}}
                nodes.append(root_node)

                edges = mindmap.get("edges")
                if not isinstance(edges, list):
                    edges = []
                    mindmap["edges"] = edges

                incoming: set[str] = set()
                for e in edges:
                    if isinstance(e, dict) and isinstance(e.get("target"), str):
                        incoming.add(e.get("target"))

                # Connect root -> all topic nodes without incoming edges.
                edge_i = len([e for e in edges if isinstance(e, dict)])
                for n in nodes:
                    if not isinstance(n, dict):
                        continue
                    nid = n.get("id")
                    if not isinstance(nid, str) or not nid or nid == root_id:
                        continue
                    if n.get("type") != "topic":
                        continue
                    if nid in incoming:
                        continue
                    edges.append({"id": f"e_auto_{edge_i}", "source": root_id, "target": nid})
                    edge_i += 1

        # Normalize edges: from/to -> source/target.
        edges = mindmap.get("edges")
        if isinstance(edges, list):
            for e_i, e in enumerate(edges):
                if not isinstance(e, dict):
                    continue
                if "source" not in e and "from" in e:
                    e["source"] = e.pop("from")
                if "target" not in e and "to" in e:
                    e["target"] = e.pop("to")
                if not isinstance(e.get("id"), str) or not e.get("id"):
                    e["id"] = f"e{e_i}"
                for k in ("source", "target"):
                    if isinstance(e.get(k), int):
                        e[k] = str(e[k])
    else:
        plan["mindmap"] = {"nodes": [], "edges": []}

    return plan


def _model_validate(cls: type[BaseModel], obj: Any) -> BaseModel:
    # Support both Pydantic v1 and v2.
    if hasattr(cls, "model_validate"):
        return cls.model_validate(obj)  # type: ignore[attr-defined]
    return cls.parse_obj(obj)  # type: ignore[attr-defined]


def _model_dump(model: BaseModel) -> dict:
    if hasattr(model, "model_dump"):
        return model.model_dump()  # type: ignore[attr-defined]
    return model.dict()  # type: ignore[attr-defined]


def validate_plan(plan: dict) -> dict:
    """Validate and normalize an LLM plan payload.

    Raises ValueError when constraints are violated.
    Returns a JSON-serializable dict.
    """

    if not isinstance(plan, dict):
        raise ValueError("plan must be an object")

    plan = _normalize_plan_payload(plan)
    parsed = _model_validate(PlanOutput, plan)
    out = _model_dump(parsed)

    blocks: list[dict] = out.get("contentBlocks") if isinstance(out.get("contentBlocks"), list) else []
    if not blocks:
        raise ValueError("contentBlocks must be non-empty")

    # Enforce contiguous block idx (0..n-1).
    sorted_by_idx = sorted(
        [b for b in blocks if isinstance(b, dict)],
        key=lambda b: int(b.get("idx") if isinstance(b.get("idx"), int) else 0),
    )
    for expected, b in enumerate(sorted_by_idx):
        idx = b.get("idx")
        if idx != expected:
            raise ValueError(f"contentBlocks block idx must be contiguous starting at 0 (expected {expected})")

    # Enforce non-overlapping time ranges (allow gaps).
    sorted_by_time = sorted(
        sorted_by_idx,
        key=lambda b: int(b.get("startMs") if isinstance(b.get("startMs"), int) else 0),
    )
    prev_end: int | None = None
    for b in sorted_by_time:
        start_ms = b.get("startMs")
        end_ms = b.get("endMs")
        if not isinstance(start_ms, int) or not isinstance(end_ms, int) or end_ms <= start_ms:
            raise ValueError("contentBlocks startMs/endMs invalid")
        if prev_end is not None and start_ms < prev_end:
            raise ValueError("contentBlocks time ranges overlap")
        prev_end = end_ms

    # Collect ids.
    block_ids: set[str] = set()
    highlight_ids: set[str] = set()

    for b in sorted_by_idx:
        block_id = b.get("blockId")
        if not isinstance(block_id, str) or not block_id:
            raise ValueError("blockId must be non-empty")
        if block_id in block_ids:
            raise ValueError("blockId must be unique")
        block_ids.add(block_id)

        start_ms = int(b["startMs"])
        end_ms = int(b["endMs"])

        hls = b.get("highlights")
        if not isinstance(hls, list):
            raise ValueError("highlights must be a list")

        hls_sorted = sorted(
            [h for h in hls if isinstance(h, dict)],
            key=lambda h: int(h.get("idx") if isinstance(h.get("idx"), int) else 0),
        )
        for expected, h in enumerate(hls_sorted):
            if h.get("idx") != expected:
                raise ValueError("highlights idx must be contiguous per block")

            hid = h.get("highlightId")
            if not isinstance(hid, str) or not hid:
                raise ValueError("highlightId must be non-empty")
            if hid in highlight_ids:
                raise ValueError("highlightId must be globally unique")
            highlight_ids.add(hid)

            hs = h.get("startMs")
            he = h.get("endMs")
            if not isinstance(hs, int) or not isinstance(he, int) or he <= hs:
                raise ValueError("highlight startMs/endMs invalid")
            if hs < start_ms or he > end_ms:
                raise ValueError("highlight time range must fall within its block")

            kfs = h.get("keyframes")
            if not isinstance(kfs, list):
                raise ValueError("keyframes must be a list")
            
            for kf in kfs:
                if not isinstance(kf, dict):
                    raise ValueError("keyframe must be an object")
                tm = kf.get("timeMs")
                if not isinstance(tm, int):
                    raise ValueError("keyframe.timeMs must be an integer")
                if tm < start_ms or tm >= end_ms:
                    raise ValueError("keyframe.timeMs must fall within its block")

    # Validate mindmap structure.
    mindmap = out.get("mindmap")
    if not isinstance(mindmap, dict):
        raise ValueError("mindmap must be an object")

    mm_nodes = mindmap.get("nodes")
    if not isinstance(mm_nodes, list):
        raise ValueError("mindmap.nodes must be a list")

    node_ids: set[str] = set()
    root_count = 0

    for n in mm_nodes:
        if not isinstance(n, dict):
            continue

        nid = n.get("id")
        if not isinstance(nid, str) or not nid:
            raise ValueError("mindmap node id must be a non-empty string")
        node_ids.add(nid)

        ntype = n.get("type")
        if ntype not in ("root", "topic", "detail"):
            raise ValueError(f"mindmap node type must be root|topic|detail, got '{ntype}'")

        if ntype == "root":
            root_count += 1

        data = n.get("data")
        if not isinstance(data, dict):
            data = {}

        # topic/detail nodes must have targetBlockId.
        tb = data.get("targetBlockId")
        if ntype in ("topic", "detail"):
            if tb is not None and (not isinstance(tb, str) or tb not in block_ids):
                raise ValueError("mindmap node targetBlockId must reference an existing blockId")

        th = data.get("targetHighlightId")
        if th is not None:
            if not isinstance(th, str) or th not in highlight_ids:
                raise ValueError("mindmap node targetHighlightId must reference an existing highlightId")

    if root_count < 1 and len(mm_nodes) > 0:
        raise ValueError("mindmap must have at least 1 root node")

    # Validate edges.
    mm_edges = mindmap.get("edges")
    if isinstance(mm_edges, list):
        for e in mm_edges:
            if not isinstance(e, dict):
                continue
            src = e.get("source")
            tgt = e.get("target")
            if isinstance(src, str) and src and src not in node_ids:
                raise ValueError(f"mindmap edge source '{src}' must reference an existing node id")
            if isinstance(tgt, str) and tgt and tgt not in node_ids:
                raise ValueError(f"mindmap edge target '{tgt}' must reference an existing node id")

    return out


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _json_dumps_compact(obj: object) -> str:
    import json

    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def _sample_segments(segments: list[dict], *, max_segments: int, max_chars: int) -> list[dict]:
    max_segments = max(1, int(max_segments))
    max_chars = max(100, int(max_chars))

    if not segments:
        return []

    picked: list[dict] = []
    count = min(max_segments, len(segments))
    for i in range(count):
        pos = int(round((i + 1) * (len(segments) + 1) / (count + 1))) - 1
        pos = max(0, min(len(segments) - 1, pos))
        seg = segments[pos]
        if not isinstance(seg, dict):
            continue
        ss = seg.get("startMs")
        ee = seg.get("endMs")
        text = seg.get("text")
        if not isinstance(ss, int) or not isinstance(ee, int) or ee <= ss:
            continue
        if not isinstance(text, str):
            text = ""
        picked.append({"startMs": int(ss), "endMs": int(ee), "text": text.strip()[:400]})

    # Enforce total size budget.
    total = 0
    out: list[dict] = []
    for s in picked:
        chunk = f"{s.get('startMs')}-{s.get('endMs')}: {s.get('text','')}"
        total += len(chunk) + 1
        if total > max_chars:
            break
        out.append(s)
    return out


def _build_placeholder_plan(*, transcript: dict, schema_version: str) -> dict:
    segments = transcript.get("segments")
    seg_dicts = [s for s in segments if isinstance(s, dict)] if isinstance(segments, list) else []

    # Determine time bounds.
    start_ms: int = 0
    end_ms: int = 60_000
    if seg_dicts:
        starts = [_as_int(s.get("startMs")) for s in seg_dicts]
        ends = [_as_int(s.get("endMs")) for s in seg_dicts]
        starts2 = [s for s in starts if isinstance(s, int)]
        ends2 = [e for e in ends if isinstance(e, int)]
        if starts2 and ends2:
            start_ms = max(0, int(min(starts2)))
            end_ms = max(start_ms + 1, int(max(ends2)))

    # Build 3 coarse blocks.
    span = max(1, end_ms - start_ms)
    block_count = 3
    block_size = max(1, span // block_count)
    blocks: list[dict] = []
    for i in range(block_count):
        b_start = start_ms + i * block_size
        b_end = start_ms + (i + 1) * block_size if i < block_count - 1 else end_ms
        mid = (b_start + b_end) // 2
        blocks.append(
            {
                "blockId": f"b{i}",
                "idx": i,
                "title": f"Block {i}",
                "startMs": int(b_start),
                "endMs": int(b_end),
                "highlights": [
                    {
                        "highlightId": f"h{i}_0",
                        "idx": 0,
                        "text": "placeholder highlight",
                        "startMs": max(int(b_start), int(mid) - 500),
                        "endMs": min(int(b_end), int(mid) + 500),
                        "endMs": min(int(b_end), int(mid) + 500),
                        "keyframes": [{"timeMs": int(mid)}],
                    }
                ],
            }
        )

    # Build hierarchical mindmap: root + one topic per block.
    mm_nodes: list[dict] = [
        {"id": "n_root", "type": "root", "label": "Video Overview", "level": 0, "data": {}},
    ]
    mm_edges: list[dict] = []
    for i in range(block_count):
        nid = f"n_b{i}"
        mm_nodes.append({
            "id": nid, "type": "topic", "label": f"Block {i}", "level": 1,
            "data": {"targetBlockId": f"b{i}"},
        })
        mm_edges.append({"id": f"e_root_{nid}", "source": "n_root", "target": nid})

    return {
        "schemaVersion": schema_version,
        "contentBlocks": blocks,
        "mindmap": {"nodes": mm_nodes, "edges": mm_edges},
    }


def generate_plan(
    *,
    transcript: dict,
    summaries: list[dict] | None = None,
    output_language: str | None = None,
    provider: AnalyzeProvider | None = None,
    llm_transport: object | None = None,
) -> dict:
    """Generate a unified analysis plan via LLM.

    This stage is the single source of truth for:
    - contentBlocks (with embedded highlights + optional keyframe.timeMs)
    - mindmap graph (with targetBlockId/targetHighlightId anchors)

    Raises AnalyzeError with details.reason in {missing_credentials, invalid_llm_output, ...}.
    """

    if (os.environ.get("PLAN_PROVIDER") or "").strip().lower() == "placeholder":
        # Smoke/dev escape hatch to validate the pipeline without relying on external LLM availability.
        placeholder = _build_placeholder_plan(transcript=transcript, schema_version="2026-02-06")
        return validate_plan(placeholder)

    if provider is None:
        resolved = llm_provider_for_jobs(transport=llm_transport)  # type: ignore[arg-type]
        if resolved is None:
            raise AnalyzeError(
                code=ErrorCode.JOB_STAGE_FAILED,
                message="LLM credentials missing",
                details={"reason": "missing_credentials", "task": "plan"},
            )
        provider = resolved

    req = build_plan_request(transcript=transcript, summaries=summaries, output_language=output_language)
    messages = req.get("messages")
    if not isinstance(messages, list):
        raise AnalyzeError(
            code=ErrorCode.JOB_STAGE_FAILED,
            message="Invalid plan request",
            details={"reason": "plan_request_invalid"},
        )

    res = provider.generate_json("plan", {"messages": messages})

    if not isinstance(res, dict):
        raise AnalyzeError(
            code=ErrorCode.JOB_STAGE_FAILED,
            message="Invalid LLM output",
            details={"reason": "invalid_llm_output", "task": "plan", "outputType": type(res).__name__},
        )

    try:
        return validate_plan(res)
    except ValidationError as e:
        # Keep stable attribution for callers/tests: it's still invalid LLM output.
        details: dict[str, object] = {"reason": "invalid_llm_output", "task": "plan", "error": str(e), "validation": True}
        details["errors"] = e.errors()
        raise AnalyzeError(code=ErrorCode.JOB_STAGE_FAILED, message="Invalid LLM output (schema)", details=details)
    except ValueError as e:
        details: dict[str, object] = {"reason": "invalid_llm_output", "task": "plan", "error": str(e)}
        details["outputKeys"] = sorted([str(k) for k in res.keys()])
        raise AnalyzeError(code=ErrorCode.JOB_STAGE_FAILED, message="Invalid LLM output", details=details)


def build_plan_request(
    *,
    transcript: dict,
    summaries: list[dict] | None = None,
    output_language: str | None = None,
) -> dict:
    """Build the LLM request payload for the plan stage.

    Intended for external AI editors (llmMode=external) so they can reproduce
    the backend's prompts/schema and submit a validated plan back.
    """

    segments = transcript.get("segments") if isinstance(transcript, dict) else None
    if not isinstance(segments, list):
        segments = []
    seg_dicts = [s for s in segments if isinstance(s, dict)]

    max_segments = _env_int("LLM_PLAN_MAX_SEGMENTS", 60)
    max_chars = _env_int("LLM_PLAN_MAX_CHARS", 12_000)
    excerpt = _sample_segments(seg_dicts, max_segments=max_segments, max_chars=max_chars)

    lang = (output_language or "").strip()
    lang_hint = ""
    if lang and lang.lower() != "auto":
        lang_hint = (
            " Output language requirement: Write ALL user-visible strings in the language specified by `outputLanguage` ("
            + lang
            + "). This includes block titles, highlight text, and mindmap node labels."
        )

    system = (
        "You are a video learning assistant. Goal: help users learn/review WITHOUT rewatching the whole video. "
        "Return ONLY one JSON object (no markdown). "
        "Write high-quality notes: blocks are coherent modules; highlights are the key knowledge points. "
        "Do NOT over-split: prefer fewer, more complete highlights; merge nearby points when they belong together. "
        "Highlight text may be refined/summarized (not verbatim transcript). Skip trivial content. "
        "Keyframes are OPTIONAL: include only when screenshots meaningfully help learning (slide/diagram/code/formula/UI). "
        "If keyframes are present, set keyframes item timeMs (int, ms) within that highlight's [startMs,endMs). "
        "Schema keys MUST be exactly: schemaVersion, contentBlocks, mindmap. All times MUST be int ms. "
        "contentBlocks[] item: {blockId:str, idx:int, title:str, startMs:int, endMs:int, highlights:[...]}. "
        "highlights[] item: {highlightId:str, idx:int, text:str, startMs:int, endMs:int, keyframes?:[{timeMs:int}]}. "
        "mindmap: {nodes:[], edges:[]}. "
        "node fields: {id:str, type:str, label:str, level:int, data:{targetBlockId?:str, targetHighlightId?:str}}. "
        "node types: exactly 1 root(type=\"root\",level=0,no targetBlockId); "
        "topic(type=\"topic\",level=1,data.targetBlockId REQUIRED referencing contentBlocks[].blockId); "
        "detail(type=\"detail\",level=2,data.targetBlockId REQUIRED, data.targetHighlightId OPTIONAL). "
        "edge fields: {id:str, source:str, target:str, label?:str}. source/target MUST reference node ids. label is OPTIONAL. "
        "Topology: root->topics->details (DAG). root has no incoming edges. "
        "Constraints: contentBlocks idx contiguous from 0; no overlapping blocks; per-block highlights idx contiguous from 0; highlight ranges within block."
        + lang_hint
    )

    user_payload: dict = {
        "task": "plan",
        "schemaVersion": "2026-02-06",
        "transcript": {"segments": excerpt},
    }
    if lang:
        user_payload["outputLanguage"] = lang
    if isinstance(summaries, list) and summaries:
        user_payload["summaries"] = summaries

    return {
        "task": "plan",
        "schemaVersion": "2026-02-06",
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": _json_dumps_compact(user_payload)},
        ],
        # Helpful for debugging / external tooling.
        "system": system,
        "userPayload": user_payload,
    }
