from __future__ import annotations

from pathlib import Path


def test_legacy_pipeline_files_removed() -> None:
	project_root = Path(__file__).resolve().parents[1]  # services/core
	legacy_paths = [
		project_root / "src" / "core" / "app" / "pipeline" / "segment.py",
		project_root / "src" / "core" / "app" / "pipeline" / "highlights.py",
		project_root / "src" / "core" / "app" / "pipeline" / "mindmap.py",
		project_root / "src" / "core" / "app" / "pipeline" / "transcribe.py",
		project_root / "src" / "core" / "pipeline" / "stages" / "segment.py",
		project_root / "src" / "core" / "pipeline" / "stages" / "ingest.py",
		project_root / "src" / "core" / "pipeline" / "stages" / "transcribe.py",
		project_root / "src" / "core" / "pipeline" / "stages" / "analyze.py",
	]

	existing = [str(p) for p in legacy_paths if p.exists()]
	assert not existing, "Legacy pipeline files should be removed: " + ", ".join(existing)


def test_plan_pipeline_imports_ok() -> None:
	from core.app.pipeline.llm_plan import generate_plan  # noqa: F401
	from core.app.worker.worker_loop import PipelineJobProcessor  # noqa: F401
