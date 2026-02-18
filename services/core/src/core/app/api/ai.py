from __future__ import annotations

import json
import logging
import uuid

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session

from core.app.api.jobs import _now_ms
from core.contracts.error_codes import ErrorCode
from core.contracts.error_envelope import build_error_envelope
from core.db.models.conversation import ChatMessage, ChatSession
from core.db.models.quiz import QuizItem, QuizSession
from core.db.repositories.projects import get_project_by_id
from core.db.session import get_db_session
from core.llm.interaction import generate_quiz, stream_chat
from core.schemas.ai import (
    ChatRequest,
    ChatMessageDTO,
    ChatSessionDTO,
    QuizDTO,
    QuizGenerateRequest,
    QuizItemDTO,
    QuizDetailDTO,
    QuizSessionDTO,
    QuizSaveRequest,
    QuizSaveResponse
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ai"])

@router.post("/chat/completions")
async def chat_completions(
    req: ChatRequest,
    request: Request,
    session: Session = Depends(get_db_session)
):
    """Stream chat completions."""
    
    # Validate project
    project = get_project_by_id(session, req.project_id)
    if not project:
         return JSONResponse(
            status_code=404,
            content=build_error_envelope(
                code=ErrorCode.PROJECT_NOT_FOUND,
                message="Project not found",
                details={"projectId": req.project_id},
            ),
        )

    # Resolve or create session
    chat_session_id = req.session_id
    if not chat_session_id:
        chat_session_id = str(uuid.uuid4())
        new_session = ChatSession(
            id=chat_session_id,
            project_id=req.project_id,
            title=req.message[:50] if req.message else "New Chat",
            created_at_ms=_now_ms(),
            updated_at_ms=_now_ms()
        )
        session.add(new_session)
        session.commit()
    else:
        # verify exists
        existing = session.query(ChatSession).filter(ChatSession.id == chat_session_id).first()
        if not existing:
             return JSONResponse(
                status_code=404,
                content=build_error_envelope(
                    code=ErrorCode.RESOURCE_NOT_FOUND,
                    message="Chat session not found",
                    details={"sessionId": chat_session_id},
                ),
            )
        existing.updated_at_ms = _now_ms()
        session.add(existing)
        session.commit()

    # Save User Message
    user_msg_id = str(uuid.uuid4())
    user_msg = ChatMessage(
        id=user_msg_id,
        session_id=chat_session_id,
        role="user",
        content=req.message,
        created_at_ms=_now_ms()
    )
    session.add(user_msg)
    session.commit()

    # Load History (simplistic: last 20 messages)
    history_objs = (
        session.query(ChatMessage)
        .filter(ChatMessage.session_id == chat_session_id)
        .order_by(ChatMessage.created_at_ms.asc())
        .limit(50) 
        .all()
    )
    
    history_dtos = [
        ChatMessageDTO(
            id=m.id,
            role=m.role, # type: ignore
            content=m.content,
            createdAtMs=m.created_at_ms
        ) for m in history_objs
    ]

    # Get video context? (Optional: passed in req or fetched from project result)
    # For now, we'll fetch from latest result if available
    video_context = ""
    # TODO: Fetch efficient context from project.latest_result_id -> mindmap or summary
    
    async def _generator():
        assistant_parts: list[str] = []
        # First chunk could contain session_id if new
        if not req.session_id:
             yield f"data: {{\"start_session_id\": \"{chat_session_id}\"}}\n\n"

        try:
            async for chunk in stream_chat(history_dtos, video_context, req.project_id):
                assistant_parts.append(chunk)
                yield f"data: {json.dumps({'content': chunk}, ensure_ascii=False)}\n\n"
        finally:
            # Persist assistant message (best-effort). This fixes: UI refresh shows no assistant
            # message, and DB only contains the user message.
            assistant_content = "".join(assistant_parts).strip()
            if assistant_content:
                try:
                    assistant_msg = ChatMessage(
                        id=str(uuid.uuid4()),
                        session_id=chat_session_id,
                        role="assistant",
                        content=assistant_content,
                        created_at_ms=_now_ms(),
                    )
                    session.add(assistant_msg)

                    chat_session = session.query(ChatSession).filter(ChatSession.id == chat_session_id).first()
                    if chat_session is not None:
                        chat_session.updated_at_ms = _now_ms()
                        session.add(chat_session)

                    session.commit()
                except Exception:
                    logger.exception("Failed to persist assistant chat message")

            yield "data: [DONE]\n\n"
        
    return StreamingResponse(
        _generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/quiz/generate", response_model=QuizDTO)
def generate_quiz_endpoint(
    req: QuizGenerateRequest,
    request: Request,
    session: Session = Depends(get_db_session)
):
    project = get_project_by_id(session, req.project_id)
    if not project:
         return JSONResponse(
            status_code=404,
            content=build_error_envelope(
                code=ErrorCode.PROJECT_NOT_FOUND,
                message="Project not found",
            ),
        )
    
    # Get context from result
    # Simplified: just use a placeholder or wait for "content_blocks" implementation
    context = f"Video Title: {project.title or 'Unknown'}"
    
    try:
        quiz = generate_quiz(context, req.project_id, req.topic_focus)
        return quiz
    except Exception as e:
         return JSONResponse(
            status_code=500,
            content=build_error_envelope(
                code=ErrorCode.JOB_STAGE_FAILED,
                message=f"Quiz generation failed: {str(e)}",
            ),
        )

@router.post("/quiz/save", response_model=QuizSaveResponse)
def save_quiz(
    req: QuizSaveRequest,
    request: Request,
    session: Session = Depends(get_db_session)
):
    try:
        # Create session record
        quiz_session = QuizSession(
            id=req.session_id,
            project_id=req.project_id,
            score=req.score,
            topics={}, # TODO: extract topics
            created_at_ms=_now_ms(),
            updated_at_ms=_now_ms()
        )
        session.add(quiz_session)
        
        # Save items
        for item in req.items:
            q_item = QuizItem(
                id=str(uuid.uuid4()),
                session_id=req.session_id,
                question_hash=item.question_hash,
                user_answer=item.user_answer,
                is_correct=item.is_correct,
                content={
                    "question": item.question or "",
                    "options": item.options or [],
                    "correctAnswer": item.correctAnswer or "",
                    "explanation": item.explanation or "",
                },
                created_at_ms=_now_ms()
            )
            session.add(q_item)
            
        session.commit()
        return QuizSaveResponse(success=True, session_id=req.session_id)
    except Exception as e:
        logger.error(f"Failed to save quiz: {e}")
        return JSONResponse(
            status_code=500,
            content=build_error_envelope(
                code=ErrorCode.INTERNAL_ERROR,
                message="Failed to save quiz",
            ),
        )


@router.get("/quiz/sessions", response_model=list[QuizSessionDTO])
def list_quiz_sessions(
    projectId: str = Query(..., alias="projectId"),
    session: Session = Depends(get_db_session)
):
    sessions = (
        session.query(QuizSession)
        .filter(QuizSession.project_id == projectId)
        .order_by(QuizSession.updated_at_ms.desc())
        .limit(50)
        .all()
    )
    return [
        QuizSessionDTO(
            id=s.id,
            projectId=s.project_id,
            score=s.score,
            createdAtMs=s.created_at_ms,
            updatedAtMs=s.updated_at_ms
        ) for s in sessions
    ]


@router.get("/quiz/sessions/{sessionId}", response_model=QuizDetailDTO)
def get_quiz_session_detail(
    sessionId: str,
    session: Session = Depends(get_db_session)
):
    quiz_session = session.query(QuizSession).filter(QuizSession.id == sessionId).first()
    if not quiz_session:
        return JSONResponse(
            status_code=404,
            content=build_error_envelope(
                code=ErrorCode.RESOURCE_NOT_FOUND,
                message="Quiz session not found",
            ),
        )

    items = (
        session.query(QuizItem)
        .filter(QuizItem.session_id == sessionId)
        .order_by(QuizItem.created_at_ms.asc())
        .all()
    )
    
    item_dtos = []
    for item in items:
        # Reconstruct DTO from stored content
        content = item.content or {} 
        # Fallback if content is missing (old data)
        item_dtos.append(QuizItemDTO(
            questionHash=item.question_hash,
            question=content.get("question", "Unknown Question"),
            options=content.get("options", []),
            correctAnswer=content.get("correctAnswer", ""),
            explanation=content.get("explanation", ""),
            userAnswer=item.user_answer
        ))

    return QuizDetailDTO(
        sessionId=quiz_session.id,
        projectId=quiz_session.project_id,
        score=quiz_session.score,
        items=item_dtos,
        createdAtMs=quiz_session.created_at_ms
    )


@router.get("/chat/sessions", response_model=list[ChatSessionDTO])
def list_chat_sessions(
    projectId: str = Query(..., alias="projectId"),
    session: Session = Depends(get_db_session)
):
    sessions = (
        session.query(ChatSession)
        .filter(ChatSession.project_id == projectId)
        .order_by(ChatSession.updated_at_ms.desc())
        .limit(50)
        .all()
    )
    return [
        ChatSessionDTO(
            id=s.id,
            projectId=s.project_id,
            title=s.title,
            createdAtMs=s.created_at_ms,
            updatedAtMs=s.updated_at_ms
        ) for s in sessions
    ]

@router.get("/chat/sessions/{sessionId}/messages", response_model=list[ChatMessageDTO])
def list_session_messages(
    sessionId: str,
    session: Session = Depends(get_db_session)
):
    msgs = (
        session.query(ChatMessage)
        .filter(ChatMessage.session_id == sessionId)
        .order_by(ChatMessage.created_at_ms.asc())
        .all()
    )
    return [
        ChatMessageDTO(
            id=m.id,
            role=m.role, # type: ignore
            content=m.content,
            createdAtMs=m.created_at_ms
        ) for m in msgs
    ]
