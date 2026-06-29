from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


def _esc(value: Any) -> str:
	if value is None:
		return "—"
	return html.escape(str(value), quote=True)


def _fmt_ms(ms: Any) -> str:
	if not isinstance(ms, (int, float)) or ms < 0:
		return "—"
	total = int(ms)
	if total < 1000:
		return f"{total} ms"
	seconds = total // 1000
	if seconds < 60:
		return f"{seconds}.{total % 1000:03d} s"
	minutes, sec = divmod(seconds, 60)
	if minutes < 60:
		return f"{minutes}m {sec}s"
	hours, rem = divmod(minutes, 60)
	return f"{hours}h {rem}m {sec}s"


def _fmt_ratio(value: Any, *, digits: int = 2) -> str:
	if not isinstance(value, (int, float)):
		return "—"
	return f"{float(value):.{digits}f}"


def _fmt_pct(value: Any) -> str:
	if not isinstance(value, (int, float)):
		return "—"
	return f"{float(value) * 100:.1f}%"


def _fmt_ts(ms: Any) -> str:
	if not isinstance(ms, (int, float)):
		return "—"
	try:
		return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
	except (OSError, OverflowError, ValueError):
		return "—"


_CHECK_LABELS: dict[str, str] = {
	"blocks_count": "内容块数量",
	"highlights_count": "重点条数",
	"mindmap_nodes": "导图节点数",
	"keyframe_coverage": "关键帧覆盖率",
	"timestamp_in_range": "时间戳在范围内",
	"timestamp_monotonic": "时间戳单调",
	"mindmap_link_rate": "导图链接率",
}

_RUBRIC_LABELS: dict[str, str] = {
	"chapterQuality": "章节切分",
	"faithfulness": "摘要忠实度",
	"mindmapUsability": "导图可用性",
}

_SKIP_REASON_LABELS: dict[str, str] = {
	"keyframes_stage_not_executed": "流水线未执行关键帧抽取",
	"keyframes_extract_no_output": "抽取已触发但无产出（Result 中无 keyframe）",
}

_PASS_REASON_LABELS: dict[str, str] = {
	"job_status_canceled": "Job 状态为 canceled",
	"job_status_failed": "Job 状态为 failed",
	"job_status_unknown": "Job 未成功完成",
	"structure_score_failed": "L2 结构质量未通过",
	"baseline_regression": "相对 baseline 回归",
}


def _status_class(ok: bool | None) -> str:
	if ok is True:
		return "ok"
	if ok is False:
		return "fail"
	return "neutral"


_TRANSCRIBE_CHILD_PREFIX = "transcribe."
_SPEECH_PARENT = "speech_to_text"


def _stage_duration(stages: Mapping[str, Any], name: str) -> int | None:
	entry = stages.get(name)
	if not isinstance(entry, dict):
		return None
	duration = entry.get("durationMs")
	if isinstance(duration, (int, float)) and duration >= 0:
		return int(duration)
	return None


def _stage_status_class(stages: Mapping[str, Any], name: str) -> str:
	entry = stages.get(name)
	if isinstance(entry, dict):
		return _status_class(str(entry.get("status") or "ok") == "ok")
	return "neutral"


def _render_one_stage_bar(
	*,
	name: str,
	duration: int,
	max_ms: int,
	stages: Mapping[str, Any],
	compact: bool = False,
) -> str:
	width = max(2, round(duration / max_ms * 100)) if max_ms > 0 else 2
	status = _stage_status_class(stages, name)
	track_class = "stage-track stage-track-compact" if compact else "stage-track"
	return f"""
	<div class="stage-row{" stage-row-compact" if compact else ""}">
		<div class="stage-meta">
			<span class="stage-name">{_esc(name)}</span>
			<span class="stage-dur">{_esc(_fmt_ms(duration))}</span>
		</div>
		<div class="{track_class}" role="presentation">
			<div class="stage-fill {status}" style="width:{width}%"></div>
		</div>
	</div>
	"""


