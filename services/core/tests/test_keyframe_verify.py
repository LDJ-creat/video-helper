from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from core.app.pipeline import keyframe_verify as kv
from core.app.pipeline.keyframe_verify import (
    VerifyBudget,
    compute_retry_time_ms,
    drop_retried_highlights_missing_asset,
    verify_keyframes_after_retry,
    verify_keyframes_initial,
)


class _MockProvider:
    def __init__(self, responses: list[dict]) -> None:
        self._responses = list(responses)
        self.calls = 0

    def generate_json(self, task_name: str, input_dict: dict, *, max_tokens: int | None = None) -> dict:
        del task_name, input_dict, max_tokens
        idx = min(self.calls, len(self._responses) - 1)
        self.calls += 1
        return self._responses[idx]


def _content_blocks(
    *,
    highlight_id: str = "h0",
    time_ms: int = 5000,
    confidence: float = 0.2,
    start_ms: int = 1000,
    end_ms: int = 10000,
) -> list[dict]:
    kf = {"timeMs": time_ms, "assetId": "asset-1"}
    return [
        {
            "blockId": "b0",
            "highlights": [
                {
                    "highlightId": highlight_id,
                    "text": "slide about topic",
                    "startMs": start_ms,
                    "endMs": end_ms,
                    "keyframeConfidence": confidence,
                    "keyframes": [dict(kf)],
                    "keyframe": dict(kf),
                }
            ],
        }
    ]


def _patch_verify_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    img = tmp_path / "frame.jpg"
    img.write_bytes(b"\xff\xd8\xff" + b"x" * 100)
    monkeypatch.setattr(kv, "get_data_dir", lambda: tmp_path)
    monkeypatch.setattr(
        kv,
        "_resolve_asset_image_abs",
        lambda **kwargs: img,
    )
    monkeypatch.setattr(
        kv,
        "_encode_image_data_url",
        lambda **kwargs: "data:image/jpeg;base64,ZmFrZQ==",
    )
    monkeypatch.setenv("KEYFRAME_VERIFY_CONFIDENCE_THRESHOLD", "0.4")


def test_compute_retry_time_ms_llm_hint_after() -> None:
    new_tm = compute_retry_time_ms(
        time_ms=5000,
        start_ms=1000,
        end_ms=10000,
        local_search_window_ms=8000,
        retry_direction="after",
        retry_offset_ms=3000,
    )
    assert new_tm == 8000


def test_compute_retry_time_ms_llm_hint_before() -> None:
    new_tm = compute_retry_time_ms(
        time_ms=5000,
        start_ms=1000,
        end_ms=10000,
        local_search_window_ms=8000,
        retry_direction="before",
        retry_offset_ms=2000,
    )
    assert new_tm == 3000


def test_compute_retry_time_ms_clamps_to_window() -> None:
    new_tm = compute_retry_time_ms(
        time_ms=5000,
        start_ms=1000,
        end_ms=6000,
        local_search_window_ms=10000,
        retry_direction="after",
        retry_offset_ms=50000,
    )
    assert new_tm == 5999


def test_compute_retry_time_ms_fallback_midpoint() -> None:
    new_tm = compute_retry_time_ms(
        time_ms=2000,
        start_ms=1000,
        end_ms=10000,
        local_search_window_ms=5000,
        retry_direction=None,
        retry_offset_ms=None,
    )
    assert 1000 <= new_tm < 10000
    assert new_tm != 2000


