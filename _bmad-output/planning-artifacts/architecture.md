---
stepsCompleted:
  - 1
  - 2
  - 3
  - 4
  - 5
  - 6
  - 7
  - 8
inputDocuments:
  - _bmad-output/planning-artifacts/prd.md
  - _bmad-output/planning-artifacts/ux-design-specification.md
  - develop_design.md
  - api.md
workflowType: 'architecture'
project_name: 'video-helper'
user_name: 'LDJ'
date: '2026-01-28'
lastStep: 8
status: 'complete'
completedAt: '2026-01-28'
---

# Architecture Decision Document

_This document builds collaboratively through step-by-step discovery. Sections are appended as we work through each architectural decision together._

## Project Context Analysis

### Requirements Overview

**Functional Requirements (Architectural Implications):**
- Project/Library：多项目持久化与列表/详情/删除，且维护 `latest_result` 指针（需要稳定的版本/引用模型）。
- Ingest：外链（YouTube/B站）+ Web 端上传；服务端落盘与元信息抽取（要求统一的“导入资源真相”，避免客户端路径成为真相）。
- Jobs：长任务状态机（queued/running/succeeded/failed/canceled），SSE 推送（含心跳）+ 轮询降级；失败需结构化错误码与可行动建议；可选取消与重试（需要幂等/可重入的任务边界）。
- Pipeline：章节切片为唯一准则；后续两子流程并发产物并最终汇总 Result（需要明确流水线阶段、产物契约与并发协调）。
- Results：Result 必须可独立渲染与恢复编辑态（要求 Result 中包含足够信息，前端不依赖内存态）。
- Editing：笔记（Tiptap JSON）与思维导图（nodes/edges）可编辑保存；关键帧/图片可绑定章节/时间点（需要清晰的写入模型：覆盖式更新 vs 生成新 Result 版本）。
- Assets：关键帧/截图可访问且路径安全（需要受限资源服务与统一 DATA_DIR 相对路径策略）。
- Search（MVP 轻量）：标题/摘要/派生文本检索（未来可扩展 FTS5/向量）。

**Non-Functional Requirements (Shape Architecture):**
- Reliability/Recoverability：刷新/重启可恢复 Job 状态与 Result 渲染；SSE 中断自动降级轮询。
- Performance：交互响应主观 ≤200ms；10–30 分钟视频端到端分析目标 ≤10 分钟（需要可配置模型/并发/缓存策略）。
- Security/Privacy：不暴露绝对路径；资源访问防目录穿越；API Key 不以明文落盘，日志/错误详情不得泄露敏感信息。
- Deployment/Portability：源码与 Docker 均可运行；CORS/API BaseURL/DATA_DIR/模型配置可配置；默认支持 2 个 Job 并发。

**Scale & Complexity:**
- Primary domain: Full-stack web app + long-running media/AI pipeline
- Complexity level: Medium
- Estimated architectural components: 9–11

### Technical Constraints & Dependencies

- 外部依赖：FFmpeg、yt-dlp、（模型/转写/切片提供方或本地模型环境）
- 存储：SQLite（含未来 FTS5 / sqlite-vec 扩展可能）+ 本地文件系统（Assets/缓存/上传文件）
- 端形态：Web/Docker 为首要验收；桌面端 Sidecar 为后续扩展方向
- 契约约束：Chapters 为唯一准则；导图/重点/关键帧必须可追溯到 `chapter_id`/`time_ms`

### Cross-Cutting Concerns Identified

- 任务编排与可观察性：stage/progress/log、错误码体系、可行动错误提示、SSE 心跳与降级策略
- 数据一致性：Result/Chapters/Assets/Keyframes 关联完整性；更新策略（编辑保存如何影响 Result 版本与 latest_result）
- 路径与资源安全：DATA_DIR 相对路径、资源读取白名单、防目录穿越
- 配置与密钥：provider/model/base_url/API key 的管理与持久化边界（Web vs 桌面）
- 前端性能：长列表虚拟化、编辑器与导图的状态管理与保存反馈

## Starter Template Evaluation

### Primary Technology Domain

Full-stack web application:

- Frontend: Next.js (App Router) + Tailwind + shadcn/ui for rich SPA-like UX and complex editor interactions
- Backend: FastAPI (Python) for long-running Jobs, SSE progress, media/AI pipeline orchestration

### Starter Options Considered

1) Next.js official starter via `create-next-app`

- Pros: 官方维护、App Router 默认、与 Tailwind/ESLint/TS 兼容性最佳、后续集成 TipTap/React Flow/shadcn 成本低
- Cons: 不会替你解决后端与 monorepo，需要我们自行落地服务边界与脚手架

2) shadcn/ui initialization on top of Next.js (`shadcn@latest init`)

- Pros: 快速得到可用的组件体系与风格基线（匹配 UX spec），便于后续做结果页复杂布局与卡片体系
- Cons: 需要对组件引入与主题 token 做规范（但这是我们本来就要做的架构决策）

### Selected Starter: Next.js `create-next-app` + shadcn/ui init (Recommended)

**Rationale for Selection:**

