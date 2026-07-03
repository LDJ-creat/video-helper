from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import httpx


def _load_env_file(path: Path) -> None:
	if not path.exists():
		return
	try:
		for raw in path.read_text(encoding="utf-8").splitlines():
			line = raw.strip()
			if not line or line.startswith("#") or "=" not in line:
				continue
			key, value = line.split("=", 1)
			if key.strip():
				os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
	except OSError:
		return


def _repo_root() -> Path:
	return Path(__file__).resolve().parents[2]


def _default_data_dir() -> Path:
	raw = os.environ.get("DATA_DIR")
	if raw and raw.strip():
		return Path(raw.strip()).resolve()
	return _repo_root() / "data"


def _load_golden_chapters(repo_root: Path, profile: str | None) -> list[dict[str, Any]] | None:
	if not profile:
		return None
	path = repo_root / "benchmarks" / "golden" / profile / "expected_chapters.json"
	if not path.exists():
		return None
	try:
		obj = json.loads(path.read_text(encoding="utf-8"))
	except (OSError, json.JSONDecodeError):
		return None
	if isinstance(obj, list):
		return [x for x in obj if isinstance(x, dict)]
	return None


def _generate_report_for_job(
	*,
	data_dir: Path,
	repo_root: Path,
	api_base: str,
	job_id: str,
	project_id: str | None,
	mode: str,
	profile: str | None,
	thresholds: dict[str, Any] | None,
	with_semantic: bool,
	with_llm_judge: bool,
	judge_full: bool,
	merge_rubric: bool,
	rubric_scores_path: Path | None,
	out_dir: Path,
) -> tuple[dict[str, Any], Path]:
	from core.app.benchmark.baseline import compare_to_baseline, load_baseline
	from core.app.benchmark.environment import collect_environment_snapshot
	from core.app.benchmark.faithfulness_judge import judge_highlight_faithfulness, load_transcript_segments
	from core.app.benchmark.http_client import get_latest_result
	from core.app.benchmark.human_rubric import load_human_rubric_for_report
	from core.app.benchmark.job_metrics import collect_job_metrics
	from core.app.benchmark.keyframe_verify_metrics import collect_keyframe_verify_metrics
	from core.app.benchmark.report import build_benchmark_report, write_benchmark_report
	from core.app.benchmark.semantic_score import score_semantic_golden
	from core.app.benchmark.structure_score import score_result_structure
	from core.app.pipeline.analyze_provider import llm_provider_for_jobs

	job_metrics = collect_job_metrics(data_dir=data_dir, job_id=job_id, project_id=project_id)
	project_id = str(job_metrics.get("projectId") or project_id or "")

	structure_score: dict[str, Any] | None = None
	semantic_score: dict[str, Any] | None = None
	result: dict[str, Any] | None = None
	faithfulness: dict[str, Any] | None = None

	if job_metrics.get("status") == "succeeded" and project_id:
		with httpx.Client(timeout=60.0) as client:
			result = get_latest_result(client=client, api_base=api_base, project_id=project_id)
		duration_ms = job_metrics.get("videoDurationMs")
		structure_score = score_result_structure(
			result,
			duration_ms=int(duration_ms) if isinstance(duration_ms, int) else None,
			pipeline_stages=job_metrics.get("stages") if isinstance(job_metrics.get("stages"), dict) else None,
		)
		if result is not None:
			expected = _load_golden_chapters(repo_root, profile) if with_semantic else None
			if with_llm_judge:
				provider = llm_provider_for_jobs()
				if provider is None:
					faithfulness = {
						"passed": False,
						"enabled": False,
						"reason": "llm_not_configured",
						"sampleSize": 0,
						"supportedRate": None,
						"meanScore": None,
						"samples": [],
					}
				else:
					segments = load_transcript_segments(
						data_dir=data_dir,
						project_id=project_id,
						job_id=job_id,
					)
					judge_thresholds = None
					if thresholds and isinstance(thresholds.get("highlightFaithfulness"), dict):
						judge_thresholds = thresholds["highlightFaithfulness"]
					faithfulness = judge_highlight_faithfulness(
						result=result,
						segments=segments,
						provider=provider,
						job_id=job_id,
						profile=profile,
						full=judge_full,
						supported_rate_min=(
							float(judge_thresholds["supportedRateMin"])
							if judge_thresholds and isinstance(judge_thresholds.get("supportedRateMin"), (int, float))
							else None
						),
						mean_score_min=(
							float(judge_thresholds["meanScoreMin"])
							if judge_thresholds and isinstance(judge_thresholds.get("meanScoreMin"), (int, float))
							else None
						),
					)
			if with_semantic and expected:
				semantic_score = score_semantic_golden(
					result=result,
					expected_chapters=expected,
					faithfulness=faithfulness,
				)
			elif faithfulness is not None:
				semantic_score = {
					"passed": bool(faithfulness.get("passed", True)),
					"highlightFaithfulness": faithfulness,
				}
	else:
		structure_score = {"passed": False, "score": 0.0, "checks": {}, "skipped": True}

	keyframe_verify = collect_keyframe_verify_metrics(
		data_dir=data_dir,
		project_id=project_id,
		job_id=job_id,
	)
	if keyframe_verify.get("enabled") and thresholds:
		kv_thresholds = thresholds.get("keyframeVerify")
		if isinstance(kv_thresholds, dict):
			p50_min = kv_thresholds.get("confidenceP50Min")
			if isinstance(p50_min, (int, float)):
				p50 = keyframe_verify.get("confidenceP50")
				if isinstance(p50, (int, float)) and p50 < float(p50_min):
					keyframe_verify["passed"] = False
				else:
					keyframe_verify["passed"] = True
			keep_min = kv_thresholds.get("keepRateMin")
			if isinstance(keep_min, (int, float)):
				keep = keyframe_verify.get("overallKeepRate")
				if keep is None:
					keep = keyframe_verify.get("keepRate")
				if isinstance(keep, (int, float)) and keep < float(keep_min):
					keyframe_verify["passed"] = False
				elif "passed" not in keyframe_verify:
					keyframe_verify["passed"] = True
			overall_min = kv_thresholds.get("overallKeepRateMin")
			if isinstance(overall_min, (int, float)):
				overall = keyframe_verify.get("overallKeepRate")
				if isinstance(overall, (int, float)) and overall < float(overall_min):
					keyframe_verify["passed"] = False
				elif "passed" not in keyframe_verify:
					keyframe_verify["passed"] = True
			second_min = kv_thresholds.get("secondVerifyPassRateMin")
			if isinstance(second_min, (int, float)):
				second = keyframe_verify.get("secondVerifyPassRate")
				if isinstance(second, (int, float)) and second < float(second_min):
					keyframe_verify["passed"] = False
				elif "passed" not in keyframe_verify:
					keyframe_verify["passed"] = True

	baseline = load_baseline(repo_root / "benchmarks" / "results" / "baseline.json")
	baseline_diff = compare_to_baseline(
		profile=profile,
		job_metrics=job_metrics,
		structure_score=structure_score or {"passed": False, "score": 0.0},
		thresholds=thresholds,
		baseline=baseline,
	)
	environment = collect_environment_snapshot()

	human_rubric = None
	if merge_rubric:
		human_rubric = load_human_rubric_for_report(
			repo_root=repo_root,
			profile=profile,
			job_id=job_id,
			rubric_scores_path=rubric_scores_path,
		)

	report = build_benchmark_report(
		mode=mode,
		job_metrics=job_metrics,
		structure_score=structure_score,
		baseline_diff=baseline_diff,
		environment=environment,
		profile=profile,
		semantic_score=semantic_score,
		keyframe_verify=keyframe_verify,
		human_rubric=human_rubric,
	)
	if semantic_score and not semantic_score.get("passed", True):
		report["passed"] = False
	if human_rubric and human_rubric.get("passed") is False:
		report["passed"] = False
	if keyframe_verify.get("enabled") and keyframe_verify.get("passed") is False:
		report["passed"] = False

	json_path, md_path, html_path = write_benchmark_report(
		report,
		out_dir=out_dir,
		profile=profile if mode == "benchmark" else None,
		job_id=job_id if mode == "report" else None,
		git_sha=str(environment.get("gitSha") or ""),
	)
	print(f"[benchmark] report written: {json_path}")
	if md_path:
		print(f"[benchmark] summary written: {md_path}")
	if html_path:
		print(f"[benchmark] html report written: {html_path}")
	return report, json_path