def _render_stage_bars(stages: Mapping[str, Any]) -> str:
	if not stages:
		return '<p class="empty">暂无分阶段耗时数据</p>'

	all_items: list[tuple[str, int]] = []
	for name, entry in stages.items():
		duration = _stage_duration(stages, str(name))
		if duration is not None:
			all_items.append((str(name), duration))
	if not all_items:
		return '<p class="empty">暂无分阶段耗时数据</p>'

	transcribe_children = sorted(
		[(n, d) for n, d in all_items if n.startswith(_TRANSCRIBE_CHILD_PREFIX)],
		key=lambda x: x[1],
		reverse=True,
	)
	top_items = [(n, d) for n, d in all_items if not n.startswith(_TRANSCRIBE_CHILD_PREFIX)]
	max_ms = max(d for _, d in top_items) if top_items else max(d for _, d in all_items) or 1

	rows: list[str] = []
	for name, duration in sorted(top_items, key=lambda x: x[1], reverse=True):
		if name == _SPEECH_PARENT and transcribe_children:
			rows.append(_render_one_stage_bar(name=name, duration=duration, max_ms=max_ms, stages=stages))
			child_max = max(d for _, d in transcribe_children) or 1
			child_rows = [
				_render_one_stage_bar(name=cname, duration=cdur, max_ms=child_max, stages=stages, compact=True)
				for cname, cdur in transcribe_children
			]
			rows.append(
				f"""
				<details class="stage-details">
					<summary>展开转写子步骤（已包含在 {_esc(_SPEECH_PARENT)} 耗时内）</summary>
					<div class="stage-children">
						{"".join(child_rows)}
					</div>
				</details>
				"""
			)
		else:
			rows.append(_render_one_stage_bar(name=name, duration=duration, max_ms=max_ms, stages=stages))

	if not top_items and transcribe_children:
		child_max = max(d for _, d in transcribe_children) or 1
		for cname, cdur in transcribe_children:
			rows.append(_render_one_stage_bar(name=cname, duration=cdur, max_ms=child_max, stages=stages))

	return "\n".join(rows)


def _render_checks(checks: Mapping[str, Any]) -> str:
	if not checks:
		return '<p class="empty">无结构检查项</p>'
	cards: list[str] = []
	for key, check in checks.items():
		if not isinstance(check, dict):
			continue
		ok = check.get("ok")
		skipped = check.get("skipped") is True
		label = _CHECK_LABELS.get(key, key)
		value = check.get("value")
		min_val = check.get("min")
		if skipped:
			card_class = "check-card skipped"
			verdict = "已跳过"
			reason = check.get("reason")
			reason_text = _SKIP_REASON_LABELS.get(str(reason or ""), str(reason) if reason else "未纳入本次评测")
			threshold_line = f'<p class="check-threshold">{_esc(reason_text)}</p>'
		else:
			card_class = f"check-card {_status_class(ok if isinstance(ok, bool) else None)}"
			verdict = "通过" if ok else "未通过"
			threshold_line = f'<p class="check-threshold">阈值 ≥ {_esc(min_val)}</p>'
		cards.append(
			f"""
			<article class="{card_class}">
				<header>{_esc(label)}</header>
				<p class="check-value">{_esc(_fmt_ratio(value, digits=3) if isinstance(value, float) else value)}</p>
				{threshold_line}
				<p class="check-verdict">{verdict}</p>
			</article>
			"""
		)
	return f'<div class="check-grid">{"".join(cards)}</div>'


def _render_alerts(alerts: list[Any]) -> str:
	if not alerts:
		return ""
	items = []
	for alert in alerts:
		if not isinstance(alert, dict):
			continue
		items.append(
			f'<li><code>{_esc(alert.get("code"))}</code> {_esc(alert.get("message"))}</li>'
		)
	if not items:
		return ""
	return f'<section class="panel alerts"><h2>Baseline 告警</h2><ul>{"".join(items)}</ul></section>'