- 与 PRD/UX/开发设计中“Next.js + Tailwind + shadcn”的既定方向一致
- 官方 starter 最稳，减少框架层不确定性，把复杂度留给 Job/Pipeline/编辑器这些真正的核心问题
- 允许未来平滑扩展到 monorepo/桌面端（Tauri sidecar）而不锁死

### Initialization Commands

**Frontend (Next.js App Router + TS + Tailwind + ESLint):**

```bash
npx create-next-app@latest apps/web --ts --tailwind --eslint --app --src-dir --import-alias "@/*" --use-pnpm
```

**UI System (shadcn/ui):**

```bash
cd apps/web
pnpm dlx shadcn@latest init
pnpm dlx shadcn@latest add button
```

**Backend (FastAPI project skeleton; dependency manager: uv):**

```bash
uv init services/core
cd services/core
uv add "fastapi[standard]"
```

### Architectural Decisions Provided by Starter

**Language & Runtime:**

- Frontend: TypeScript-first Next.js project
- Backend: Python project managed via uv (lockfile-ready)

**Styling Solution:**

- Tailwind CSS baseline (aligned with UX tokens and shadcn/ui)

**Build Tooling & DX:**

- Next.js App Router project structure
- Linting via ESLint (can be revisited if switching to Biome)

**Code Organization:**

- `apps/web` for frontend
- `services/core` for backend API and pipeline orchestration

**Note:** Project initialization using these commands should be the first implementation story.

## Core Architectural Decisions

### Decision Priority Analysis

Top-priority decisions (biggest downstream impact) locked in so far:

- Single-node persistence: SQLite as the primary datastore for metadata/state.
- DB access strategy: SQLAlchemy ORM as the primary access layer (with explicit SQL allowed where needed).
- Schema evolution: Alembic migrations (including SQLite-safe patterns).
- Asset storage: local filesystem under `DATA_DIR`, with DB storing only relative paths.

These decisions optimize for MVP speed + local-first reliability, while keeping a clear migration path to more scalable storage if needed.

### Data Architecture

#### 1) Primary datastore

**Decision:** SQLite is the primary database for the application.

**Rationale:** Local-first, simple deployment (Docker/源码运行), strong enough for MVP scale, and aligns with “recoverability after refresh/restart”.

**Implementation notes:**

- Enable WAL mode and set a reasonable busy timeout to support limited concurrent writes.
- Keep a clear boundary between DB metadata and filesystem assets.

#### 2) DB access approach

**Decision:** Use SQLAlchemy ORM as the main persistence layer.

**Validated versions (as of 2026-01-28):** SQLAlchemy 2.0.46.

**Rationale:** Maintains readability and schema discipline as tables grow (projects/jobs/results/chapters/assets/highlights), while still allowing selective raw SQL for performance hotspots.

**Implementation notes:**

- Use a per-request session pattern in FastAPI.
- Centralize transaction boundaries: API request handlers and pipeline job stage commits.

#### 3) Migration strategy

**Decision:** Use Alembic for migrations.

**Validated versions (as of 2026-01-28):** alembic 1.18.1.

**Rationale:** Keeps schema evolution explicit and repeatable across dev/Docker environments.

**Implementation notes:**

- Prefer additive migrations.
- For SQLite “ALTER limitations”, use Alembic’s batch operations pattern when needed.

**Migration workflow (one-liner):** Make schema changes by updating SQLAlchemy models first, then generate and review an Alembic migration (`alembic revision --autogenerate -m "..."`), and apply via `alembic upgrade head` — never hand-edit the SQLite schema.

#### 4) Schema/modeling stance

**Decision:** Treat the DB schema as the source of truth for metadata/state; treat filesystem as the source of truth for binary assets.

**Rationale:** Avoids leaking absolute paths into the DB, enables safer asset serving, and simplifies backup/restore semantics.

#### 5) Asset storage & path safety

**Decision:** Store assets under `DATA_DIR` only; persist only relative paths in the DB.

**Rationale:** Meets the security requirement “do not expose absolute paths” and prevents directory traversal when serving assets.

**Implementation notes:**

- Define a canonical layout (example):
  - `DATA_DIR/db/app.db`
  - `DATA_DIR/projects/{project_id}/uploads/`
  - `DATA_DIR/projects/{project_id}/artifacts/` (keyframes, screenshots, derived JSON, etc.)
- All file access goes through a single “safe join + whitelist” utility.

#### 6) Caching strategy

**Decision:** Use lightweight caching (in-memory within a job + optional on-disk cache under `DATA_DIR/cache`) instead of a dedicated cache service.

**Rationale:** Matches MVP deployment constraints and reduces moving parts.

**Implementation notes:**

- Cache keys must include model/provider configuration to avoid stale cross-run artifacts.
- Cache eviction can start as size-based or time-based.

#### Related foundational library versions

- Pydantic 2.12.5 (as of 2026-01-28).

### Security & Auth

#### 1) Access mode (MVP)

**Decision:** Default to local / intranet usage with no mandatory login.

**Rationale:** Optimize for “it just works” in the primary MVP scenario.

**Implementation notes:**

- The backend should support an auth switch so that remote deployments can be protected without code changes.

#### 2) Frontend/backend auth mechanism

**Decision:** Dual-mode auth.

