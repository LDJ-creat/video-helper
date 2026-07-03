"""Real OpenAI-compatible SSE integration test for LLM token usage extraction.

Exercises ``LLMAnalyzeProvider.generate_json()`` against a live endpoint (streaming)
and verifies ``llm_usage.jsonl`` is written with plausible token counts.

Requires (environment or ``services/core/.env``):

- ``LLM_API_BASE`` — OpenAI-compatible base URL (not Anthropic)
- ``LLM_API_KEY``
- ``LLM_MODEL`` — optional; provider default applies if unset

Run:

```bash
cd services/core
uv run pytest tests/test_llm_usage_real.py -v -s -m integration
```

Optional:

- ``LLM_USAGE_REAL_REQUIRE_API=1`` — fail instead of skip when the gateway
  does not return usage (only ``estimated`` fallback is available).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

load_dotenv(".env")

pytestmark = pytest.mark.integration


def _env_bool(name: str) -> bool:
	return (os.environ.get(name) or "").strip().lower() in {"1", "true", "yes", "on"}


def _is_openai_compat_configured() -> bool:
	base = (os.environ.get("LLM_API_BASE") or "").strip()
	key = (os.environ.get("LLM_API_KEY") or "").strip()
	if not base or not key:
		return False
	kind = (os.environ.get("LLM_API_KIND") or "").strip().lower()
	if kind == "anthropic":
		return False
	if "anthropic.com" in base.lower():
		return False
	return True


if not _is_openai_compat_configured():
	pytest.skip(
		"OpenAI-compatible LLM not configured (set LLM_API_BASE + LLM_API_KEY; not Anthropic)",
		allow_module_level=True,
	)


@pytest.fixture
def real_openai_compat_provider():
	from core.app.pipeline.analyze_provider import llm_provider_from_env

	return llm_provider_from_env()


def test_real_openai_compat_sse_extracts_token_usage(
	tmp_path: Path,
	monkeypatch: pytest.MonkeyPatch,
	real_openai_compat_provider,
) -> None:
	"""Live SSE call: parse usage from stream and persist to llm_usage.jsonl."""
	from core.app.pipeline.llm_usage_context import clear_llm_usage_context, set_llm_usage_context

	monkeypatch.setenv("DATA_DIR", str(tmp_path))
	monkeypatch.setenv("LLM_STREAM_INCLUDE_USAGE", "1")
	monkeypatch.setenv("LLM_USAGE_ESTIMATE_FALLBACK", "0")

	project_id = "proj-usage-real"
	job_id = "job-usage-real"
	set_llm_usage_context(project_id=project_id, job_id=job_id)
	try:
		out = real_openai_compat_provider.generate_json(
			"plan_content_blocks",
			{
				"messages": [
					{
						"role": "system",
						"content": 'Return only one JSON object: {"ok": true}. No markdown.',
					},
					{"role": "user", "content": "{}"},
				],
			},
			max_tokens=64,
		)
	finally:
		clear_llm_usage_context()

	assert isinstance(out, dict)
	assert out.get("ok") is True

	usage_path = tmp_path / project_id / "artifacts" / job_id / "llm_usage.jsonl"
	assert usage_path.exists(), f"expected artifact at {usage_path}"

	rows = [json.loads(line) for line in usage_path.read_text(encoding="utf-8").splitlines() if line.strip()]
	assert len(rows) == 1
	record = rows[0]

	assert record.get("task") == "plan_content_blocks"
	assert record.get("stage") == "analyze"
	assert record.get("providerKind") == "openai_compat"

	source = str(record.get("source") or "")
	prompt = record.get("promptTokens")
	completion = record.get("completionTokens")
	total = record.get("totalTokens")

	print(
		"\n[llm_usage_real] "
		f"source={source} prompt={prompt} completion={completion} total={total} "
		f"model={record.get('model')}"
	)

	if source != "api":
		msg = (
			f"Gateway did not return stream usage (source={source!r}). "
			"Parsing may still work if the provider sends a trailing usage chunk; "
			"check whether your endpoint supports stream_options.include_usage. "
			"Set LLM_USAGE_REAL_REQUIRE_API=1 to fail hard on this condition."
		)
		if _env_bool("LLM_USAGE_REAL_REQUIRE_API"):
			pytest.fail(msg)
		pytest.skip(msg)

	assert isinstance(prompt, int) and prompt > 0
	assert isinstance(completion, int) and completion > 0
	assert isinstance(total, int) and total > 0
	assert total >= prompt
	assert total >= completion
