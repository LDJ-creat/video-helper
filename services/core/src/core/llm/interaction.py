from __future__ import annotations

import json
import logging
from typing import AsyncGenerator, Any

import httpx

from core.app.pipeline.analyze_provider import llm_provider_for_jobs, LLMAnalyzeProvider, AnalyzeError, ErrorCode, _env_int
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
        
    import uuid
    return QuizDTO(sessionId=str(uuid.uuid4()), items=items)


async def stream_chat(
    history: list[ChatMessageDTO], 
    video_context: str, 
    project_id: str
) -> AsyncGenerator[str, None]:
    """Stream chat response."""
    
    # We need async client. Reuse config logic from provider.
    # This is a bit duplicative but safest to ensure async support without refactoring provider.
    provider = llm_provider_for_jobs()
    if not provider:
         yield json.dumps({"error": "LLM not configured"})
         return

    # Construct messages
    sys_msg = "You are a helpful assistant answering questions about a video. Use the provided context."
    
    messages = [{"role": "system", "content": sys_msg}]
    if video_context:
        messages.append({"role": "system", "content": f"Video Context:\n{video_context[:50000]}"})
        
    for msg in history:
        messages.append({"role": msg.role, "content": msg.content})

    # Prepare request
    # Access private fields of provider (naughty but effective for quick-dev)
    # OR better: use public properties if available. They are not.
    # So we use protected members.
    api_base = provider._api_base
    api_key = provider._api_key
    model = provider._model
    timeout = provider._timeout_s
    
    url = api_base
    # Fix URL construction logic duplication
    if url.lower().endswith("/v1"):
        url += "/chat/completions"
    elif url.lower().endswith("/chat/completions"):
        pass
    else:
        url += "/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream", # Standard for OpenAI streaming
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