- Local mode: auth disabled (or only enforced for non-localhost requests).
- Remote mode: require `Authorization: Bearer <token>` on API requests.

**Rationale:** Keeps MVP friction low while preventing accidental exposure when the service is bound to `0.0.0.0`, port-forwarded, or reverse-proxied.

**Implementation notes:**

- Single shared token configured via environment variable (e.g. `AUTH_BEARER_TOKEN`) in Docker / server environments.
- Frontend injects `Authorization` header when token is present.
- Backend uses a single dependency/middleware to enforce auth consistently across endpoints (including asset streaming routes).

#### 3) CORS policy

**Decision:** Same-origin by default; during development allow `http://localhost:*` via an explicit allowlist.

**Rationale:** Minimizes cross-origin risk while keeping local DX smooth.

#### 4) Asset access control

**Decision:** All assets (video / keyframes / screenshots) are served through backend-controlled routes.

**Rationale:** Prevents absolute path exposure and blocks directory traversal by construction.

**Implementation notes:**

- Asset endpoints must reuse the same safe-path validation used for filesystem reads.
- When remote auth is enabled, asset routes must also require `Authorization: Bearer ...`.

#### 5) Secrets management

**Decision:** Environment variables first; allow future optional encrypted local storage.

**Rationale:** Keeps deployment simple today and matches a potential future desktop/sidecar scenario.

#### 6) Logging and error disclosure

**Decision:** Use structured error codes; do not return internal stack traces by default; allow verbose details only in debug mode.

**Rationale:** Meets privacy/security requirements and keeps user-facing errors actionable.

### API Architecture

#### 1) API versioning and routing prefix

**Decision:** Use explicit versioned API prefix: `/api/v1/...`.

**Rationale:** Enables forward-compatible evolution without breaking existing clients.

#### 2) Project creation vs Job creation

**Decision:** One-step flow: `POST /api/v1/jobs` auto-creates a Project and returns both `project_id` and `job_id`.

**Rationale:** Minimizes frontend orchestration and aligns with the “Job as long-running unit of work” model.

**Implementation notes:**

- The job creation request includes the video source (URL or uploaded asset reference).
- Response should include: `job_id`, `project_id`, initial `status`, and any normalization of source metadata.

#### 3) Source input boundary (Web vs Desktop)

**Decision:** Environment split.

- Web/Docker: do not accept `source_file_path`.
- Desktop sidecar: may accept `source_file_path`.

**Rationale:** Prevents external absolute paths from becoming system truth in web deployments; stays compatible with future desktop mode.

#### 4) Pagination strategy

**Decision:** Use cursor pagination consistently for list/search endpoints.

**Rationale:** Stable ordering and better performance characteristics as datasets grow.

**Implementation notes:**

- Pattern: `?limit=...&cursor=...`
- Cursor should encode a stable sort key (e.g. `updated_at/created_at` + `id`).

#### 5) Error response envelope

**Decision:** Standardize error envelope across all endpoints:

`{ "error": { "code": "...", "message": "...", "details": { ... }?, "request_id": "..."? } }`

**Rationale:** Keeps failures actionable for users and debuggable for developers; aligns with Jobs needing structured errors.

**Implementation notes:**

- Define a fixed mapping from business error codes to HTTP status codes.
- Do not leak stack traces or sensitive config in responses.

#### 6) Jobs: SSE event contract

**Decision:** SSE is the default progress channel, with a fixed event taxonomy:

- `heartbeat`
- `progress`
- `log`
- `state`

Support `Last-Event-ID` for best-effort reconnect/continuation.

**Rationale:** Provides responsive UX for long-running pipelines with graceful degradation.

**Implementation notes:**

- Polling fallback remains supported via job status endpoint.
- Heartbeats should be sent periodically to prevent false “stalled” detection.

#### 7) Assets: route shape

**Decision:** Bind asset routes to project scope:

- `GET /api/v1/projects/{project_id}/assets/{asset_id}` (metadata)
- `GET /api/v1/projects/{project_id}/assets/{asset_id}/content` (stream)

**Rationale:** Matches the security model (project scoping + relative path validation) and supports optional remote auth enforcement.

#### 8) Editing write semantics (Result updates)

**Decision:** Editing APIs overwrite the existing `result_id` (no new Result version created on each save).

**Rationale:** Keeps MVP implementation simple.

**Implementation notes:**

- If future versioning is required, introduce a separate “result revisions” mechanism or switch to version-per-save.

#### 9) Model/provider settings boundary

**Decision:** API exposes read and non-sensitive settings only; API keys are not set via HTTP.

**Rationale:** Aligns with “env vars first + optional encrypted local storage” and reduces risk of secrets leakage.

### Frontend Architecture

#### 1) Client data fetching and caching

**Decision:** Use TanStack Query (`@tanstack/react-query`) as the standard data layer for projects/jobs/results/search.

**Rationale:** Provides robust caching, invalidation, retries, polling, and request lifecycle controls needed for a Job/SSE-heavy app.

#### 2) Global UI state management

**Decision:** Use Zustand for UI state (player state, panel visibility/sizes, selected chapter, right-panel tabs).

