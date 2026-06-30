from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from core.asr.runtime import AsrRuntimeSettings
from core.app.pipeline.asr_router import transcribe_with_router
from core.external.asr_faster_whisper import AsrResult, AsrSegment
from core.external.asr_providers.base import AsrCloudError
from core.external.asr_providers.normalize import (
	segments_from_dashscope_transcription,
	segments_from_openai_verbose,
	segments_from_volcengine_result,
)


def test_normalize_dashscope_sentences():
	data = {
		"transcripts": [
			{
				"sentences": [
					{"begin_time": 100, "end_time": 900, "text": "你好"},
					{"begin_time": 900, "end_time": 1500, "text": "世界"},
				]
			}
		]
	}
	segments, _lang = segments_from_dashscope_transcription(data)
	assert len(segments) == 2
	assert segments[0].start_ms == 100
	assert segments[0].text == "你好"


def test_normalize_openai_verbose_seconds_to_ms():
	data = {
		"language": "zh",
		"segments": [
			{"start": 0.1, "end": 1.2, "text": " hello "},
		],
	}
	segments, lang = segments_from_openai_verbose(data)
	assert lang == "zh"
	assert len(segments) == 1
	assert segments[0].start_ms == 100
	assert segments[0].end_ms == 1200
	assert segments[0].text == "hello"


def test_normalize_volcengine_utterances():
	data = {
		"result": {
			"text": "整段",
			"utterances": [
				{"start_time": 0, "end_time": 500, "text": "第一句"},
				{"start_time": 500, "end_time": 1000, "text": "第二句"},
			],
		}
	}
	segments, _ = segments_from_volcengine_result(data)
	assert len(segments) == 2
	assert segments[1].text == "第二句"


def test_router_uses_local_when_cloud_disabled(tmp_path: Path):
	wav = tmp_path / "a.wav"
	wav.write_bytes(b"RIFF")
	settings = AsrRuntimeSettings(
		cloud_enabled=False,
		provider_id="dashscope",
		model_id="paraformer-v2",
		language_hints=["zh"],
		local_model_size="base",
		local_device="cpu",
		fallback_to_local=True,
		api_key="sk-test",
		configured=True,
	)
	mock_result = AsrResult(provider="faster-whisper", language="zh", segments=[AsrSegment(0, 100, "hi")])
	with patch("core.app.pipeline.asr_router._local_transcribe", return_value=mock_result) as local_fn:
		out = transcribe_with_router(audio_path=wav, settings=settings, audio_duration_s=1.0)
	assert out.asr_mode == "local"
	assert out.fallback_from is None
	local_fn.assert_called_once()


def test_router_falls_back_on_cloud_error(tmp_path: Path):
	wav = tmp_path / "a.wav"
	wav.write_bytes(b"RIFF")
	settings = AsrRuntimeSettings(
		cloud_enabled=True,
		provider_id="dashscope",
		model_id="paraformer-v2",
		language_hints=["zh"],
		local_model_size="base",
		local_device="cpu",
		fallback_to_local=True,
		api_key="sk-test",
		configured=True,
	)
	mock_result = AsrResult(provider="faster-whisper", language="zh", segments=[AsrSegment(0, 100, "hi")])
	with patch(
		"core.app.pipeline.asr_router._cloud_transcribe",
		side_effect=AsrCloudError("auth", "bad key"),
	), patch("core.app.pipeline.asr_router._local_transcribe", return_value=mock_result):
		out = transcribe_with_router(audio_path=wav, settings=settings, audio_duration_s=1.0)
	assert out.asr_mode == "local"
	assert out.fallback_from == "dashscope"
	assert out.fallback_reason == "auth"


def test_asr_settings_catalog_api(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
	monkeypatch.setenv("DATA_DIR", str(tmp_path))
	from fastapi.testclient import TestClient
	from core.main import create_app

	with TestClient(create_app()) as client:
		resp = client.get("/api/v1/settings/asr/catalog")
		assert resp.status_code == 200
		body = resp.json()
		assert "providers" in body
		ids = {p["providerId"] for p in body["providers"]}
		assert ids == {"dashscope", "openai", "volcengine"}


def test_asr_connectivity_test_dashscope_uses_get_policy(monkeypatch: pytest.MonkeyPatch):
	from core.asr.active_test import run_asr_connectivity_test

	settings = AsrRuntimeSettings(
		cloud_enabled=True,
		provider_id="dashscope",
		model_id="paraformer-v2",
		language_hints=["zh"],
		local_model_size="base",
		local_device="cpu",
		fallback_to_local=True,
		api_key="sk-test",
		configured=True,
	)

	class FakeResp:
		status_code = 200

		@staticmethod
		def json():
			return {"data": {"upload_host": "https://oss.example.com"}}

	called: dict[str, str] = {}

	def fake_get(url, *, headers, params):
		called["url"] = url
		called["auth"] = headers.get("Authorization", "")
		called["model"] = params.get("model", "")
		return FakeResp()

	class FakeClient:
		def __init__(self, *args, **kwargs):
			pass

		def __enter__(self):
			return self

		def __exit__(self, *args):
			return False

		get = staticmethod(fake_get)

	monkeypatch.setattr("core.asr.active_test.httpx.Client", FakeClient)
	ok, latency_ms, mode, message = run_asr_connectivity_test(settings)
	assert ok is True
	assert latency_ms >= 0
	assert mode == "cloud"
	assert message is None
	assert called["model"] == "paraformer-v2"
	assert called["auth"] == "Bearer sk-test"


def test_asr_cloud_timings_mutable():
	from core.external.asr_providers.base import AsrCloudTimingsMs

	timings = AsrCloudTimingsMs()
	timings.upload_ms = 12.5
	timings.total_ms = 100.0
	assert timings.upload_ms == 12.5
	assert timings.total_ms == 100.0


def test_asr_active_put_get(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
	monkeypatch.setenv("DATA_DIR", str(tmp_path))
	from fastapi.testclient import TestClient
	from core.main import create_app

	with TestClient(create_app()) as client:
		put = client.put(
			"/api/v1/settings/asr/active",
			json={
				"cloudEnabled": True,
				"providerId": "dashscope",
				"modelId": "paraformer-v2",
				"languageHints": ["zh", "en"],
				"fallbackToLocal": True,
			},
		)
		assert put.status_code == 200
		get = client.get("/api/v1/settings/asr/active")
		assert get.status_code == 200
		body = get.json()
		assert body["configured"] is True
		assert body["providerId"] == "dashscope"
		assert body["modelId"] == "paraformer-v2"
		assert body["cloudEnabled"] is True
