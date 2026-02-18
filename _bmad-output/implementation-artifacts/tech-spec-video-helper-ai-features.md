---
title: 'Video Helper AI Features'
slug: 'video-helper-ai-features'
created: '2026-02-14'
status: 'ready-for-dev'
stepsCompleted: [1, 2, 3, 4]
tech_stack: ['FastAPI', 'Pydantic', 'Next.js', 'React Query', 'Tailwind CSS', 'PostgreSQL', 'SQLAlchemy']
files_to_modify: 
    - 'apps/web/src/app/(main)/projects/[projectId]/results/page.tsx'
    - 'apps/web/src/components/features/AIChat.tsx'
    - 'apps/web/src/components/features/ExercisesCanvas.tsx'
    - 'services/core/src/core/app/api/ai.py'
    - 'services/core/src/core/schemas/ai.py'
    - 'services/core/src/core/db/models/conversation.py'
    - 'services/core/src/core/db/models/quiz.py'
    - 'services/core/src/core/llm/interaction.py'
    - 'services/core/src/core/app/main.py'
code_patterns: ['FastAPI Router', 'Dependency Injection', 'Repository Pattern', 'React Query Hooks', 'StreamingResponse', 'JSON Mode', 'BackgroundTasks']
test_patterns: ['Unit tests for API endpoints', 'Mocking LLM responses']
---

# Tech-Spec: Video Helper AI Features

**Created:** 2026-02-14

## Overview

### Problem Statement
Enhance the results page with interactive AI features:
1.  **AI Chat**: Multi-turn, context-aware Q&A about the video.
2.  **Interactive Exercises**: "Canvas" style quiz generation with immediate feedback and extensive history.

### Solution

Implement a "Structure & Learning Hub" in the Left Pane.

**1. AI Chat:**
-   **Multi-Session**: Users can start fresh threads.
-   **Context Strategy**: Adaptive Context Window (Full History -> Summarization via Background Task).
-   **Architecture**: Streaming responses using `StreamingResponse`.

**2. Interactive Exercises:**
-   **Architecture**: Backend generates **Structured JSON** batches; Frontend renders **Standard React Components** and handles grading locally.
-   **Persistence**: Save every `QuizSession` (batch) to DB.
-   **Adaptive Flow**: Frontend requests next batch based on performance context.

### Scope

**In Scope:**
-   **Backend**:
    -   DB Models: `ChatSession`, `ChatMessage`, `QuizSession`, `QuizItem`.
    -   API: `POST /ai/chat` (streaming), `POST /ai/quiz/generate` (JSON), `POST /ai/quiz/save`.
    -   Service: `InteractionService` for prompting and background summarization.
-   **Frontend**:
    -   `AIChat`: sidebar/history/input.
    -   `ExercisesCanvas`: quiz renderer/result view/adaptive next.
    -   Layout: Tabs integration in Results page.

## Implementation Plan

### 1. Database & Models
- [ ] Task 1.1: Create Chat DB Models
  - File: `services/core/src/core/db/models/conversation.py`
  - Action: Define `ChatSession` (id, title, project_id) and `ChatMessage` (id, session_id, role, content, created_at).
- [ ] Task 1.2: Create Quiz DB Models
  - File: `services/core/src/core/db/models/quiz.py`
  - Action: Define `QuizSession` (id, project_id, score, topics, created_at) and `QuizItem` (id, session_id, question_hash, user_answer, is_correct).
- [ ] Task 1.3: Register Models and Generate Migration (if using Alembic, else update init)
  - File: `services/core/src/core/db/models/__init__.py`
  - Action: Export new models.

### 2. Backend Schemas & Service
- [ ] Task 2.1: Define Pydantic Schemas
  - File: `services/core/src/core/schemas/ai.py`
  - Action: Create `ChatRequest`, `ChatResponse` (chunk), `QuizGenerateRequest` (context), `QuizSaveRequest`, `QuizDTO`.
- [ ] Task 2.2: Implement Interaction Service (Quiz)
  - File: `services/core/src/core/llm/interaction.py`
  - Action: logic for `generate_quiz(context)` -> constructs prompts, calls LLM with json_mode, returns clean JSON.
- [ ] Task 2.3: Implement Interaction Service (Chat & Summarization)
  - File: `services/core/src/core/llm/interaction.py`
  - Action: logic for `stream_chat(history, video_context)` and `summarize_context(session_id)`.

### 3. Backend API Endpoints
- [ ] Task 3.1: Create AI Router
  - File: `services/core/src/core/app/api/ai.py`
  - Action: Implement endpoints:
    - `POST /chat/completions`: Streaming. Triggers background summarization if needed.
    - `POST /quiz/generate`: Returns JSON batch.
    - `POST /quiz/save`: Persists results.
    - `GET /chat/sessions`: List history.
    - `GET /chat/sessions/{id}/messages`: Load thread.
- [ ] Task 3.2: Register Router
  - File: `services/core/src/core/app/main.py`
  - Action: Include `ai_router` with prefix `/api/v1/ai`.

### 4. Frontend - API & State
- [ ] Task 4.1: API Clients & Hooks
  - File: `apps/web/src/lib/api/ai.ts`, `apps/web/src/hooks/useAI.ts`
  - Action: `useChatMutation` (streaming), `useQuizGenerator`, `useQuizSave`.
- [ ] Task 4.2: Results Page Layout
  - File: `apps/web/src/app/(main)/projects/[projectId]/results/page.tsx`
  - Action: Implement `Tabs` (Mindmap | Chat | Exercises) in Left Pane.

### 5. Frontend - Features
- [ ] Task 5.1: AIChat Component
  - File: `apps/web/src/components/features/AIChat.tsx`
  - Action: Messaging UI, Markdown rendering, auto-scroll, Session list sidebar.
- [ ] Task 5.2: ExercisesCanvas Component (Renderer)
  - File: `apps/web/src/components/features/ExercisesCanvas.tsx`
  - Action: Render MCQ/Cloze from JSON. Handle selection state.
- [ ] Task 5.3: ExercisesCanvas Component (Logic)
  - File: `apps/web/src/components/features/ExercisesCanvas.tsx`
  - Action: Grading logic (client-side), Score calculation, "Next Batch" flow with adaptive context.

## Acceptance Criteria

### Chat
- [ ] **Given** a user asks a question about the video, **When** they send it, **Then** they see a streaming response that references video content.
- [ ] **Given** a long conversation, **When** the user sends the 20th message, **Then** the response is still relevant (context was summarized invisibly).
- [ ] **Given** a user leaves and returns, **When** they open "Chat", **Then** they see their previous conversation threads.

### Exercises
- [ ] **Given** a finished video analysis, **When** user clicks "Exercises", **Then** a batch of relevant questions is generated.
- [ ] **Given** a displayed MCQ, **When** user selects the correct answer, **Then** they immediately see "Correct" and an explanation.
- [ ] **Given** a user performs poorly on "Topic A", **When** they request "Next Batch", **Then** the new questions focus on "Topic A/Consolidation".
- [ ] **Given** a completed quiz, **When** user clicks "Save", **Then** the result (score) is visible in their history.

## Testing Strategy
-   **Backend**: `pytest` for `interaction.py` (mocking LLM) and API endpoints.
-   **Frontend**: Manual testing of Chat streaming and Quiz grading flows.