**Rationale:** Lightweight and well-suited for cross-component UI state without introducing heavy boilerplate.

#### 3) Job progress consumption (SSE)

**Decision:** SSE updates TanStack Query caches; on disconnect, automatically fall back to polling.

**Rationale:** Keeps the UI responsive while aligning with the backend’s SSE-first + polling fallback contract.

**Implementation notes:**

- SSE events update the canonical cached job state.
- On page refresh/reconnect, the UI can reconstruct progress from the job status endpoint.

#### 4) Editing save strategy (Tiptap + mindmap)

**Decision:** Local-first editing with debounced autosave (e.g. 800–1500ms) and flush on navigation/unload.

**Rationale:** Prevents request storms and improves perceived reliability (edits are unlikely to be lost).

#### 5) Editing vs server state boundary

**Decision:** Cache editing state client-side (in-memory, optional localStorage) and persist by overwriting the server-side Result.

**Rationale:** Matches the chosen API semantics (overwrite existing `result_id`) and supports recoverability across refreshes.

**Implementation notes:**

- Server should return `updated_at` (or ETag equivalent) to help clients reconcile.

#### 6) Three-column layout + floating player

**Decision:** Implement with CSS Grid + resizable panels.

- Left: project/chapter navigation
- Center: note + mindmap workspace
- Right: keyframes/highlights
- Player: floating overlay anchored in the center column

**Rationale:** Provides the most stable basis for complex desktop-first layout while remaining adaptable to responsive behavior.

#### 7) Long-list performance

**Decision:** Use virtualization (`@tanstack/react-virtual`) plus cursor pagination.

**Rationale:** Ensures smooth scrolling and predictable performance as projects/chapters/highlights grow.

#### 8) API client + auth header injection

**Decision:** Use a single API client wrapper that:

- injects `Authorization: Bearer ...` when configured
- centralizes error-envelope parsing and request-id propagation

**Rationale:** Prevents auth/header drift and keeps error handling consistent across the app.

### Deployment & Operations

#### 1) Deployment target

**Decision:** Docker Compose is the primary deployment path; source-run is supported for local development.

**Rationale:** Matches MVP distribution needs while keeping developer ergonomics high.

#### 2) Process topology

**Decision:** Two processes/services: Next.js frontend + FastAPI backend.

**Rationale:** Keeps responsibilities clean and avoids coupling frontend build/runtime to backend concerns.

#### 3) Data directory contract

**Decision:** `DATA_DIR` controls all persistent data locations; default may be `./data`.

**Rationale:** Enables safe local-first persistence and predictable Docker volume mounting.

**Implementation notes:**

- All persisted filesystem assets must be under `DATA_DIR`.
- All DB-stored paths must be relative to `DATA_DIR`.

#### 4) Database file location

**Decision:** SQLite DB path is fixed to `DATA_DIR/db/app.db`.

**Rationale:** Keeps ops simple and consistent across environments.

#### 5) Auth switch (remote protection)

**Decision:** Environment-driven auth switch:

- `AUTH_MODE=off|bearer` (default: `off`)
- `AUTH_BEARER_TOKEN` (required when `AUTH_MODE=bearer`)

**Rationale:** Protects remote deployments without adding user accounts.

#### 6) CORS configuration

**Decision:** CORS allowlist via env var `CORS_ALLOWED_ORIGINS` (comma-separated).

**Rationale:** Prevents accidental cross-origin exposure while preserving local DX.

**Implementation notes:**

- Default behavior: same-origin.
- Development: allow `http://localhost:*`.

#### 7) Job concurrency and resource limits

**Decision:** Application-level job queue with configurable concurrency:

- `MAX_CONCURRENT_JOBS=2` (default)

**Rationale:** Meets the “default 2 concurrent jobs” requirement and avoids conflating HTTP worker count with pipeline concurrency.

#### 8) External tool execution model

**Decision:** Run FFmpeg / yt-dlp / other heavy steps via subprocess with controlled args, timeouts, and log capture.

**Rationale:** Improves robustness and makes cancellation/logging feasible.

#### 9) Observability baseline

**Decision:** Structured JSON logs with `request_id`; job logs are queryable by `job_id`.

**Rationale:** Supports debugging long-running pipelines and correlating user actions with job execution.

#### 10) Health checks

**Decision:** Provide `/api/v1/health` that reports service status and validates required dependencies (ffmpeg/yt-dlp; optional provider connectivity).

**Rationale:** Enables the frontend and deployment tooling to detect readiness and degraded states.

### Pipeline & Jobs Architecture

#### 1) Job lifecycle and persistence

**Decision:** Jobs are persisted in SQLite and remain recoverable across refresh/restart.

**Rationale:** Directly supports reliability/recoverability requirements.

**Implementation notes:**

- Job states: `queued | running | succeeded | failed | canceled`.
- Persist timestamps (`created_at`, `started_at`, `finished_at`, `canceled_at`) and the latest `stage` + `progress`.

#### 2) Pipeline stage model

**Decision:** Represent pipeline execution as discrete stages with stable names used by UI and SSE.

**Rationale:** Enables consistent progress reporting and actionable error messages.

**Recommended stages (MVP):**

