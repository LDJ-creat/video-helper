from __future__ import annotations

import os
import sys
from pathlib import Path

import httpx


def _load_env_file(path: Path) -> None:
    """Minimal dotenv loader.

    Loads KEY=VALUE pairs into os.environ (does not override existing vars).
    """

    if not path.exists():
        return

    try:
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if not key:
                continue
            os.environ.setdefault(key, value)
    except OSError:
        return


def main() -> int:
    core_root = Path(__file__).resolve().parents[1]
    _load_env_file(core_root / ".env")

    # Ensure imports work when running as a standalone script.
    src_dir = core_root / "src"
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))

    from core.app.pipeline.analyze_provider import _normalize_model_id  # noqa: E402

    api_base = (os.environ.get("LLM_API_BASE") or "").strip().rstrip("/")
    api_key = (os.environ.get("LLM_API_KEY") or "").strip()
    model = _normalize_model_id((os.environ.get("LLM_MODEL") or "minimaxai/minimax-m2.1").strip())
    timeout_s = float((os.environ.get("LLM_TIMEOUT_S") or "120").strip() or "120")

    if not api_base or not api_key:
        print("LLM smoke test FAILED")
        print("missing LLM_API_BASE or LLM_API_KEY")
        return 2

    lower = api_base.lower()
    if lower.endswith("/v1"):
        endpoint = api_base + "/chat/completions"
    elif lower.endswith("/chat/completions") or lower.endswith("/v1/chat/completions"):
        endpoint = api_base
    else:
        endpoint = api_base + "/v1/chat/completions"

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a connectivity smoke test. Reply concisely."},
            {"role": "user", "content": "ping"},
        ],
        "temperature": 0,
        "max_tokens": 16,
        "stream": False,
    }

    print(f"LLM smoke test sending: endpoint={endpoint} model={model} timeout_s={timeout_s}")

    try:
        with httpx.Client(timeout=timeout_s, headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"}) as client:
            resp = client.post(endpoint, json=payload)
    except httpx.TimeoutException:
        print("LLM smoke test FAILED")
        print("timeout")
        return 3
    except httpx.RequestError as e:
        print("LLM smoke test FAILED")
        print(f"request_error={type(e).__name__}")
        return 4

    if resp.status_code >= 400:
        print("LLM smoke test FAILED")
        print(f"httpStatus={resp.status_code}")
        # Avoid dumping sensitive content; show only a short snippet.
        text = (resp.text or "").strip().replace("\n", " ")
        print(f"bodySnippet={text[:200]}")
        return 5

    try:
        body = resp.json()
    except Exception:
        print("LLM smoke test FAILED")
        print("non_json_response")
        print(f"bodyLen={len(resp.text or '')}")
        return 6

    content = None
    if isinstance(body, dict) and isinstance(body.get("choices"), list) and body["choices"]:
        c0 = body["choices"][0]
        if isinstance(c0, dict):
            msg = c0.get("message")
            if isinstance(msg, dict):
                content = msg.get("content")
            elif "text" in c0:
                content = c0.get("text")

    if not isinstance(content, str):
        print("LLM smoke test FAILED")
        print(f"unexpected_response_shape keys={sorted(body.keys()) if isinstance(body, dict) else type(body).__name__}")
        return 7

    answer = content.strip()
    if not answer:
        print("LLM smoke test FAILED")
        print("empty_answer")
        return 8

    expected = (os.environ.get("LLM_SMOKE_EXPECT") or "").strip()
    if expected and expected.lower() not in answer.lower():
        print("LLM smoke test FAILED")
        print(f"expected={expected!r}")
        print(f"answerSnippet={answer[:200]}")
        return 9

    print("LLM smoke test OK")
    print(f"answerSnippet={answer[:200]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