def main() -> int:
	parser = argparse.ArgumentParser(description="Run benchmark or generate report for existing job")
	parser.add_argument("--mode", choices=["benchmark", "report"], default="benchmark")
	parser.add_argument("--profile", default="short-local")
	parser.add_argument("--api-base", default="http://127.0.0.1:8000")
	parser.add_argument("--data-dir", default="")
	parser.add_argument("--profiles-file", default="")
	parser.add_argument("--out-dir", default="")
	parser.add_argument("--job-id", default="")
	parser.add_argument("--project-id", default="")
	parser.add_argument("--with-semantic", action="store_true")
	parser.add_argument("--with-llm-judge", action="store_true")
	parser.add_argument("--judge-full", action="store_true")
	parser.add_argument("--merge-rubric", action="store_true")
	parser.add_argument("--rubric-scores", default="")
	args = parser.parse_args()

	core_root = Path(__file__).resolve().parents[1]
	repo_root = _repo_root()
	_load_env_file(core_root / ".env")
	src_dir = core_root / "src"
	if str(src_dir) not in sys.path:
		sys.path.insert(0, str(src_dir))

	from core.app.benchmark.http_client import (
		post_json_job,
		post_upload_job,
		wait_for_job_done,
	)
	from core.app.benchmark.profiles import get_profile, load_profiles, profile_env_overrides

	data_dir = Path(args.data_dir).resolve() if args.data_dir else _default_data_dir()
	out_dir = Path(args.out_dir).resolve() if args.out_dir else (repo_root / "benchmarks" / "results")
	api_base = str(args.api_base).rstrip("/")
	profile_name: str | None = str(args.profile).strip() or None
	thresholds: dict[str, Any] | None = None

	job_id = str(args.job_id).strip()
	project_id = str(args.project_id).strip() or None

	if args.mode == "benchmark":
		profiles_path = Path(args.profiles_file).resolve() if args.profiles_file else repo_root / "benchmarks" / "profiles.yaml"
		doc = load_profiles(profiles_path)
		profile_cfg = get_profile(doc, str(args.profile))
		profile_name = str(args.profile)
		thresholds = profile_cfg.get("thresholds") if isinstance(profile_cfg.get("thresholds"), dict) else None
		for key, value in profile_env_overrides(profile_cfg).items():
			os.environ.setdefault(key, value)
		timeout_s = int(profile_cfg.get("timeoutSec") or 1200)
		source_type = str(profile_cfg.get("sourceType") or "").strip().lower()

		with httpx.Client(timeout=120.0) as client:
			if source_type == "upload":
				file_rel = str(profile_cfg.get("file") or "smoke/fixtures/smoke-fixture.mp4")
				file_path = (repo_root / file_rel).resolve()
				created = post_upload_job(client=client, api_base=api_base, file_path=str(file_path))
			else:
				source_url = str(profile_cfg.get("sourceUrl") or "").strip()
				if not source_url:
					raise RuntimeError(f"profile {args.profile} missing sourceUrl")
				created = post_json_job(
					client=client,
					api_base=api_base,
					source_type=source_type,
					source_url=source_url,
				)
			job_id = str(created["jobId"])
			project_id = str(created["projectId"])
			print(f"[benchmark] job created jobId={job_id} projectId={project_id}")
			final_job = wait_for_job_done(client=client, api_base=api_base, job_id=job_id, timeout_s=timeout_s)
			if final_job.get("status") != "succeeded":
				print(f"[benchmark] job finished with status={final_job.get('status')}")
		mode = "benchmark"
	else:
		if not job_id:
			parser.error("--job-id is required for --mode report")
		mode = "report"
		if not args.profile or args.profile == "short-local":
			profile_name = None

	rubric_scores_path = Path(args.rubric_scores).resolve() if str(args.rubric_scores).strip() else None

	report, _json_path = _generate_report_for_job(
		data_dir=data_dir,
		repo_root=repo_root,
		api_base=api_base,
		job_id=job_id,
		project_id=project_id,
		mode=mode,
		profile=profile_name,
		thresholds=thresholds,
		with_semantic=bool(args.with_semantic),
		with_llm_judge=bool(args.with_llm_judge),
		judge_full=bool(args.judge_full),
		merge_rubric=bool(args.merge_rubric) or rubric_scores_path is not None,
		rubric_scores_path=rubric_scores_path,
		out_dir=out_dir,
	)
	return 0 if report.get("passed") else 1


if __name__ == "__main__":
	raise SystemExit(main())