- `ingest` (download/import)
- `transcribe`
- `segment` (chapters as source of truth)
- `analyze` (chapter-wise analysis)
- `assemble_result`
- `extract_keyframes` (if not earlier)

#### 3) Worker model

**Decision:** In-process worker loop in the backend consumes queued jobs with a concurrency cap (`MAX_CONCURRENT_JOBS`).

**Rationale:** Keeps MVP simple while meeting concurrency requirements.

**Implementation notes:**

- Use a DB-backed claim mechanism to prevent double-processing.
- Ensure a single job runs at most once at a time even if multiple backend instances are started (best-effort; single-node is the target).

#### 4) Idempotency

**Decision:** Support optional idempotency for job creation using `idempotency_key` scoped to `(project_id, job_type)`.

**Rationale:** Prevents duplicate long-running work from repeated user actions or retries.

#### 5) Cancellation

**Decision:** Cancellation is cooperative: marking a job as canceled should stop scheduling further stages and attempt to terminate any active subprocesses.

**Rationale:** Provides user control without requiring heavyweight orchestration.

#### 6) Progress + logs transport

**Decision:** SSE is the primary channel for stage/progress/log updates, with polling fallback.

**Rationale:** Aligns with the API Architecture decision and UX expectations.

**Implementation notes:**

- Emit periodic `heartbeat` events.
- Use monotonically increasing event IDs for best-effort `Last-Event-ID` support.
- Persist job logs as files on disk (MVP: full logs to file) so UI can recover after refresh and operators can inspect failures.

#### 6.1) Job log persistence (MVP)

**Decision:** Persist full job logs to files under `DATA_DIR` (append-only).

**Rationale:** Keeps DB lean, makes post-mortem/debugging straightforward, and supports “refresh/restart可恢复”的体验（SSE 断开后仍可通过 HTTP 拉取日志尾部）。

**Implementation notes:**

- Recommended layout: `DATA_DIR/projects/{project_id}/jobs/{job_id}/logs.jsonl` (structured) and/or `logs.txt` (human-readable).
- Provide an HTTP endpoint to fetch a tail with cursor pagination (opaque cursor could be byte offset).

#### 7) Result materialization

**Decision:** On success, a job produces/updates the project’s latest Result and updates `projects.latest_result_id`.

**Rationale:** Ensures results are independently renderable and recoverable.

#### 8) Filesystem layout for pipeline artifacts

**Decision:** All derived artifacts (downloads, transcripts, keyframes) are stored under `DATA_DIR/projects/{project_id}/...` and referenced by relative paths.

**Rationale:** Keeps storage local-first, portable, and consistent with asset-serving security.

### Search & Indexing

#### 1) MVP search scope

**Decision:** Implement MVP search over project title + result summary/plaintext fields; expand later to transcript/RAG.

**Rationale:** Delivers immediate utility with low complexity.

#### 2) Implementation approach

**Decision:** Start with SQLite-backed search.

- Phase 1: simple LIKE queries over small derived text fields.
- Phase 2 (when needed): SQLite FTS5 virtual table for notes/searchable text.

**Rationale:** Keeps dependencies minimal while offering a clear upgrade path.

### Model Provider Integration

#### 1) Configuration boundaries

**Decision:** Non-sensitive provider settings may be stored in SQLite; secrets (API keys) are not set via HTTP.

**Rationale:** Matches the selected security posture and prevents accidental secret leakage.

#### 2) Runtime configuration model

**Decision:** Provider selection and options are represented as a typed config object (validated with Pydantic) and injected into pipeline stages.

**Rationale:** Ensures reproducibility and makes cache keys safe (include provider/model/options).

#### 3) Health validation

**Decision:** `/api/v1/health` includes optional provider connectivity checks when configured.

**Rationale:** Helps users diagnose missing/misconfigured dependencies early.

## Implementation Patterns & Consistency Rules

### Pattern Categories Defined

**Critical conflict points identified:** 12 areas where different AI agents could accidentally make incompatible choices (naming, folder placement, API shapes, SSE payloads, timestamps/IDs, error handling, asset paths, and state ownership between UI/cache/editor).

### Naming Patterns

**Database naming conventions:**

- Tables: `snake_case` + plural (e.g. `projects`, `jobs`, `results`, `chapter_keyframes`).
- Columns: `snake_case` (e.g. `created_at`, `updated_at`, `time_ms`, `latest_result_id`).
- Primary keys: `id` (TEXT UUID).
- Foreign keys: `{entity}_id` (e.g. `project_id`, `job_id`, `result_id`, `chapter_id`).
- Timestamps: `*_at` for ISO datetime columns (if used) OR `*_ms` for epoch milliseconds (if used); do not mix within the same logical field.
- Indices: `idx_{table}_{col1}_{col2}`; unique indices `ux_{table}_{col}`.

**API naming conventions:**

- Prefix: `/api/v1` only.
- Paths: lowercase + plural nouns for collections.
- Route params: `{project_id}` style in docs; actual URLs follow `/projects/{project_id}/...`.
- Query params: `camelCase` (align with TS clients).
- Cursor pagination response shape: `{ items: T[], nextCursor: string | null }`.

**JSON field naming conventions:**