def _render_keyframe_verify(kv: Mapping[str, Any]) -> str:
	enabled = kv.get("enabled") is True
	if not enabled:
		reason = kv.get("reason") or "verify_mode_off_or_no_artifact"
		return f"""
		<section class="panel muted-panel">
			<h2>L3 Keyframe Verify（LLM 校验）</h2>
			<p class="panel-note">未启用（{_esc(reason)}）。与 L2「关键帧覆盖率」无关；verify 关闭不影响结构分跳过逻辑。</p>
		</section>
		"""
	metrics = [
		("模式", kv.get("mode")),
		("样本数", kv.get("count")),
		("保留率", _fmt_pct(kv.get("keepRate")) if kv.get("keepRate") is not None else "—"),
		("丢弃率", _fmt_pct(kv.get("dropRate")) if kv.get("dropRate") is not None else "—"),
		("P50 置信度", kv.get("confidenceP50")),
		("P90 置信度", kv.get("confidenceP90")),
	]
	cards = "".join(
		f'<div class="metric-card"><span class="metric-label">{_esc(k)}</span><span class="metric-value">{_esc(v)}</span></div>'
		for k, v in metrics
	)
	passed = kv.get("passed")
	badge = "通过" if passed is True else ("未通过" if passed is False else "—")
	return f"""
	<section class="panel">
		<div class="panel-head">
			<h2>Keyframe Verify</h2>
			<span class="badge {_status_class(passed if isinstance(passed, bool) else None)}">{_esc(badge)}</span>
		</div>
		<div class="metric-grid">{cards}</div>
	</section>
	"""


def _render_semantic(sem: Mapping[str, Any]) -> str:
	if not sem:
		return ""
	chapter = sem.get("chapterBoundary") if isinstance(sem.get("chapterBoundary"), dict) else {}
	hf = sem.get("highlightFaithfulness") if isinstance(sem.get("highlightFaithfulness"), dict) else None

	chapter_html = ""
	if chapter:
		chapter_html = f"""
		<div class="sub-block">
			<h3>章节边界 F1</h3>
			<div class="metric-grid">
				<div class="metric-card"><span class="metric-label">F1</span><span class="metric-value">{_esc(chapter.get("f1"))}</span></div>
				<div class="metric-card"><span class="metric-label">Precision</span><span class="metric-value">{_esc(chapter.get("precision"))}</span></div>
				<div class="metric-card"><span class="metric-label">Recall</span><span class="metric-value">{_esc(chapter.get("recall"))}</span></div>
				<div class="metric-card"><span class="metric-label">匹配</span><span class="metric-value">{_esc(chapter.get("matched"))} / {_esc(chapter.get("expected"))}</span></div>
			</div>
		</div>
		"""

	hf_html = ""
	if hf:
		if hf.get("skipped"):
			hf_html = f'<p class="panel-note">LLM judge 跳过：{_esc(hf.get("reason") or "—")}</p>'
		elif hf.get("enabled") is False:
			hf_html = f'<p class="panel-note">LLM judge 未运行：{_esc(hf.get("reason") or "—")}</p>'
		else:
			samples = hf.get("samples") if isinstance(hf.get("samples"), list) else []
			sample_rows = []
			for s in samples[:20]:
				if not isinstance(s, dict):
					continue
				sample_rows.append(
					f"<tr><td>{'✓' if s.get('supported') else '✗'}</td>"
					f"<td>{_esc(_fmt_ratio(s.get('score')))}</td>"
					f"<td>{_esc(s.get('highlightId') or s.get('blockId') or '—')}</td>"
					f"<td>{_esc(s.get('reason') or s.get('error') or '')}</td></tr>"
				)
			table = ""
			if sample_rows:
				table = f"""
				<table class="data-table">
					<thead><tr><th>支持</th><th>分数</th><th>ID</th><th>说明</th></tr></thead>
					<tbody>{"".join(sample_rows)}</tbody>
				</table>
				"""
			hf_html = f"""
			<div class="sub-block">
				<h3>Highlight 忠实度（LLM Judge）</h3>
				<div class="metric-grid">
					<div class="metric-card"><span class="metric-label">抽样数</span><span class="metric-value">{_esc(hf.get("sampleSize"))}</span></div>
					<div class="metric-card"><span class="metric-label">支持率</span><span class="metric-value">{_esc(_fmt_pct(hf.get("supportedRate")))}</span></div>
					<div class="metric-card"><span class="metric-label">均分</span><span class="metric-value">{_esc(hf.get("meanScore"))}</span></div>
				</div>
				{table}
			</div>
			"""

	if not chapter_html and not hf_html:
		return ""

	passed = sem.get("passed")
	return f"""
	<section class="panel">
		<div class="panel-head">
			<h2>L3 语义质量</h2>
			<span class="badge {_status_class(passed if isinstance(passed, bool) else None)}">{"通过" if passed else "未通过"}</span>
		</div>
		{chapter_html}
		{hf_html}
	</section>
	"""