def test_initial_keep_no_retry(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_verify_env(monkeypatch, tmp_path)
    provider = _MockProvider([{"keep": True, "confidence": 0.9, "reason": "good slide"}])
    monkeypatch.setattr(kv, "llm_provider_for_jobs", lambda: provider)

    blocks = _content_blocks()
    retry_times, scheduled, stats = verify_keyframes_initial(
        session=MagicMock(),
        project_id="p1",
        job_id="j1",
        content_blocks=blocks,
        output_language=None,
        mode="multimodal",
    )

    assert retry_times == []
    assert scheduled == []
    assert stats.verified_count == 1
    assert blocks[0]["highlights"][0]["keyframes"][0]["timeMs"] == 5000
    assert provider.calls == 1


def test_initial_fail_schedules_retry(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_verify_env(monkeypatch, tmp_path)
    provider = _MockProvider([{"keep": False, "confidence": 0.1, "reason": "talking head"}])
    monkeypatch.setattr(kv, "llm_provider_for_jobs", lambda: provider)

    blocks = _content_blocks()
    retry_times, scheduled, stats = verify_keyframes_initial(
        session=MagicMock(),
        project_id="p1",
        job_id="j1",
        content_blocks=blocks,
        output_language=None,
        mode="multimodal",
    )

    assert len(retry_times) == 1
    assert scheduled == ["h0"]
    assert stats.retry_scheduled_count == 1
    assert blocks[0]["highlights"][0]["keyframes"][0]["timeMs"] != 5000
    assert provider.calls == 1


def test_retry_hint_direction_used(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_verify_env(monkeypatch, tmp_path)
    provider = _MockProvider(
        [
            {
                "keep": False,
                "confidence": 0.1,
                "reason": "no slide yet",
                "retry": {"direction": "after", "offsetMs": 2000},
            }
        ]
    )
    monkeypatch.setattr(kv, "llm_provider_for_jobs", lambda: provider)

    blocks = _content_blocks(time_ms=3000)
    retry_times, _, _ = verify_keyframes_initial(
        session=MagicMock(),
        project_id="p1",
        job_id="j1",
        content_blocks=blocks,
        output_language=None,
        mode="multimodal",
    )

    assert retry_times == [5000]


def test_after_retry_kept(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_verify_env(monkeypatch, tmp_path)
    provider = _MockProvider([{"keep": True, "confidence": 0.85, "reason": "slide visible"}])
    monkeypatch.setattr(kv, "llm_provider_for_jobs", lambda: provider)

    blocks = _content_blocks(time_ms=7000)
    stats = verify_keyframes_after_retry(
        session=MagicMock(),
        project_id="p1",
        job_id="j1",
        content_blocks=blocks,
        output_language=None,
        mode="multimodal",
        retried_highlight_ids=["h0"],
        verify_used_job=1,
    )

    assert stats.retried_kept_count == 1
    assert stats.retried_dropped_count == 0
    assert blocks[0]["highlights"][0]["keyframes"]


def test_after_retry_dropped(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_verify_env(monkeypatch, tmp_path)
    provider = _MockProvider([{"keep": False, "confidence": 0.1, "reason": "still bad"}])
    monkeypatch.setattr(kv, "llm_provider_for_jobs", lambda: provider)

    blocks = _content_blocks(time_ms=7000)
    stats = verify_keyframes_after_retry(
        session=MagicMock(),
        project_id="p1",
        job_id="j1",
        content_blocks=blocks,
        output_language=None,
        mode="multimodal",
        retried_highlight_ids=["h0"],
        verify_used_job=1,
    )

    assert stats.retried_kept_count == 0
    assert stats.retried_dropped_count == 1
    assert blocks[0]["highlights"][0]["keyframes"] == []
    assert blocks[0]["highlights"][0]["keyframe"] is None


def test_per_highlight_retry_independent(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_verify_env(monkeypatch, tmp_path)
    provider = _MockProvider(
        [
            {"keep": False, "confidence": 0.1, "reason": "bad1"},
            {"keep": False, "confidence": 0.1, "reason": "bad2"},
        ]
    )
    monkeypatch.setattr(kv, "llm_provider_for_jobs", lambda: provider)

    blocks = [
        {
            "blockId": "b0",
            "highlights": [
                {
                    "highlightId": "h0",
                    "text": "a",
                    "startMs": 1000,
                    "endMs": 10000,
                    "keyframeConfidence": 0.2,
                    "keyframes": [{"timeMs": 2000, "assetId": "asset-1"}],
                    "keyframe": {"timeMs": 2000, "assetId": "asset-1"},
                },
                {
                    "highlightId": "h1",
                    "text": "b",
                    "startMs": 1000,
                    "endMs": 10000,
                    "keyframeConfidence": 0.1,
                    "keyframes": [{"timeMs": 3000, "assetId": "asset-1"}],
                    "keyframe": {"timeMs": 3000, "assetId": "asset-1"},
                },
            ],
        }
    ]

    retry_times, scheduled, stats = verify_keyframes_initial(
        session=MagicMock(),
        project_id="p1",
        job_id="j1",
        content_blocks=blocks,
        output_language=None,
        mode="multimodal",
    )

    assert len(retry_times) == 2
    assert set(scheduled) == {"h0", "h1"}
    assert stats.retry_scheduled_count == 2
    assert provider.calls == 2


def test_concurrency_respects_max_per_job(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_verify_env(monkeypatch, tmp_path)
    monkeypatch.setenv("KEYFRAME_VERIFY_MAX_PER_JOB", "2")
    monkeypatch.setenv("KEYFRAME_VERIFY_CONCURRENCY", "3")

    provider = _MockProvider(
        [
            {"keep": True, "confidence": 0.9, "reason": "ok"},
            {"keep": True, "confidence": 0.9, "reason": "ok"},
            {"keep": True, "confidence": 0.9, "reason": "ok"},
        ]
    )
    monkeypatch.setattr(kv, "llm_provider_for_jobs", lambda: provider)

    blocks = [
        {
            "blockId": "b0",
            "highlights": [
                {
                    "highlightId": f"h{i}",
                    "text": f"t{i}",
                    "startMs": 1000,
                    "endMs": 10000,
                    "keyframeConfidence": 0.2,
                    "keyframes": [{"timeMs": 2000 + i * 100, "assetId": "asset-1"}],
                    "keyframe": {"timeMs": 2000 + i * 100, "assetId": "asset-1"},
                }
                for i in range(3)
            ],
        }
    ]

    _, _, stats = verify_keyframes_initial(
        session=MagicMock(),
        project_id="p1",
        job_id="j1",
        content_blocks=blocks,
        output_language=None,
        mode="multimodal",
        budget=VerifyBudget(
            max_verify_per_highlight=1,
            max_verify_per_job=2,
            retry_max_per_highlight=1,
            local_search_window_ms=10_000,
        ),
    )

    assert provider.calls == 2
    assert stats.verified_count == 2


def test_initial_fail_no_retry_budget_drops(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_verify_env(monkeypatch, tmp_path)
    provider = _MockProvider([{"keep": False, "confidence": 0.1, "reason": "bad"}])
    monkeypatch.setattr(kv, "llm_provider_for_jobs", lambda: provider)

    blocks = _content_blocks()
    retry_times, _, stats = verify_keyframes_initial(
        session=MagicMock(),
        project_id="p1",
        job_id="j1",
        content_blocks=blocks,
        output_language=None,
        mode="multimodal",
        budget=VerifyBudget(
            max_verify_per_highlight=1,
            max_verify_per_job=5,
            retry_max_per_highlight=0,
            local_search_window_ms=10_000,
        ),
    )

    assert retry_times == []
    assert stats.dropped_count == 1
    assert blocks[0]["highlights"][0]["keyframes"] == []


def test_prepare_failure_drops_initial(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_verify_env(monkeypatch, tmp_path)
    monkeypatch.setattr(kv, "_prepare_candidate_messages", lambda **kwargs: None)
    provider = _MockProvider([{"keep": True, "confidence": 0.9, "reason": "ok"}])
    monkeypatch.setattr(kv, "llm_provider_for_jobs", lambda: provider)

    blocks = _content_blocks()
    _, _, stats = verify_keyframes_initial(
        session=MagicMock(),
        project_id="p1",
        job_id="j1",
        content_blocks=blocks,
        output_language=None,
        mode="multimodal",
    )

    assert provider.calls == 0
    assert stats.skipped_prepare_count == 1
    assert stats.dropped_count == 1
    assert blocks[0]["highlights"][0]["keyframes"] == []


def test_retry_verify_runs_when_initial_budget_exhausted(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_verify_env(monkeypatch, tmp_path)

    class _BudgetProvider:
        def __init__(self) -> None:
            self.calls = 0

        def generate_json(self, task_name: str, input_dict: dict, *, max_tokens: int | None = None) -> dict:
            del task_name, input_dict, max_tokens
            self.calls += 1
            if self.calls == 1:
                return {"keep": False, "confidence": 0.1, "reason": "bad1"}
            return {"keep": True, "confidence": 0.9, "reason": "good retry"}

    provider = _BudgetProvider()
    monkeypatch.setattr(kv, "llm_provider_for_jobs", lambda: provider)

    blocks = [
        {
            "blockId": "b0",
            "highlights": [
                {
                    "highlightId": "h0",
                    "text": "a",
                    "startMs": 1000,
                    "endMs": 10000,
                    "keyframeConfidence": 0.2,
                    "keyframes": [{"timeMs": 2000, "assetId": "asset-1"}],
                    "keyframe": {"timeMs": 2000, "assetId": "asset-1"},
                },
                {
                    "highlightId": "h1",
                    "text": "b",
                    "startMs": 1000,
                    "endMs": 10000,
                    "keyframeConfidence": 0.1,
                    "keyframes": [{"timeMs": 3000, "assetId": "asset-1"}],
                    "keyframe": {"timeMs": 3000, "assetId": "asset-1"},
                },
            ],
        }
    ]

    budget = VerifyBudget(
        max_verify_per_highlight=1,
        max_verify_per_job=1,
        retry_max_per_highlight=1,
        local_search_window_ms=10_000,
    )
    _, scheduled, initial_stats = verify_keyframes_initial(
        session=MagicMock(),
        project_id="p1",
        job_id="j1",
        content_blocks=blocks,
        output_language=None,
        mode="multimodal",
        budget=budget,
    )
    assert provider.calls == 1
    assert scheduled == ["h0"]
    assert initial_stats.verify_used_job == 1

    blocks[0]["highlights"][0]["keyframes"] = [{"timeMs": 7000, "assetId": "asset-1"}]
    blocks[0]["highlights"][0]["keyframe"] = {"timeMs": 7000, "assetId": "asset-1"}

    retry_stats = verify_keyframes_after_retry(
        session=MagicMock(),
        project_id="p1",
        job_id="j1",
        content_blocks=blocks,
        output_language=None,
        mode="multimodal",
        retried_highlight_ids=scheduled,
        budget=budget,
        verify_used_job=initial_stats.verify_used_job,
    )

    assert provider.calls == 2
    assert retry_stats.retried_kept_count == 1
    assert blocks[0]["highlights"][0]["keyframes"]


def test_drop_retried_highlights_missing_asset() -> None:
    blocks = [
        {
            "blockId": "b0",
            "highlights": [
                {
                    "highlightId": "h0",
                    "text": "a",
                    "startMs": 1000,
                    "endMs": 10000,
                    "keyframes": [{"timeMs": 7000}],
                    "keyframe": {"timeMs": 7000},
                }
            ],
        }
    ]
    remaining = drop_retried_highlights_missing_asset(
        content_blocks=blocks,
        scheduled_highlight_ids=["h0"],
        project_id="p1",
        job_id="j1",
        mode="multimodal",
    )
    assert remaining == []
    assert blocks[0]["highlights"][0]["keyframes"] == []


def test_verify_orchestration_sequence(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Simulate worker order: initial -> re-extract asset backfill -> drop missing -> after_retry."""

    _patch_verify_env(monkeypatch, tmp_path)
    calls: list[str] = []

    class _SeqProvider:
        def __init__(self) -> None:
            self.calls = 0

        def generate_json(self, task_name: str, input_dict: dict, *, max_tokens: int | None = None) -> dict:
            del task_name, input_dict, max_tokens
            self.calls += 1
            if self.calls == 1:
                calls.append("initial")
                return {"keep": False, "confidence": 0.1, "reason": "bad"}
            calls.append("retry")
            return {"keep": True, "confidence": 0.9, "reason": "fixed"}

    provider = _SeqProvider()
    monkeypatch.setattr(kv, "llm_provider_for_jobs", lambda: provider)

    blocks = _content_blocks()
    retry_times, scheduled, initial_stats = verify_keyframes_initial(
        session=MagicMock(),
        project_id="p1",
        job_id="j1",
        content_blocks=blocks,
        output_language=None,
        mode="multimodal",
    )
    assert calls == ["initial"]
    assert retry_times
    assert scheduled == ["h0"]

    new_tm = retry_times[0]
    blocks[0]["highlights"][0]["keyframes"] = [{"timeMs": new_tm, "assetId": "asset-1"}]
    blocks[0]["highlights"][0]["keyframe"] = {"timeMs": new_tm, "assetId": "asset-1"}

    eligible = drop_retried_highlights_missing_asset(
        content_blocks=blocks,
        scheduled_highlight_ids=scheduled,
        project_id="p1",
        job_id="j1",
        mode="multimodal",
    )
    assert eligible == ["h0"]

    retry_stats = verify_keyframes_after_retry(
        session=MagicMock(),
        project_id="p1",
        job_id="j1",
        content_blocks=blocks,
        output_language=None,
        mode="multimodal",
        retried_highlight_ids=eligible,
        verify_used_job=initial_stats.verify_used_job,
    )
    assert calls == ["initial", "retry"]
    assert retry_stats.retried_kept_count == 1