- API request/response JSON uses `camelCase`.
- Backend uses Pydantic field aliases to map internal `snake_case` → external `camelCase`.
- IDs: `projectId`, `jobId`, `resultId`, `chapterId`, `assetId`.
- Time: `timeMs` and `createdAtMs/updatedAtMs` (epoch ms, number).

**Code naming conventions:**

- TypeScript: `camelCase` variables/functions, `PascalCase` React components/types.
- Files: `kebab-case.ts/tsx` for components and routes helpers; `camelCase.ts` allowed for libs where consistent.
- Python: `snake_case` modules/functions/vars; `PascalCase` classes.

### Structure Patterns

**Project organization (monorepo):**

- Frontend lives only in `apps/web`.
- Backend lives only in `services/core`.
- Shared, cross-cutting specs live in one place:
  - API contracts, event payload docs: `api.md` + `architecture.md`.
  - Shared TS types generated/maintained under `apps/web/src/lib/api/types` (single source for UI).

**Backend layering:**

- FastAPI “routes layer” is thin: parse/validate request, call service layer, return DTO.
- Business logic lives in `services/` (e.g. job creation, result updates).
- Persistence in `db/` (SQLAlchemy models + session + repos).
- Pipeline execution in `pipeline/` with explicit stage boundaries.
- Filesystem and asset access in `storage/` with a single safe-path utility.

**Frontend layering:**

- Server data: React Query.
- UI-only state: Zustand.
- Editors (Tiptap/mindmap) keep local state; persistence via debounced API writes.
- All HTTP goes through one `apiClient` wrapper.

### Format Patterns

**API success response formats:**

- “Get one” endpoints return a single object DTO.
- List endpoints return `{ items, nextCursor }`.
- “Mutation” endpoints return the updated object DTO (preferred) or `{ ok: true }` if no entity.

**API error response envelope (mandatory):**

```json
{
  "error": {
    "code": "SOME_CODE",
    "message": "Human readable message",
    "details": {},
    "request_id": "..."
  }
}
```

Rules:

- Never return raw stack traces unless explicit debug mode.
- Always include a stable `code` suitable for UI branching.

**Timestamp & ID formats:**

- IDs are UUID strings.
- Times in API are epoch milliseconds (number).
- Internally, Python may use timezone-aware `datetime`, but serialization is always epoch ms.

### Communication Patterns

**SSE event taxonomy (mandatory):**

- `heartbeat`
- `progress`
- `log`
- `state`

**SSE payload standard fields (camelCase):**

- `eventId` (monotonic, string)
- `jobId`, `projectId`
- `stage` (stable stage name)
- `progress` (0..1)
- `message` (optional)
- `tsMs` (epoch ms)

**State update rules (UI):**

- SSE updates the React Query cache for the job; derived UI listens from cache.
- On SSE disconnect: switch to polling the job status endpoint.

### Process Patterns

**Error handling patterns:**

- Backend maps domain errors to HTTP + error envelope.
- Frontend parses error envelope in `apiClient` and surfaces `error.code` + `message`.
- User-facing errors must be actionable (what to do next).

**Loading state patterns:**

- React Query `isLoading/isFetching` is the source of truth for server data.
- Editor autosave shows a dedicated “saving/saved/error” indicator; do not reuse list-page loading spinners.

**Editing save patterns:**

- Debounced autosave (800–1500ms) + flush on navigation/unload.
- Server write semantics: overwrite existing `resultId`.

**Filesystem safety patterns (mandatory):**

- All persisted files live under `DATA_DIR`.
- DB stores only relative paths.
- Asset reads/writes go through a single safe-join utility; prevent directory traversal.

### Enforcement Guidelines

**All AI agents MUST:**

- Use the defined API shapes (`{ items, nextCursor }`, error envelope) and `camelCase` JSON.
- Use the standard SSE event types and payload fields.
- Respect `DATA_DIR` and relative-path-only persistence.
- Use a single `apiClient` for HTTP and a single safe-path helper for assets.

**Pattern enforcement:**

- If adding a new endpoint/event/table, update `architecture.md` and `api.md` in the same change.
- Prefer extending existing modules over creating parallel helpers with different naming.

### Pattern Examples

**Good examples:**

- `GET /api/v1/projects?limit=20&cursor=...` → `{ items: [...], nextCursor: "..." }`
- SSE `progress` event → `{ eventId, jobId, projectId, stage, progress, tsMs }`
- Asset retrieval via controlled route + safe path resolution

**Anti-patterns:**

- Mixing `snake_case` and `camelCase` fields in API payloads
- Returning `{ data: ... }` in some endpoints but direct DTO in others
- Storing absolute filesystem paths in DB or returning them to the client
- Adding a second HTTP client wrapper that does not parse the error envelope

## Project Structure & Boundaries

### Requirements Mapping → Components

