# video-helper — 统一标准 & 并行开发/依赖顺序（UYOLO 版）

本文件是所有 Story 的“统一真相（single source of truth）”。并行开发时，任何涉及接口/数据契约/错误码/事件字段/阶段名的改动，必须先改这里或引用的契约文件，再落到代码，避免多 agent 漂移。

## 1) 必须统一（先由单个 Agent 定标准）

### 1.1 API 基础约束（强约束）
- **API 前缀**：仅允许 `/api/v1/*`
- **错误 envelope**（所有非 2xx）：`{ "error": { "code": string, "message": string, "details"?: any, "requestId"?: string } }`
- **列表分页**：统一 cursor 形态：`{ items: T[], nextCursor: string | null }`
- **ID/时间戳**：实体 ID = UUID string；时间戳 = Unix epoch milliseconds（number）

补充约束（建议同样冻结）：
- **响应字段命名**：对外一律 camelCase（即使后端内部使用 snake_case）
- **请求/响应 Content-Type**：JSON 使用 `application/json`；上传使用 `multipart/form-data`
- **requestId**：建议后端中间件生成并回传（header 或 error.requestId），便于排障

### 1.2 SSE 契约（强约束）
- Endpoint：`GET /api/v1/jobs/{jobId}/events`
- 事件类型仅：`heartbeat | progress | log | state`
- payload 字段 **camelCase**，必须包含：`eventId, tsMs, jobId, projectId, stage`，可选：`progress, message`
- 支持 `Last-Event-ID` best-effort 续传（无法续传时也要稳定降级为“从当前状态继续”）

### 1.3 Job stage 命名（对外稳定）
对外 stage 建议集合（允许内部更细，但对外必须映射到稳定集合）：
- `ingest` / `transcribe` / `segment` / `analyze` / `assemble_result` / `extract_keyframes`

### 1.4 资源与路径安全（强约束）
- 所有资源必须落在 `DATA_DIR` 下；DB 只存相对路径
- 资源访问必须走后端受控路由 + safe-join（防目录穿越）
- 错误响应不得泄露绝对路径、Key、stacktrace

### 1.6 鉴权与部署模式（强约束）
- 本地默认可不启用登录；远程模式可启用 Bearer：`Authorization: Bearer <token>`
- 一旦启用鉴权：必须同时覆盖 API 与 assets content 路由，不能“只保护 API 不保护静态资源”

### 1.7 配置/环境变量（建议冻结，便于可复现）
- `DATA_DIR`：资源与 DB 的根目录（默认本机路径；对外不暴露）
- `MAX_CONCURRENT_JOBS`：默认 2
- `CORS_ORIGINS`（或等价）：Docker/远程部署时可配置
- `LOG_LEVEL`：默认 info
- 上传限制（建议）：`MAX_UPLOAD_MB` 或等价

### 1.8 错误码注册表（强约束）
建议以“单文件注册表”冻结错误码（后端/前端共用），至少覆盖：
- 输入校验：`VALIDATION_ERROR`、`UNSUPPORTED_SOURCE_TYPE`、`INVALID_SOURCE_URL`
- 资源不存在：`PROJECT_NOT_FOUND`、`JOB_NOT_FOUND`、`ASSET_NOT_FOUND`、`RESULT_NOT_FOUND`
- 依赖缺失：`FFMPEG_MISSING`、`YTDLP_MISSING`
- 任务执行：`JOB_STAGE_FAILED`、`JOB_CANCELED`、`JOB_NOT_CANCELLABLE`
- 资源不足：`RESOURCE_EXHAUSTED`（CPU/RAM/磁盘/并发）
- 权限：`UNAUTHORIZED`、`FORBIDDEN`
- 资源越界：`PATH_TRAVERSAL_BLOCKED`

### 1.5 工程结构（强约束）
- 前端：`apps/web`（Next.js App Router + TS）
- 后端：`services/core`（FastAPI）
- 合同/DTO/枚举建议集中：
  - 后端：`services/core/app/contracts/*`（DTO/schema、error codes、stage enum、SSE event schema）
  - 前端：`apps/web/src/lib/contracts/*`（与后端字段一致；可手写或后续生成，但必须一致）