def _render_human_rubric(hr: Mapping[str, Any]) -> str:
	if not hr:
		return ""
	dimensions = hr.get("dimensions") if isinstance(hr.get("dimensions"), dict) else {}
	scores = hr.get("scores") if isinstance(hr.get("scores"), dict) else {}
	items = dimensions or scores
	bars: list[str] = []
	for dim_id, entry in items.items():
		if isinstance(entry, dict):
			score = entry.get("score")
			note = entry.get("note")
		else:
			score = entry
			note = ""
		if not isinstance(score, (int, float)):
			continue
		label = _RUBRIC_LABELS.get(str(dim_id), str(dim_id))
		width = max(4, int(float(score) / 5 * 100))
		note_html = f'<p class="rubric-note">{_esc(note)}</p>' if note else ""
		bars.append(
			f"""
			<div class="rubric-row">
				<div class="rubric-meta">
					<span>{_esc(label)}</span>
					<strong>{int(score)}/5</strong>
				</div>
				<div class="rubric-track"><div class="rubric-fill" style="width:{width}%"></div></div>
				{note_html}
			</div>
			"""
		)
	passed = hr.get("passed")
	return f"""
	<section class="panel">
		<div class="panel-head">
			<h2>人工 Rubric</h2>
			<span class="badge {_status_class(passed if isinstance(passed, bool) else None)}">均分 {_esc(hr.get("meanScore"))}</span>
		</div>
		<p class="panel-note">评分者 {_esc(hr.get("scorer"))} · {_esc(_fmt_ts(hr.get("scoredAtMs")))}</p>
		{"".join(bars) if bars else '<p class="empty">无维度分数</p>'}
	</section>
	"""


def _render_pass_summary(report: Mapping[str, Any], *, jm: Mapping[str, Any], ss: Mapping[str, Any]) -> str:
	ps = report.get("passSummary") if isinstance(report.get("passSummary"), dict) else {}
	job_ok = ps.get("jobSucceeded")
	structure_ok = ps.get("structurePassed")
	baseline_ok = ps.get("baselinePassed")
	overall = ps.get("overallPassed")
	reasons = ps.get("reasons") if isinstance(ps.get("reasons"), list) else []

	def _pill(label: str, ok: bool | None) -> str:
		cls = _status_class(ok if isinstance(ok, bool) else None)
		text = "通过" if ok is True else ("未通过" if ok is False else "—")
		return f'<span class="pass-pill {cls}">{_esc(label)} · {text}</span>'

	reason_items = []
	for r in reasons:
		if not isinstance(r, str):
			continue
		label = _PASS_REASON_LABELS.get(r)
		if label is None and r.startswith("job_status_"):
			label = f"Job 状态为 {r.removeprefix('job_status_')}"
		reason_items.append(f"<li>{_esc(label or r)}</li>")

	reason_html = ""
	if reason_items and overall is not True:
		reason_html = f'<ul class="pass-reasons">{"".join(reason_items)}</ul>'

	mode = str(report.get("mode") or "")
	mode_note = ""
	if mode == "report" and job_ok is False and structure_ok is True:
		mode_note = '<p class="pass-note">历史 Job 报告模式：整体通过仅看 L2 结构 + baseline，不要求 Job 状态 succeeded。</p>'

	return f"""
	<div class="pass-summary">
		{_pill("Job", job_ok if isinstance(job_ok, bool) else (str(jm.get("status")) == "succeeded"))}
		{_pill("L2 结构", structure_ok if isinstance(structure_ok, bool) else ss.get("passed"))}
		{_pill("Baseline", baseline_ok if isinstance(baseline_ok, bool) else True)}
		{_pill("整体", overall if isinstance(overall, bool) else report.get("passed"))}
	</div>
	{mode_note}
	{reason_html}
	"""