- FR Category: Projects/Library（列表/详情/删除/latest_result）→ `services/core/app/api/projects.py` + `services/core/services/projects_service.py` + `services/core/db/repositories/projects_repo.py` + `apps/web/src/app/(main)/projects/*`
- FR Category: Ingest（URL/上传）→ `services/core/app/api/jobs.py` + `services/core/pipeline/stages/ingest.py` + `services/core/storage/*` + `apps/web/src/components/features/ingest/*`
- FR Category: Jobs（状态机/SSE/轮询降级）→ `services/core/app/api/jobs.py` + `services/core/app/sse/jobs_sse.py` + `services/core/worker/*` + `apps/web/src/lib/sse/*` + React Query keys
- FR Category: Pipeline（阶段/并发/产物）→ `services/core/pipeline/*` + `services/core/worker/*`
- FR Category: Results（渲染与恢复编辑态）→ `services/core/app/api/results.py` + `services/core/services/results_service.py` + `apps/web/src/app/(main)/projects/[projectId]/*`
- FR Category: Editing（Tiptap/mindmap autosave）→ `apps/web/src/components/features/editor/*` + `apps/web/src/lib/autosave/*` + `services/core/app/api/results.py`
- FR Category: Assets（受控读取/相对路径）→ `services/core/app/api/assets.py` + `services/core/storage/safe_paths.py` + `apps/web/src/components/features/assets/*`
- FR Category: Search（LIKE→FTS5）→ `services/core/app/api/search.py` + `services/core/services/search_service.py` + `apps/web/src/app/(main)/search/*`
- Cross-cutting: Auth/CORS/Config/Health → `services/core/app/middleware/*` + `services/core/app/api/health.py` + env files + `apps/web/src/lib/api/apiClient.ts`

### Complete Project Directory Structure

```text
video-helper/
├── README.md
├── api.md
├── develop_design.md
├── docker-compose.yml
├── .gitignore
├── .env.example
├── data/                           # default DATA_DIR (dev); docker mounts here
│   ├── db/
│   ├── projects/
│   └── cache/
├── apps/
│   └── web/
│       ├── package.json
│       ├── pnpm-lock.yaml
│       ├── next.config.ts
│       ├── tailwind.config.ts
│       ├── postcss.config.js
│       ├── tsconfig.json
│       ├── eslint.config.*
│       ├── public/
│       └── src/
│           ├── app/
│           │   ├── (main)/
│           │   │   ├── layout.tsx
│           │   │   ├── page.tsx
│           │   │   ├── projects/
│           │   │   │   ├── page.tsx
│           │   │   │   └── [projectId]/
│           │   │   │       ├── page.tsx
│           │   │   │       └── components/
│           │   │   ├── jobs/
│           │   │   └── search/
│           │   ├── api/             # Next.js internal routes if needed (optional)
│           │   ├── globals.css
│           │   └── layout.tsx
│           ├── components/
│           │   ├── ui/              # shadcn/ui
│           │   ├── layout/          # panels, resizers, shell
│           │   └── features/
│           │       ├── player/
│           │       ├── ingest/
│           │       ├── projects/
│           │       ├── jobs/
│           │       ├── editor/      # tiptap + mindmap
│           │       ├── keyframes/
│           │       └── search/
│           ├── lib/
│           │   ├── api/
│           │   │   ├── apiClient.ts
│           │   │   ├── endpoints.ts
│           │   │   ├── types.ts
│           │   │   └── queryKeys.ts
│           │   ├── sse/
│           │   │   ├── jobEvents.ts
│           │   │   └── useJobSse.ts
│           │   ├── state/
│           │   │   └── uiStore.ts
│           │   ├── utils/
│           │   └── config.ts
│           ├── styles/
│           └── types/
│       └── tests/                   # optional (if added later)
├── services/
│   └── core/
│       ├── pyproject.toml
│       ├── uv.lock
│       ├── .env.example
│       ├── alembic.ini
│       ├── alembic/
│       │   ├── env.py
│       │   └── versions/
│       └── src/
│           └── core/
│               ├── main.py
│               ├── app/
│               │   ├── api/
│               │   │   ├── health.py
│               │   │   ├── projects.py
│               │   │   ├── jobs.py
│               │   │   ├── results.py
│               │   │   ├── assets.py
│               │   │   └── search.py
│               │   ├── middleware/
│               │   │   ├── auth.py
│               │   │   ├── cors.py
│               │   │   └── request_id.py
│               │   └── sse/
│               │       └── jobs_sse.py
│               ├── db/
│               │   ├── session.py
│               │   ├── models/
│               │   ├── repositories/
│               │   └── migrations/
│               ├── services/
│               │   ├── projects_service.py
│               │   ├── jobs_service.py
│               │   ├── results_service.py
│               │   └── search_service.py
│               ├── pipeline/
│               │   ├── runner.py
│               │   └── stages/
│               │       ├── ingest.py
│               │       ├── transcribe.py
│               │       ├── segment.py
│               │       ├── analyze.py
│               │       └── assemble_result.py
│               ├── worker/
│               │   ├── scheduler.py
│               │   └── executor.py
│               ├── storage/
│               │   ├── layout.py
│               │   └── safe_paths.py
│               ├── external/
│               │   ├── ffmpeg.py
│               │   └── ytdlp.py
│               ├── schemas/
│               ├── settings.py
│               └── logging.py
└── _bmad-output/
  └── planning-artifacts/
    ├── prd.md
    ├── ux-design-specification.md
    └── architecture.md
```