## 2) 并行开发的“先后顺序”与依赖图

### 2.1 必须先做（避免契约冲突）
以下工作建议由 **一个 agent** 先落地/冻结（产出契约与最小骨架），其它 agent 再并行：
1) **Story 8.1（Contract）**：补全并锁定 Result/Assets 读取契约（含字段名、示例、错误码）
2) **Story 5.4（Stage 映射）**：稳定 stage 集合与对外映射（含 SSE/state/progress 语义）
3) **错误码清单**：至少覆盖：输入不合法、资源/依赖缺失、网络/下载失败、模型/Key 不可用、资源不足、Job/Project 不存在、越权/越界资源
4) **DB 基本表结构**（projects/jobs/results/assets + 必要索引/约束）与迁移策略（Alembic）

> 说明：一旦这些“接口/枚举/契约”冻结，前后端即可高度并行，避免返工。

### 2.2 可以并行的分工（建议 Worktree/Branch）

#### 并行块 A：后端基础 API（BE/core）
- Epic 1/2/3/4 的后端 story 可串行推进，但可由多个后端 agent 分摊不同子域：
  - projects（2.1/2.3）
  - jobs ingest（3.1/3.2/3.4）
  - jobs progress/sse/logs（4.1/4.2/4.4/4.6）

#### 并行块 B：前端骨架与页面（FE/web）
- 只要契约冻结（2.1），前端可在后端未完成时使用 mock（MSW/本地 mock 数据）先做：
  - Health banner（1.2）
  - Projects 页面（2.2/2.4）
  - Ingest 页面（3.3）
  - Job 详情页与 SSE 客户端（4.3/4.5）

#### 并行块 C：流水线（Pipeline）
- worker/queue（5.1）与 stage 映射（5.4）确定后，流水线各 stage 可分配给不同后端 agent：
  - transcribe（5.2）
  - segment（5.3）
  - keyframes（6.1）
  - highlights（6.2）
  - mindmap（7.1）
  - assemble_result（8.3）

### 2.3 建议执行顺序（高效最小闭环优先）
1) **契约/标准冻结**：8.1 + 5.4 + error codes + DB schema
2) **可见性闭环**：1.1 + 4.1 + 4.2 + 4.3 + 4.5（先让“进度可见、失败可解释”跑通）
3) **导入闭环**：3.1/3.2/3.3 + 3.4
4) **项目库闭环**：2.1/2.2 + 2.3/2.4
5) **最小分析闭环**：5.1/5.2/5.3 + 8.3 + 8.4/8.6
6) **体验增强**：8.5 + 6.x + 7.1
7) **编辑持久化**：9.x
8) **搜索/设置**：10.x

## 3) Worktree/Branch 派发规范（建议）
- 分支名：`feat/<area>/<storyKey>`
  - 例：`feat/be/4-2-be-core-job-sse`、`feat/fe/2-2-fe-web-project-pages`
- 每个 worktree 只做一个 story（或同 epic 的紧密相邻 story），合并前跑基础 lint/test
- **禁止** 多个 agent 同时改“契约/枚举/DTO 文件”，除非先在本文件里协商并锁定字段

## 4) 需要一次性冻结的“变更门”
- stage 名集合与映射
- SSE event schema（字段名/类型）
- error code 列表与含义
- Result/Assets/Jobs/Projects 的核心 DTO 字段（camelCase）

建议新增冻结项：
- health 响应 schema（哪些字段、如何表达缺依赖/建议动作）
- assets content 路由（是否需要 Range、Content-Type/mime 规则）
- Job 状态机（queued/running/succeeded/failed/canceled）与可重试/可取消语义

参考：
- _bmad-output/planning-artifacts/epics.md
- _bmad-output/planning-artifacts/prd.md
- _bmad-output/planning-artifacts/architecture.md
- api.md