def render_benchmark_report_html(report: Mapping[str, Any]) -> str:
	jm = report.get("jobMetrics") if isinstance(report.get("jobMetrics"), dict) else {}
	ss = report.get("structureScore") if isinstance(report.get("structureScore"), dict) else {}
	bd = report.get("baselineDiff") if isinstance(report.get("baselineDiff"), dict) else {}
	env = report.get("environment") if isinstance(report.get("environment"), dict) else {}
	meta = report.get("meta") if isinstance(report.get("meta"), dict) else {}
	kv = report.get("keyframeVerify") if isinstance(report.get("keyframeVerify"), dict) else {}
	sem = report.get("semanticScore") if isinstance(report.get("semanticScore"), dict) else None
	hr = report.get("humanRubric") if isinstance(report.get("humanRubric"), dict) else None

	passed = report.get("passed") is True
	verdict = "通过" if passed else "未通过"
	verdict_class = "ok" if passed else "fail"

	title = str(meta.get("evaluationLabel") or report.get("profile") or jm.get("jobId") or "Benchmark Report")
	source_url = meta.get("sourceUrl")
	source_link = (
		f'<a class="source-link" href="{_esc(source_url)}" target="_blank" rel="noopener">{_esc(source_url)}</a>'
		if isinstance(source_url, str) and source_url.strip()
		else ""
	)

	llm = jm.get("llm") if isinstance(jm.get("llm"), dict) else {}
	stages = jm.get("stages") if isinstance(jm.get("stages"), dict) else {}

	structure_score = ss.get("score")
	structure_passed = ss.get("passed")
	pass_summary_html = _render_pass_summary(report, jm=jm, ss=ss)

	return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
	<meta charset="utf-8" />
	<meta name="viewport" content="width=device-width, initial-scale=1" />
	<title>{_esc(title)} · Video Helper 评测报告</title>
	<link rel="preconnect" href="https://fonts.googleapis.com" />
	<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
	<link href="https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,500;0,9..40,600;1,9..40,400&family=IBM+Plex+Mono:wght@400;500&family=Syne:wght@600;700&display=swap" rel="stylesheet" />
	<style>
		:root {{
			--bg: #0b1016;
			--surface: #121a24;
			--surface-2: #1a2430;
			--ink: #e8edf2;
			--muted: #8b9cb0;
			--line: #2a3644;
			--teal: #2dd4bf;
			--teal-dim: #1a8f82;
			--amber: #f59e0b;
			--red: #ef4444;
			--ok: #34d399;
			--fail: #f87171;
			--radius: 10px;
			--font-display: "Syne", system-ui, sans-serif;
			--font-body: "DM Sans", system-ui, sans-serif;
			--font-mono: "IBM Plex Mono", ui-monospace, monospace;
		}}
		*, *::before, *::after {{ box-sizing: border-box; }}
		html {{ scroll-behavior: smooth; }}
		@media (prefers-reduced-motion: reduce) {{
			html {{ scroll-behavior: auto; }}
			.hero-verdict, .stage-fill, .rubric-fill {{ animation: none !important; }}
		}}
		body {{
			margin: 0;
			font-family: var(--font-body);
			background: var(--bg);
			color: var(--ink);
			line-height: 1.55;
			font-size: 15px;
		}}
		a {{ color: var(--teal); }}
		a:focus-visible, button:focus-visible {{
			outline: 2px solid var(--teal);
			outline-offset: 3px;
		}}
		.wrap {{ max-width: 1080px; margin: 0 auto; padding: 2rem 1.25rem 4rem; }}
		.hero {{
			display: grid;
			gap: 1.5rem;
			padding: 2rem;
			border: 1px solid var(--line);
			border-radius: calc(var(--radius) + 4px);
			background:
				radial-gradient(ellipse 80% 60% at 100% 0%, rgba(45,212,191,.12), transparent 55%),
				linear-gradient(160deg, var(--surface) 0%, var(--bg) 100%);
			margin-bottom: 1.5rem;
		}}
		.eyebrow {{
			font-family: var(--font-mono);
			font-size: .72rem;
			letter-spacing: .14em;
			text-transform: uppercase;
			color: var(--teal);
		}}
		.hero h1 {{
			font-family: var(--font-display);
			font-size: clamp(1.6rem, 4vw, 2.4rem);
			line-height: 1.15;
			margin: .35rem 0 0;
			font-weight: 700;
		}}
		.hero-meta {{
			display: flex;
			flex-wrap: wrap;
			gap: .5rem 1rem;
			color: var(--muted);
			font-size: .88rem;
			font-family: var(--font-mono);
		}}
		.hero-verdict {{
			display: inline-flex;
			align-items: center;
			gap: .6rem;
			font-family: var(--font-display);
			font-size: 1.1rem;
			font-weight: 600;
			padding: .65rem 1rem;
			border-radius: 999px;
			width: fit-content;
			border: 1px solid var(--line);
			animation: fadeUp .5s ease both;
		}}
		.hero-verdict.ok {{ background: rgba(52,211,153,.12); border-color: rgba(52,211,153,.35); color: var(--ok); }}
		.hero-verdict.fail {{ background: rgba(248,113,113,.1); border-color: rgba(248,113,113,.35); color: var(--fail); }}
		.hero-verdict .dot {{ width: .55rem; height: .55rem; border-radius: 50%; background: currentColor; }}
		.pass-summary {{
			display: flex;
			flex-wrap: wrap;
			gap: .5rem;
		}}
		.pass-pill {{
			font-family: var(--font-mono);
			font-size: .72rem;
			padding: .3rem .6rem;
			border-radius: 6px;
			border: 1px solid var(--line);
		}}
		.pass-pill.ok {{ color: var(--ok); border-color: rgba(52,211,153,.35); }}
		.pass-pill.fail {{ color: var(--fail); border-color: rgba(248,113,113,.35); }}
		.pass-pill.neutral {{ color: var(--muted); }}
		.pass-note, .pass-reasons {{
			margin: 0;
			font-size: .85rem;
			color: var(--muted);
		}}
		.pass-reasons {{ padding-left: 1.1rem; }}
		.metric-grid {{
			display: grid;
			grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
			gap: .75rem;
		}}
		.metric-card {{
			background: var(--surface-2);
			border: 1px solid var(--line);
			border-radius: var(--radius);
			padding: .85rem 1rem;
		}}
		.metric-label {{
			display: block;
			font-size: .72rem;
			color: var(--muted);
			text-transform: uppercase;
			letter-spacing: .06em;
			font-family: var(--font-mono);
			margin-bottom: .35rem;
		}}
		.metric-value {{
			font-family: var(--font-mono);
			font-size: 1.05rem;
			font-weight: 500;
		}}
		.panel {{
			background: var(--surface);
			border: 1px solid var(--line);
			border-radius: calc(var(--radius) + 2px);
			padding: 1.35rem 1.5rem;
			margin-bottom: 1rem;
		}}
		.panel-head {{
			display: flex;
			align-items: center;
			justify-content: space-between;
			gap: 1rem;
			margin-bottom: 1rem;
		}}
		.panel h2 {{
			font-family: var(--font-display);
			font-size: 1.05rem;
			margin: 0;
			font-weight: 600;
		}}
		.panel h3 {{
			font-size: .92rem;
			margin: 0 0 .75rem;
			color: var(--muted);
			font-weight: 500;
		}}
		.panel-note {{ color: var(--muted); font-size: .9rem; margin: 0 0 .75rem; }}
		.muted-panel {{ opacity: .92; }}
		.badge {{
			font-family: var(--font-mono);
			font-size: .72rem;
			padding: .25rem .55rem;
			border-radius: 6px;
			border: 1px solid var(--line);
		}}
		.badge.ok {{ color: var(--ok); border-color: rgba(52,211,153,.4); }}
		.badge.fail {{ color: var(--fail); border-color: rgba(248,113,113,.4); }}
		.badge.neutral {{ color: var(--muted); }}
		.stage-row {{ margin-bottom: .85rem; }}
		.stage-meta {{
			display: flex;
			justify-content: space-between;
			gap: 1rem;
			font-family: var(--font-mono);
			font-size: .78rem;
			margin-bottom: .35rem;
		}}
		.stage-name {{ color: var(--ink); }}
		.stage-dur {{ color: var(--teal); }}
		.stage-track {{
			height: 8px;
			background: var(--surface-2);
			border-radius: 999px;
			overflow: hidden;
			border: 1px solid var(--line);
		}}
		.stage-fill {{
			height: 100%;
			border-radius: 999px;
			background: linear-gradient(90deg, var(--teal-dim), var(--teal));
			animation: growBar .7s ease both;
		}}
		.stage-fill.fail {{ background: linear-gradient(90deg, #9f1239, var(--fail)); }}
		.stage-details {{
			margin: -.35rem 0 .85rem .25rem;
			padding-left: .5rem;
			border-left: 1px dashed var(--line);
		}}
		.stage-details summary {{
			cursor: pointer;
			font-size: .76rem;
			color: var(--muted);
			padding: .25rem 0;
			list-style: none;
		}}
		.stage-details summary::-webkit-details-marker {{ display: none; }}
		.stage-details summary::before {{
			content: "▸ ";
			color: var(--teal);
		}}
		.stage-details[open] summary::before {{ content: "▾ "; }}
		.stage-children {{ padding: .35rem 0 .15rem .35rem; }}
		.stage-row-compact .stage-meta {{ font-size: .72rem; }}
		.stage-track-compact {{ height: 6px; }}
		.check-card.skipped {{
			border-style: dashed;
			border-color: var(--line);
			opacity: .88;
		}}
		.check-card.skipped .check-verdict {{ color: var(--muted); }}
		.check-grid {{
			display: grid;
			grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
			gap: .75rem;
		}}
		.check-card {{
			border: 1px solid var(--line);
			border-radius: var(--radius);
			padding: .9rem 1rem;
			background: var(--surface-2);
		}}
		.check-card.ok {{ border-color: rgba(52,211,153,.35); }}
		.check-card.fail {{ border-color: rgba(248,113,113,.4); }}
		.check-card header {{
			font-size: .78rem;
			color: var(--muted);
			margin-bottom: .4rem;
		}}
		.check-value {{
			font-family: var(--font-mono);
			font-size: 1.2rem;
			margin: 0;
			font-weight: 500;
		}}
		.check-threshold, .check-verdict {{
			margin: .25rem 0 0;
			font-size: .78rem;
			color: var(--muted);
		}}
		.check-verdict {{ color: var(--ink); font-weight: 500; }}
		.sub-block {{ margin-top: 1.25rem; padding-top: 1.25rem; border-top: 1px solid var(--line); }}
		.sub-block:first-of-type {{ margin-top: 0; padding-top: 0; border-top: 0; }}
		.data-table {{
			width: 100%;
			border-collapse: collapse;
			font-size: .82rem;
			margin-top: .75rem;
		}}
		.data-table th, .data-table td {{
			border-bottom: 1px solid var(--line);
			padding: .5rem .4rem;
			text-align: left;
			vertical-align: top;
		}}
		.data-table th {{
			color: var(--muted);
			font-family: var(--font-mono);
			font-weight: 500;
			font-size: .72rem;
			text-transform: uppercase;
			letter-spacing: .05em;
		}}
		.rubric-row {{ margin-bottom: 1rem; }}
		.rubric-meta {{
			display: flex;
			justify-content: space-between;
			margin-bottom: .35rem;
			font-size: .9rem;
		}}
		.rubric-track {{
			height: 6px;
			background: var(--surface-2);
			border-radius: 999px;
			overflow: hidden;
		}}
		.rubric-fill {{
			height: 100%;
			background: linear-gradient(90deg, var(--amber), #fbbf24);
			border-radius: 999px;
		}}
		.rubric-note {{ margin: .35rem 0 0; font-size: .82rem; color: var(--muted); }}
		.alerts ul {{ margin: 0; padding-left: 1.2rem; }}
		.alerts li {{ margin-bottom: .4rem; }}
		.alerts code {{
			font-family: var(--font-mono);
			font-size: .78rem;
			color: var(--amber);
		}}
		.empty {{ color: var(--muted); font-size: .9rem; }}
		.footer {{
			margin-top: 2rem;
			padding-top: 1rem;
			border-top: 1px solid var(--line);
			color: var(--muted);
			font-size: .78rem;
			font-family: var(--font-mono);
		}}
		@keyframes fadeUp {{
			from {{ opacity: 0; transform: translateY(6px); }}
			to {{ opacity: 1; transform: translateY(0); }}
		}}
		@keyframes growBar {{
			from {{ transform: scaleX(0); transform-origin: left; }}
			to {{ transform: scaleX(1); transform-origin: left; }}
		}}
		@media (max-width: 640px) {{
			.wrap {{ padding: 1rem .85rem 3rem; }}
			.hero {{ padding: 1.25rem; }}
		}}
	</style>
</head>
<body>
	<div class="wrap">
		<header class="hero">
			<div>
				<p class="eyebrow">Video Helper · L0–L3 评测</p>
				<h1>{_esc(title)}</h1>
				<div class="hero-meta">
					<span>Job {_esc(jm.get("jobId"))}</span>
					<span>Project {_esc(jm.get("projectId"))}</span>
					<span>{_esc(_fmt_ts(report.get("generatedAtMs")))}</span>
				</div>
				{source_link}
			</div>
			<div class="hero-verdict {verdict_class}" role="status">
				<span class="dot" aria-hidden="true"></span>
				<span>整体 {verdict}</span>
			</div>
			{pass_summary_html}
			<div class="metric-grid">
				<div class="metric-card">
					<span class="metric-label">视频时长</span>
					<span class="metric-value">{_esc(_fmt_ms(jm.get("videoDurationMs")))}</span>
				</div>
				<div class="metric-card">
					<span class="metric-label">端到端</span>
					<span class="metric-value">{_esc(_fmt_ms(jm.get("e2eMs")))}</span>
				</div>
				<div class="metric-card">
					<span class="metric-label">执行耗时</span>
					<span class="metric-value">{_esc(_fmt_ms(jm.get("executionMs")))}</span>
				</div>
				<div class="metric-card">
					<span class="metric-label">Speed factor</span>
					<span class="metric-value">{_esc(jm.get("speedFactor"))}</span>
				</div>
				<div class="metric-card">
					<span class="metric-label">Job 状态</span>
					<span class="metric-value">{_esc(jm.get("status"))}</span>
				</div>
				<div class="metric-card">
					<span class="metric-label">L2 结构分</span>
					<span class="metric-value">{_esc(structure_score)}</span>
				</div>
			</div>
		</header>

		<section class="panel">
			<div class="panel-head">
				<h2>流水线分阶段耗时</h2>
				<span class="badge neutral">LLM {_esc(llm.get("calls"))} 次 · repair {_esc(llm.get("repairs"))}</span>
			</div>
			{_render_stage_bars(stages)}
		</section>

		<section class="panel">
			<div class="panel-head">
				<h2>L2 结构质量</h2>
				<span class="badge {_status_class(structure_passed if isinstance(structure_passed, bool) else None)}">
					{"通过" if structure_passed else "未通过"}
				</span>
			</div>
			{_render_checks(ss.get("checks") if isinstance(ss.get("checks"), dict) else {})}
			{f'<p class="panel-note">{_esc(ss.get("note"))}</p>' if ss.get("note") else ""}
		</section>

		{_render_semantic(sem) if sem else ""}
		{_render_keyframe_verify(kv)}
		{_render_human_rubric(hr) if hr else ""}
		{_render_alerts(bd.get("alerts") if isinstance(bd.get("alerts"), list) else [])}

		<footer class="footer">
			schema {_esc(report.get("schemaVersion"))} · mode {_esc(report.get("mode"))} · git {_esc(env.get("gitSha"))}
		</footer>
	</div>
</body>
</html>
"""


def write_benchmark_report_html(report: Mapping[str, Any], *, html_path: Path) -> Path:
	html_path.parent.mkdir(parents=True, exist_ok=True)
	html_path.write_text(render_benchmark_report_html(report), encoding="utf-8")
	return html_path


def render_benchmark_report_html_from_json(path: Path) -> str:
	payload = json.loads(path.read_text(encoding="utf-8"))
	if not isinstance(payload, dict):
		raise ValueError("report JSON must be an object")
	return render_benchmark_report_html(payload)