### Architectural Boundaries

**API boundaries (FastAPI):**

- Public HTTP surface is only `/api/v1/*`.
- Auth enforcement is centralized in `app/middleware/auth.py` and applies to all API + asset streaming routes.
- SSE is isolated under `app/sse/` and shares DTOs with job status responses.

**Component boundaries (Next.js):**

- Pages compose feature components; feature components never call `fetch` directly.
- `lib/api/apiClient.ts` is the only place that knows base URL + bearer injection + error envelope parsing.
- Server-state is React Query; UI-state only in Zustand; editor local state not stored in React Query.

**Data boundaries:**

- SQLAlchemy models + repos are the only modules that touch the DB session.
- Pipeline stages do not reach into FastAPI route layer; they call services/storage.
- Filesystem access is only through `storage/safe_paths.py` and `storage/layout.py`.
- DB stores only relative paths under `DATA_DIR`.

## Architecture Validation Results

### Coherence Validation ✅

**Decision Compatibility:**

- Next.js App Router + React Query + Zustand + SSE is compatible; responsibilities are explicit (Query for server-state, Zustand for UI-state).
- FastAPI + SQLite + SQLAlchemy + Alembic is coherent for single-node MVP; WAL + busy-timeout cover light concurrent writes.
- `DATA_DIR` + relative-path-only persistence + backend-controlled asset routes satisfy privacy/path traversal constraints.

**Pattern Consistency:**

- API JSON uses `camelCase`, DB uses `snake_case`, bridged via Pydantic aliases.
- SSE event types and payload fields are standardized to avoid client/server drift.

**Structure Alignment:**

- `apps/web` and `services/core` boundaries reflect the chosen stack and prevent cross-layer coupling.
- Backend layering (routes → services → repos/pipeline/storage) aligns with consistency rules and reduces agent conflicts.

### Requirements Coverage Validation ✅

**Functional Requirements Coverage:**

- Projects/Library, Ingest (URL + upload), Jobs (SSE + polling fallback), Pipeline, Results, Editing (autosave), Assets (safe serving), Search (LIKE → FTS5), Model provider settings are all mapped to explicit modules.

**Non-Functional Requirements Coverage:**

- Reliability/Recoverability: persisted jobs + latest result pointer + SSE reconnect and polling fallback.
- Performance: cursor pagination + virtualization + bounded concurrent jobs + subprocess execution controls.
- Security/Privacy: no absolute paths, safe-join, controlled asset routes, remote Bearer auth option.

### Implementation Readiness Validation ✅

**Decision Completeness:**

- Core decisions + implementation patterns + project structure are specified.
- Important gaps closed by hardening API contracts in `api.md` (error envelope, list pagination shape, SSE payloads, upload endpoint, Range streaming, job log tail).

**Structure Completeness:**

- Directory tree and boundaries cover all major features and cross-cutting concerns.

### Gap Analysis Results

- Critical: none
- Important (addressed):
  - API/DTO contracts made copy/pasteable in `api.md`
  - Upload endpoint defined (multipart) and asset content supports HTTP Range
  - Job logs persistence clarified (MVP: full logs to file + HTTP tail)
  - Alembic/SQLAlchemy migration workflow standardized

### Architecture Completeness Checklist

- [x] Project context analyzed
- [x] Technology stack selected
- [x] Core architectural decisions documented
- [x] Implementation patterns defined
- [x] Project structure & boundaries defined
- [x] API contracts hardened for consistent implementation

### Architecture Readiness Assessment

**Overall Status:** READY FOR IMPLEMENTATION

## Architecture Completion & Handoff

我们已经完成了 `video-helper` 的架构工作流并把关键分歧点“钉死”，这会显著降低多代理/多人并行实现时的冲突概率。

### What We Locked In

- **Tech stack:** Next.js (App Router) + Tailwind + shadcn/ui；FastAPI；SQLite + SQLAlchemy + Alembic；React Query + Zustand；SSE。
- **Data & storage:** `DATA_DIR` 为唯一持久化根；DB 仅存相对路径；资产通过后端受控路由读取。
- **API contract (hard rules):** `/api/v1`；统一 error envelope；列表统一 `{ items, nextCursor }`；SSE 事件类型与 payload 字段固定。
- **Jobs & pipeline:** 阶段化 stage；`MAX_CONCURRENT_JOBS=2`；子进程执行 ffmpeg/yt-dlp；MVP job 日志全量按文件落盘并提供 tail 拉取。
- **Security:** 本地默认无登录；远程可选 Bearer；asset 路由复用同一鉴权。

### Next Steps (Implementation)

1) 以本文档为“唯一真相”，开始搭建仓库骨架（`apps/web` + `services/core`）并把环境变量与 `DATA_DIR` 契约跑通。
2) 优先实现最小闭环：`POST /api/v1/jobs`（JSON + multipart）→ Job 入队 → SSE/轮询 → `GET /jobs/{jobId}` 状态更新 → 产出 result。
3) 按 `api.md` 的契约落地：error envelope / pagination / SSE payload / Range streaming / logs tail。

如需，我可以继续带你跑后续的 Implementation Readiness（IR）或直接进入开发执行（Dev）。
