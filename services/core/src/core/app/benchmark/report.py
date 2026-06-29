from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from core.app.benchmark.report_html import write_benchmark_report_html


def build_benchmark_report(
	*,
	mode: str,
	job_metrics: Mapping[str, Any],
	structure_score: Mapping[str, Any] | None = None,
	baseline_diff: Mapping[str, Any] | None = None,
	environment: Mapping[str, Any] | None = None,
	profile: str | None = None,
	semantic_score: Mapping[str, Any] | None = None,
	keyframe_verify: Mapping[str, Any] | None = None,
	human_rubric: Mapping[str, Any] | None = None,
	extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
	status = str(job_metrics.get("status") or "")
	structure = structure_score or {"passed": False, "score": 0.0, "checks": {}}
	baseline = baseline_diff or {"passed": True, "alerts": []}
	job_succeeded = status == "succeeded"
	structure_passed = bool(structure.get("passed"))
	baseline_passed = bool(baseline.get("passed"))

	if mode == "report":
		passed = structure_passed and baseline_passed
	else:
		passed = job_succeeded and structure_passed and baseline_passed

	pass_reasons: list[str] = []
	if not job_succeeded:
		pass_reasons.append(f"job_status_{status or 'unknown'}")
	if not structure_passed:
		pass_reasons.append("structure_score_failed")
	if not baseline_passed:
		pass_reasons.append("baseline_regression")

	report: dict[str, Any] = {
		"schemaVersion": "2026-06-22",
		"generatedAtMs": int(datetime.now(tz=timezone.utc).timestamp() * 1000),
		"mode": mode,
		"passed": passed,
		"passSummary": {
			"jobSucceeded": job_succeeded,
			"structurePassed": structure_passed,
			"baselinePassed": baseline_passed,
			"overallPassed": passed,
			"reasons": pass_reasons,
		},
		"jobMetrics": dict(job_metrics),
		"structureScore": dict(structure),
		"baselineDiff": dict(baseline),
	}
	if profile:
		report["profile"] = profile
	if environment:
		report["environment"] = dict(environment)
	if semantic_score:
		report["semanticScore"] = dict(semantic_score)
	kv = keyframe_verify or {
		"enabled": False,
		"reason": "verify_mode_off_or_no_artifact",
		"confidenceP50": None,
		"confidenceP90": None,
		"keepRate": None,
	}
	report["keyframeVerify"] = dict(kv)
	if human_rubric:
		report["humanRubric"] = dict(human_rubric)
	if extra:
		report["meta"] = dict(extra)
	return report


def _report_basename(*, date_str: str, git_sha: str, profile: str | None, job_id: str | None) -> str:
	sha = git_sha or "unknown"
	if profile:
		return f"{date_str}_{sha}_{profile}"
	if job_id:
		return f"{date_str}_{sha}_job-{job_id}"
	return f"{date_str}_{sha}_report"


def write_benchmark_report(
	report: Mapping[str, Any],
	*,
	out_dir: Path,
	profile: str | None = None,
	job_id: str | None = None,
	git_sha: str | None = None,
) -> tuple[Path, Path | None, Path | None]:
	out_dir.mkdir(parents=True, exist_ok=True)
	date_str = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
	env = report.get("environment") if isinstance(report.get("environment"), dict) else {}
	sha = git_sha or str(env.get("gitSha") or "unknown")
	base = _report_basename(date_str=date_str, git_sha=sha, profile=profile, job_id=job_id)
	json_path = out_dir / f"{base}.json"
	json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

	md_path = out_dir / f"{base}.md"
	md_path.write_text(_render_markdown_summary(report), encoding="utf-8")

	html_path = out_dir / f"{base}.html"
	write_benchmark_report_html(report, html_path=html_path)
	return json_path, md_path, html_path


def _render_markdown_summary(report: Mapping[str, Any]) -> str:
	jm = report.get("jobMetrics") if isinstance(report.get("jobMetrics"), dict) else {}
	ss = report.get("structureScore") if isinstance(report.get("structureScore"), dict) else {}
	bd = report.get("baselineDiff") if isinstance(report.get("baselineDiff"), dict) else {}
	lines = [
		"# Benchmark Report",
		"",
		f"- **passed**: {report.get('passed')}",
		f"- **mode**: {report.get('mode')}",
		f"- **profile**: {report.get('profile', '—')}",
		f"- **jobId**: {jm.get('jobId', '—')}",
		f"- **status**: {jm.get('status', '—')}",
		"",
		"## Performance",
		"",
		f"- e2eMs: {jm.get('e2eMs')}",
		f"- executionMs: {jm.get('executionMs')}",
		f"- speedFactor: {jm.get('speedFactor')}",
		"",
		"## Structure",
		"",
		f"- score: {ss.get('score')}",
		f"- passed: {ss.get('passed')}",
		"",
	]
	alerts = bd.get("alerts") if isinstance(bd.get("alerts"), list) else []
	if alerts:
		lines.extend(["## Alerts", ""])
		for alert in alerts:
			if isinstance(alert, dict):
				lines.append(f"- [{alert.get('code')}] {alert.get('message')}")
		lines.append("")
	kv = report.get("keyframeVerify") if isinstance(report.get("keyframeVerify"), dict) else {}
	lines.extend(
		[
			"## Keyframe verify",
			"",
			f"- enabled: {kv.get('enabled')}",
			f"- keepRate: {kv.get('keepRate')}",
			f"- confidenceP50: {kv.get('confidenceP50')}",
			"",
		]
	)
	sem = report.get("semanticScore") if isinstance(report.get("semanticScore"), dict) else {}
	hf = sem.get("highlightFaithfulness") if isinstance(sem.get("highlightFaithfulness"), dict) else None
	if hf:
		lines.extend(
			[
				"## Highlight faithfulness (LLM judge)",
				"",
				f"- passed: {hf.get('passed')}",
				f"- supportedRate: {hf.get('supportedRate')}",
				f"- meanScore: {hf.get('meanScore')}",
				"",
			]
		)
	hr = report.get("humanRubric") if isinstance(report.get("humanRubric"), dict) else None
	if hr:
		lines.extend(
			[
				"## Human rubric",
				"",
				f"- passed: {hr.get('passed')}",
				f"- meanScore: {hr.get('meanScore')}",
				"",
			]
		)
	return "\n".join(lines)
