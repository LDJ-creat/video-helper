#!/usr/bin/env python3
"""Benchmark cloud ASR (DashScope Paraformer-v2) on a local video/audio file.

Uses shared production modules under core.external.asr_providers.

Usage:
  cd services/core
  uv run python scripts/test_cloud_asr_bench.py --video path/to/video.mp4 --api-key sk-...
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

MODEL_NAME = "paraformer-v2"


@dataclass
class StageTimingsMs:
	ffprobe_ms: float = 0.0
	ffmpeg_extract_ms: float = 0.0
	upload_ms: float = 0.0
	submit_ms: float = 0.0
	wait_ms: float = 0.0
	download_ms: float = 0.0
	total_ms: float = 0.0


@dataclass
class BenchReport:
	model: str
	input_path: str
	audio_path: str
	audio_duration_s: float | None
	transcript_preview: str | None
	sentence_count: int
	timings_ms: StageTimingsMs
	output_files: dict[str, str] = field(default_factory=dict)
	created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


def _load_env_file(path: Path) -> None:
	if not path.exists():
		return
	for raw in path.read_text(encoding="utf-8").splitlines():
		line = raw.strip()
		if not line or line.startswith("#") or "=" not in line:
			continue
		key, value = line.split("=", 1)
		os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
	return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")


def probe_duration_s(path: Path, ffprobe: str) -> float | None:
	proc = _run([
		ffprobe, "-hide_banner", "-v", "error", "-show_entries", "format=duration",
		"-of", "default=noprint_wrappers=1:nokey=1", str(path),
	])
	try:
		return float(proc.stdout.strip()) if proc.returncode == 0 else None
	except ValueError:
		return None


def extract_wav(ffmpeg: str, media: Path, out: Path) -> None:
	proc = _run([
		ffmpeg, "-hide_banner", "-nostdin", "-y", "-i", str(media), "-vn", "-ac", "1",
		"-ar", "16000", "-c:a", "pcm_s16le", "-f", "wav", str(out),
	])
	if proc.returncode != 0:
		raise RuntimeError(proc.stderr[-500:])


def main() -> int:
	core_root = Path(__file__).resolve().parents[1]
	src = core_root / "src"
	if str(src) not in sys.path:
		sys.path.insert(0, str(src))
	_load_env_file(core_root / ".env")

	from core.external.asr_providers.dashscope import transcribe_dashscope_paraformer

	parser = argparse.ArgumentParser(description="Benchmark DashScope Paraformer ASR")
	src_group = parser.add_mutually_exclusive_group(required=True)
	src_group.add_argument("--video", type=Path)
	src_group.add_argument("--audio", type=Path)
	parser.add_argument("--api-key", default=os.environ.get("DASHSCOPE_API_KEY", "").strip())
	parser.add_argument("--model", default=MODEL_NAME)
	parser.add_argument("--output-dir", type=Path, default=None)
	args = parser.parse_args()

	input_path = (args.video or args.audio).expanduser().resolve()
	api_key = args.api_key.strip()
	if not api_key:
		print("missing --api-key or DASHSCOPE_API_KEY", file=sys.stderr)
		return 2

	ffmpeg = shutil.which("ffmpeg")
	ffprobe = shutil.which("ffprobe")
	if not ffmpeg or not ffprobe:
		print("ffmpeg/ffprobe required on PATH", file=sys.stderr)
		return 2

	timings = StageTimingsMs()
	total_start = time.perf_counter()
	with tempfile.TemporaryDirectory(prefix="cloud-asr-bench-") as tmp:
		audio_path = Path(tmp) / f"{input_path.stem}.16k.wav"
		t0 = time.perf_counter()
		duration_s = probe_duration_s(input_path, ffprobe)
		timings.ffprobe_ms = (time.perf_counter() - t0) * 1000
		t0 = time.perf_counter()
		extract_wav(ffmpeg, input_path, audio_path)
		timings.ffmpeg_extract_ms = (time.perf_counter() - t0) * 1000
		if duration_s is None:
			duration_s = probe_duration_s(audio_path, ffprobe)

		result, cloud = transcribe_dashscope_paraformer(
			audio_path=audio_path,
			api_key=api_key,
			model=args.model,
			audio_duration_s=duration_s,
			progress_cb=lambda msg: print(msg),
		)
		timings.upload_ms = cloud.upload_ms
		timings.submit_ms = cloud.submit_ms
		timings.wait_ms = cloud.wait_ms
		timings.download_ms = cloud.download_ms
		timings.total_ms = (time.perf_counter() - total_start) * 1000

	transcript = result.to_transcript_dict()
	preview = " ".join(s["text"] for s in transcript.get("segments", [])[:3])[:240]
	report = BenchReport(
		model=args.model,
		input_path=str(input_path),
		audio_path=str(audio_path),
		audio_duration_s=duration_s,
		transcript_preview=preview,
		sentence_count=len(transcript.get("segments") or []),
		timings_ms=timings,
	)

	print("\n=== Cloud ASR benchmark ===")
	print(f"duration: {duration_s:.1f}s" if duration_s else "duration: unknown")
	print(f"wait: {timings.wait_ms:.0f}ms total: {timings.total_ms:.0f}ms")
	print(f"preview: {preview}")

	if args.output_dir:
		args.output_dir.mkdir(parents=True, exist_ok=True)
		stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
		out = args.output_dir / f"cloud-asr-bench-{stamp}.json"
		out.write_text(json.dumps({**asdict(report), "transcript": transcript}, ensure_ascii=False, indent=2), encoding="utf-8")
		print(f"saved: {out}")

	return 0


if __name__ == "__main__":
	raise SystemExit(main())
