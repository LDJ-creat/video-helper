from __future__ import annotations

import json
import logging
import os
import uuid
from typing import AsyncGenerator, Any
from urllib.parse import urlparse

import httpx

from core.app.pipeline.analyze_provider import llm_provider_for_jobs, llm_runtime_for_jobs, AnalyzeError, ErrorCode, _env_int
from core.schemas.ai import QuizDTO, QuizItemDTO, ChatMessageDTO

logger = logging.getLogger(__name__)

QUIZ_SYS_PROMPT = """You are an expert educational AI assistant.
Your goal is to generate a high-quality quiz based on the provided video content.
Focus on key concepts, facts, and understanding.
Output must be valid JSON matching the specified schema.
"""

QUIZ_USER_PROMPT_TEMPLATE = """
Context:
{context}

Topic Focus: {topic}

Generate 5 multiple-choice questions.
Format:
{{
  "items": [
    {{
      "question": "Question text",
      "options": ["Option 1", "Option 2", "Option 3", "Option 4"],
      "correct_answer": "Option 1",
      "explanation": "Brief explanation of why this is correct."
    }}
  ]
}}
"""

def generate_quiz(context_text: str, project_id: str, topic_focus: str | None = None) -> QuizDTO:
    """Generate a quiz based on context."""
    provider = llm_provider_for_jobs()
    if not provider:
        raise AnalyzeError(code=ErrorCode.JOB_STAGE_FAILED, message="LLM not configured")

    topic = topic_focus or "General understanding"
    
    # Truncate context if too long? 
    # For now assume it fits.
    
    messages = [
        {"role": "system", "content": QUIZ_SYS_PROMPT},
        {"role": "user", "content": QUIZ_USER_PROMPT_TEMPLATE.format(context=context_text[:100000], topic=topic)} 
    ]
    
    try:
        data = provider.generate_json(task_name=f"quiz-{project_id}", input_dict={"messages": messages})
    except Exception as e:
        logger.error(f"Quiz generation failed: {e}")
        raise e

    # Map to schemas
    items = []
    for item in data.get("items", []):
        # Generate hash for simple dedup/tracking
        import hashlib
        q_hash = hashlib.md5(item["question"].encode()).hexdigest()
        
        items.append(QuizItemDTO(
            questionHash=q_hash,
            question=item["question"],
            options=item["options"],
            correctAnswer=item["correct_answer"],
            explanation=item.get("explanation", "")
        ))
        
    return QuizDTO(sessionId=str(uuid.uuid4()), items=items)


async def stream_chat(
    history: list[ChatMessageDTO], 
    video_context: str, 
    project_id: str
) -> AsyncGenerator[str, None]:
    """Stream chat response."""
    
    rt = llm_runtime_for_jobs()
    if rt is None:
        yield json.dumps({"error": "LLM not configured"})
        return

    # Construct messages
    sys_msg = "You are a helpful assistant answering questions about a video. Use the provided context."
    
    messages = [{"role": "system", "content": sys_msg}]
    if video_context:
        messages.append({"role": "system", "content": f"Video Context:\n{video_context[:50000]}"})
        
    for msg in history:
        messages.append({"role": msg.role, "content": msg.content})

    def _is_anthropic_base_url(api_base: str) -> bool:
        try:
            p = urlparse(api_base)
            host = (p.netloc or "").lower()
            return host.endswith("anthropic.com")
        except Exception:
            return False

    api_base = rt.api_base
    api_key = rt.api_key
    model = rt.model
    timeout = float(max(1, int(rt.timeout_s)))

    if (rt.provider_id or "").strip().lower() == "anthropic" or _is_anthropic_base_url(api_base):
        url = api_base.rstrip("/")
        lower = url.lower()
        if lower.endswith("/v1/messages"):
            pass
        elif lower.endswith("/v1"):
            url += "/messages"
        else:
            url += "/v1/messages"

        system_parts = [m["content"] for m in messages if isinstance(m, dict) and m.get("role") == "system" and isinstance(m.get("content"), str)]
        user_assistant = [m for m in messages if isinstance(m, dict) and m.get("role") in {"user", "assistant"}]
        anth_msgs = []
        for m in user_assistant:
            content = m.get("content")
            if not isinstance(content, str):
                content = "" if content is None else str(content)
            anth_msgs.append({"role": m.get("role"), "content": content})

        payload = {
            "model": model,
            "max_tokens": 1024,
            "messages": anth_msgs or [{"role": "user", "content": "Hello"}],
            "temperature": 0.5,
        }
        if system_parts:
            payload["system"] = "\n\n".join([p for p in system_parts if p.strip()])

        version = (os.environ.get("ANTHROPIC_VERSION") or "2023-06-01").strip() or "2023-06-01"
        headers = {
            "x-api-key": api_key,
            "anthropic-version": version,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        logger.info(f"Connecting to Anthropic at {url} with model {model}")

        try:
            async with httpx.AsyncClient(timeout=timeout, trust_env=True) as client:
                resp = await client.post(url, json=payload, headers=headers)
                if resp.status_code != 200:
                    yield json.dumps({"content": f"\n\n**Error**: LLM Provider returned {resp.status_code}."})
                    return
                body = resp.json()
                content = body.get("content") if isinstance(body, dict) else None
                parts: list[str] = []
                if isinstance(content, list):
                    for b in content:
                        if isinstance(b, dict) and b.get("type") == "text" and isinstance(b.get("text"), str):
                            parts.append(b["text"])
                full = "".join(parts).strip()
                if full:
                    yield full
        except Exception as e:
            logger.exception(f"Unexpected error in stream_chat (anthropic): {e}")
            yield json.dumps({"content": f"\n\n**System Error**: {str(e)}"})
        return

    # OpenAI-compatible streaming
    url = api_base.rstrip("/")
    lower = url.lower()
    if lower.endswith("/v1"):
        url += "/chat/completions"
    elif lower.endswith("/chat/completions") or lower.endswith("/v1/chat/completions") or lower.endswith("/responses") or lower.endswith("/v1/responses"):
        pass
    else:
        url += "/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
    }

    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
        "temperature": 0.5,
    }

    logger.info(f"Connecting to LLM at {url} with model {model}")

    try:
        async with httpx.AsyncClient(timeout=timeout, trust_env=True) as client:
            try:
                async with client.stream("POST", url, json=payload, headers=headers) as response:
                    if response.status_code != 200:
                        err_text = await response.read()
                        logger.error(f"Chat stream error: {response.status_code} - {err_text}")
                        yield json.dumps({"content": f"\n\n**Error**: LLM Provider returned {response.status_code}."})
                        return

                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data_str = line[6:]
                            if data_str.strip() == "[DONE]":
                                break
                            try:
                                chunk = json.loads(data_str)
                                choices = chunk.get("choices", [])
                                if choices:
                                    delta = choices[0].get("delta", {})
                                    content = delta.get("content")
                                    if content:
                                        yield content
                            except json.JSONDecodeError:
                                continue
            except httpx.ConnectError as e:
                logger.error(f"Connection failed to {url}: {e}")
                yield json.dumps({"content": f"\n\n**Connection Error**: Could not connect to LLM provider at `{url}`.\nPlease check your network or API settings."})
            except httpx.ReadTimeout as e:
                logger.error(f"Read timeout from {url}: {e}")
                yield json.dumps({"content": "\n\n**Timeout**: LLM didn't respond in time."})
    except Exception as e:
        logger.exception(f"Unexpected error in stream_chat: {e}")
        yield json.dumps({"content": f"\n\n**System Error**: {str(e)}"})
