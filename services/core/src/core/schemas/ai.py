from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class ChatRequest(BaseModel):
    project_id: str
    message: str
    session_id: str | None = None


class ChatResponse(BaseModel):
    """Chunk of a streaming response."""
    content: str = ""
    start_session_id: str | None = None  # Sent in first chunk if new session
    # We might add citation or references here later


class ChatMessageDTO(BaseModel):
    id: str
    role: Literal["user", "assistant"]
    content: str
    createdAtMs: int
    
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ChatSessionDTO(BaseModel):
    id: str
    projectId: str
    title: str | None
    createdAtMs: int
    updatedAtMs: int

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class QuizGenerateRequest(BaseModel):
    project_id: str
    topic_focus: str | None = None
    output_language: str | None = None


class QuizItemDTO(BaseModel):
    questionHash: str
    question: str
    options: list[str]
    correctAnswer: str
    explanation: str
    userAnswer: str | None = None


class QuizDTO(BaseModel):
    sessionId: str
    items: list[QuizItemDTO]


class QuizAnswerItem(BaseModel):
    question_hash: str
    user_answer: str
    is_correct: bool
    # Content fields for persistence
    question: str | None = None
    options: list[str] | None = None
    correctAnswer: str | None = None
    explanation: str | None = None


class QuizSaveRequest(BaseModel):
    session_id: str
    project_id: str
    score: int
    items: list[QuizAnswerItem]


class QuizSaveResponse(BaseModel):
    success: bool
    session_id: str


class QuizItemUpdateRequest(BaseModel):
    user_answer: str
    is_correct: bool


class QuizItemUpdateResponse(BaseModel):
    success: bool


class QuizSessionDTO(BaseModel):
    id: str
    projectId: str
    score: int | None
    createdAtMs: int
    updatedAtMs: int

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class QuizDetailDTO(BaseModel):
    sessionId: str
    projectId: str
    score: int | None
    items: list[QuizItemDTO]
    createdAtMs: int
    
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
