---
stepsCompleted:
  - step-01-validate-prerequisites
  - step-02-design-epics
  - step-03-create-stories
inputDocuments:
  - _bmad-output/planning-artifacts/prd.md
  - _bmad-output/planning-artifacts/architecture.md
  - _bmad-output/planning-artifacts/ux-design-specification.md
  - api.md
  - develop_design.md
---

# video-helper - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for video-helper, decomposing the requirements from the PRD, UX Design, and Architecture requirements into implementable stories.

## Requirements Inventory

### Functional Requirements

FR1: 用户可以创建一个 Project 来承载单个视频的分析与笔记资产。
FR2: 用户可以查看 Project 列表（支持分页/排序）。
FR3: 用户可以查看 Project 详情（含来源、更新时间、latest_result 指针等）。
FR4: 用户可以删除 Project，并同时删除其关联数据与资源。
FR5: 系统可以为 Project 维护“最新可渲染结果”的引用关系（latest_result）。
FR6: 用户可以通过粘贴外链创建分析任务，外链来源至少支持 YouTube 与 B 站。
FR7: 用户可以在 Web 端上传本地视频文件并创建分析任务。
FR8: 系统可以校验导入输入的合法性（例如链接格式/文件类型等），并在不合法时返回可理解提示。
FR9: 系统可以抽取并持久化视频的基础元信息（例如时长/格式）并关联到 Project。
FR10: 用户可以为一个 Project 创建分析 Job（类型：analyze_video）。
FR11: 用户可以查询 Job 状态（queued/running/succeeded/failed/canceled）、stage、progress。
FR12: 用户可以订阅 Job 的进度事件流（SSE），并接收阶段与进度更新。
FR13: 当事件流不可用或断线时，客户端可以通过轮询继续获取 Job 状态并恢复展示。
FR14: 用户可以取消正在运行的 Job（可选）。
FR15: 当 Job 失败时，系统可以返回结构化错误信息（error_code/error_message/error_details）。
FR16: 用户可以对失败的 Job 发起重试（在同一 Project 语境下再次分析）。
FR17: 系统可以对导入视频执行转写，产出带时间戳的 transcript（对外是否暴露可选）。
FR18: 系统可以基于转写结果进行章节切片，并生成 Chapters 列表（start_ms/end_ms/title/summary）。
FR19: 系统将 Chapters 作为后续产物生成与 UI 跳转的唯一结构与时间准则。
FR20: 系统可以并发生成思维导图产物（nodes/edges），并与 chapter_id 具备可追溯关联。
FR21: 系统可以为每章生成重点摘要（highlights 列表），并可关联 time_ms 或 chapter_id。
FR22: 系统可以为每章生成并持久化关键帧截图（assets），并可关联 chapter_id 与可选 time_ms。
FR23: 系统可以将章节/导图/笔记/重点/关键帧汇总为一次 Result，并落库可回放渲染。
FR24: 系统可以为 Result 记录轻量版本标识（schema_version/pipeline_version 类字段）。
FR25: 用户可以获取某 Project 的最新 Result。
FR26: 用户可以在结果页查看章节列表，并基于章节进行时间跳转（start_ms/end_ms）。
FR27: 用户可以在结果页查看每章重点摘要。
FR28: 用户可以在结果页查看每章关键帧，并将关键帧作为视觉锚点辅助定位与复习。
FR29: 用户可以在结果页查看思维导图（graph: nodes/edges）。
FR30: 用户可以在结果页进行“章节跳转/看重点/看关键帧”的高频复习操作闭环。
FR31: 用户可以编辑章节信息（至少包含章节标题；可选包含章节时间范围与章节顺序）。
FR32: 系统在章节被用户编辑后，仍能保证“章节作为唯一准则”的一致性要求对外成立（例如章节跳转与章节索引不失效）。
FR33: 用户可以编辑并保存笔记内容（富文本结构化数据）。
FR34: 用户可以编辑并保存思维导图（节点/连线的增删改）。
FR35: 用户可以更新关键帧/图片与章节或笔记模块的关联关系（绑定/替换/排序）。
FR36: 保存后系统可以将用户编辑内容持久化，并在再次打开项目时恢复编辑态。
FR37: 系统可以管理项目资源（assets），并将资源与 Project/Chapter 关联。
FR38: 系统可以提供资源访问接口以供前端渲染图片/截图。
FR39: 系统在资源访问时应限制路径范围以防止目录穿越。
FR40: 用户可以基于关键词搜索项目/笔记内容（MVP 可先支持标题/摘要/派生文本）。
FR41: 系统可以返回可定位到 Project/Chapter 的搜索结果（至少能打开到对应项目）。
FR42: 运维/高级用户可以配置模型提供方与参数（provider/base_url/model 等）。
FR43: 运维/高级用户可以配置 API Key 的使用方式（至少支持传入并在服务端使用；是否落盘由实现决定）。
FR44: 系统可以在模型配置无效时给出可理解提示，并阻止启动分析或在失败时归因明确。
FR45: 客户端可以调用健康检查接口判断服务可用性与关键依赖就绪状态。
FR46: 当分析失败时，用户可以看到可理解的失败原因分类与建议行动（与错误码体系一致）。

### NonFunctional Requirements

NFR1: Web 端关键交互的主观响应应流畅：常规操作（切换章节/展开卡片/保存按钮点击等）在常见设备上应达到约 ≤200ms 的界面反馈（以“不明显卡顿”为准）。
NFR2: 对 10–30 分钟视频，端到端分析完成时间目标 ≤10 分钟（测试条件需可复现：模型配置、是否 GPU、并发设置）。
NFR3: 结果页在长内容下应避免一次性渲染导致卡顿，列表型内容需要支持分段加载/虚拟化，保证滚动与交互可用。
NFR4: Job 进度推送应默认通过 SSE 工作，并通过心跳降低“假断线”风险。
NFR5: SSE 不可用或断线时，客户端必须自动降级为轮询，且用户仍能继续看到 job 的最新状态与错误信息。
NFR6: 刷新/重启后，用户应能恢复到：Project 列表与详情可读；Job 详情仍可查看阶段/错误详情/重试入口；Result 可重新渲染（不依赖前端内存状态）。
NFR7: 默认本地优先：持久化数据与资源应存于本机 DATA_DIR 范围内，对外不暴露绝对路径。
NFR8: 静态资源访问必须进行路径限制，防止目录穿越与任意文件读取。
NFR9: API Key 不应以明文持久化到磁盘；同时日志与错误详情中不应泄露 Key 等敏感信息。
NFR10: MVP 达到基础可访问性：主流程支持键盘操作、按钮/表单具备语义与必要的 aria 标签、文本对比度与可读性满足基本可用。
NFR11: 同时支持源码运行与 Docker 运行；部署配置（API base url、CORS、DATA_DIR、模型配置）可通过环境变量或配置文件调整。
NFR12: 自部署场景下默认支持同时 2 个 Job 并发运行；资源不足时应可理解地排队或报错，而不是无响应。

### Additional Requirements

- 技术栈/工程形态：前端 Next.js（App Router）+ Tailwind + shadcn/ui；后端 FastAPI（Python）；持久化 SQLite + SQLAlchemy 2.x + Alembic；前端数据层 React Query，UI 状态 Zustand。
- 初始化脚手架（架构已选定）：`apps/web` 使用 `create-next-app`（TS/Tailwind/ESLint/App Router/src-dir/@/* alias/pnpm）；UI 体系用 shadcn 初始化；后端 `services/core` 用 uv 管理依赖。
- API 版本与前缀强约束：所有公共 HTTP 面仅允许 `/api/v1/*`。
- 错误统一 envelope（强约束）：`{ error: { code, message, details?, request_id? } }`；禁止返回 stacktrace/敏感信息（默认）。
- 列表分页统一形态（强约束）：所有 list/search 返回 `{ items: [...], nextCursor }`，使用 cursor 分页。
- SSE 契约（强约束）：`GET /api/v1/jobs/{jobId}/events`，事件类型仅 `heartbeat|progress|log|state`；payload 字段 camelCase 且包含 `eventId, tsMs, jobId, projectId, stage, progress?, message?`；支持 `Last-Event-ID` best-effort 续传。
- 时间戳与 ID 约束：时间戳统一 Unix epoch milliseconds（number）；实体 ID 统一 UUID string。
- Job 阶段模型：stage 名必须稳定并与 UI 对齐（建议 ingest/transcribe/segment/analyze/assemble_result/extract_keyframes；或在内部细分但对外保持稳定映射）。
- Job 可恢复性：刷新/重启后 Job 状态、日志与 Result 必须可查询；SSE 断开自动降级轮询（前端无感）。
- Job 并发：应用层队列 + 并发上限（默认 2）；需要 DB-backed claim 机制防止重复消费。
- 取消语义：cooperative cancellation；标记 canceled 后停止调度后续 stage，尽力终止 subprocess（ffmpeg/yt-dlp 等）。
- Job 日志：MVP 推荐按文件落盘并提供 logs tail HTTP API（带 cursor）。
- Ingest 输入边界：Web/Docker 不接受 `source_file_path`；上传/外链成为服务端“导入资源真相”；桌面端未来可扩展 `source_file_path`。
- 资产/文件路径安全（强约束）：所有资源必须落在 `DATA_DIR` 下；DB 只存相对路径；资源访问必须通过后端受控路由 + safe-join 防目录穿越；远程模式下 asset 路由同样需要鉴权。
- 数据库运维：SQLite 建议 WAL + busy timeout；迁移用 Alembic（必要时用 batch operations）。
- 编辑写入语义：保存覆盖现有 `result_id`（MVP 不做“每次保存生成新版本”）；需要 `updated_at`/ETag 类字段支持前端对账。
- 前端状态边界：server-state 进 React Query；UI-only 状态进 Zustand；编辑器本地状态不放入 React Query（避免重渲染/冲突）。
- 编辑保存策略：debounced autosave（建议 800–1500ms）+ 导航/卸载 flush；保存成功/失败需明确反馈。
- 结果页核心布局/交互（UX 强约束）：Desktop Tri-Pane Focus（左视频+导图、右笔记）；Sticky Floating Player 用 Intersection Observer 触发悬浮；Mobile <768px 垂直堆叠与 tab view。
- 设计系统落地（UX 强约束）：Warm Minimalist（`bg-[#FDFBF7]`、stone 系列、橙色 accent）；卡片/按钮/骨架屏样式与对比度要求；React Flow 节点“便签/索引卡”风格。
- 健康检查：提供 `/api/v1/health` 并检测关键依赖（ffmpeg/yt-dlp；可选 provider connectivity）。
- 鉴权模式：本地默认无登录；远程可选 Bearer（`Authorization: Bearer <token>`），并通过统一中间件/依赖在 API + asset streaming 上一致执行。
- 并行开发防漂移约束：命名规范（ID 字段 camelCase 等）、API shape、SSE payload、错误码与资产路径工具必须集中定义/复用，避免多 agent 各自发挥造成契约不一致。

### FR Coverage Map

FR1: Epic 2 - 创建项目承载视频与笔记资产
FR2: Epic 2 - 项目列表（分页/排序）
FR3: Epic 2 - 项目详情（来源/更新时间/latest_result）
FR4: Epic 2 - 删除项目（含关联数据与资源）
FR5: Epic 2 - 维护 latest_result 指针

FR6: Epic 3 - 外链导入（YouTube/B 站）创建分析
FR7: Epic 3 - Web 端上传视频创建分析
FR8: Epic 3 - 导入输入合法性校验与可理解提示
FR9: Epic 3 - 抽取并持久化视频基础元信息

FR10: Epic 3 - 创建分析 Job（analyze_video）
FR11: Epic 4 - 查询 Job 状态（status/stage/progress）
FR12: Epic 4 - 订阅 Job SSE 进度事件流
FR13: Epic 4 - SSE 断线/不可用自动降级轮询
FR14: Epic 4 - 取消 Job（可选）
FR15: Epic 4 - Job 失败返回结构化错误信息
FR16: Epic 4 - 对失败 Job 发起重试

FR17: Epic 5 - 转写产出 transcript（带时间戳）
FR18: Epic 5 - 章节切片产出 Chapters（start/end/title/summary）
FR19: Epic 5 - Chapters 作为唯一结构与时间准则

FR20: Epic 7 - 生成思维导图（nodes/edges）并可追溯
FR21: Epic 6 - 生成每章重点摘要（highlights）并可追溯
FR22: Epic 6 - 生成并持久化关键帧（assets）并可追溯
FR23: Epic 8 - 汇总章节/导图/笔记/重点/关键帧为 Result 并落库
FR24: Epic 8 - Result 记录 schema/pipeline 版本字段

FR25: Epic 8 - 获取某 Project 的最新 Result
FR26: Epic 8 - 结果页章节列表与时间跳转播放
FR27: Epic 8 - 结果页每章重点摘要展示
FR28: Epic 8 - 结果页每章关键帧展示与跳转
FR29: Epic 8 - 结果页思维导图渲染
FR30: Epic 8 - 章节跳转/看重点/看关键帧的复习闭环

FR31: Epic 9 - 编辑章节信息
FR32: Epic 9 - 章节编辑后仍保持“章节唯一准则”一致性
FR33: Epic 9 - 编辑并保存笔记（富文本结构化数据）
FR34: Epic 9 - 编辑并保存思维导图
FR35: Epic 9 - 更新关键帧/图片与章节/笔记模块的关联
FR36: Epic 9 - 编辑内容持久化并可恢复编辑态

FR37: Epic 8 - 管理项目资源（assets）并关联 Project/Chapter
FR38: Epic 8 - 提供资源访问接口供前端渲染
FR39: Epic 8 - 资源访问路径限制（防目录穿越）

FR40: Epic 10 - 关键词搜索项目/笔记（MVP 轻量）
FR41: Epic 10 - 返回可定位到 Project/Chapter 的搜索结果

FR42: Epic 10 - 配置模型提供方与参数
FR43: Epic 10 - 配置 API Key 使用方式（不落盘/边界明确）
FR44: Epic 10 - 模型配置无效提示并阻止/归因明确

FR45: Epic 1 - 健康检查接口判断依赖与服务就绪
FR46: Epic 4 - 失败原因分类与可行动建议（与错误码体系一致）

## Epic List

### Epic 1: 可安装可自检的基础系统（First Run & Health）
用户可以在源码/Docker 形态下启动服务，并通过健康检查确认 ffmpeg/yt-dlp/可选模型依赖就绪，避免“跑不起来”。
**FRs covered:** FR45
**Implementation notes:** 统一 `/api/v1/health` 输出；把 DATA_DIR/鉴权模式/日志级别等环境变量约定写清；为后续 epics 提供稳定基础。

### Epic 2: 项目库（Projects）— 创建/列表/详情/删除 + latest_result
用户可以管理多个视频项目，并快速打开最新结果（即使 Job/结果还没做完，也能先完成“库”的闭环）。
**FRs covered:** FR1, FR2, FR3, FR4, FR5
**Implementation notes:** Cursor pagination + 统一字段命名（camelCase 输出）；删除需级联清理 DB + DATA_DIR 资源。

### Epic 3: 导入视频并创建分析任务（URL/上传）
用户可以通过外链或上传文件创建分析任务（系统自动创建 Project + Job），并获得可靠的输入校验与元信息抽取。
**FRs covered:** FR6, FR7, FR8, FR9, FR10
**Implementation notes:** `POST /api/v1/jobs` 同时支持 JSON 与 multipart；Web/Docker 严禁 `source_file_path` 成为真相；落盘路径只存相对 DATA_DIR。

### Epic 4: 任务进度、日志与失败恢复（SSE + 轮询降级）
用户可以实时/可恢复地观察任务进度、查看日志、在失败时获得可行动建议，并可取消/重试任务。
**FRs covered:** FR11, FR12, FR13, FR14, FR15, FR16, FR46
**Implementation notes:** SSE 事件类型与 payload 字段必须严格对齐 api.md；前端 SSE 断线自动降级轮询；日志 tail 用 cursor；错误统一 envelope。

### Epic 5: 转写与章节切片（Chapters 作为唯一准则）
用户可以获得基于转写的章节结构（start/end/title/summary），并确保后续产物/跳转统一以 Chapters 为准。
**FRs covered:** FR17, FR18, FR19
**Implementation notes:** stage/progress 映射稳定；章节 ID 与时间戳规范化（ms）；产物持久化后可重放。

### Epic 6: 每章重点与关键帧产出（Highlights + Keyframes）
用户可以看到每章重点摘要与关键帧截图，并能追溯到 chapter_id/time_ms。
**FRs covered:** FR21, FR22
**Implementation notes:** 关键帧与 highlights 都需引用 Chapters；截图落盘与 asset 记录严格走安全路径工具。

### Epic 7: 思维导图产出（Mindmap）
用户可以看到基于章节的思维导图（nodes/edges），并能追溯到 chapter_id。
**FRs covered:** FR20
**Implementation notes:** 先定义最小 graph schema（节点/连线/章节引用），避免后续前后端对结构各自发挥。

### Epic 8: 结果汇总与复习体验（Results & Review）
用户可以在结果页完成核心复习动作：章节跳转播放、看重点、看关键帧、看导图；并且 assets 受控访问安全可靠。
**FRs covered:** FR23, FR24, FR25, FR26, FR27, FR28, FR29, FR30, FR37, FR38, FR39
**Implementation notes:** 结果页遵循 UX 的 Tri-Pane + Sticky Floating Player；assets 必须通过后端路由流式读取（可扩展 Range）；Result 必须可独立渲染。

### Epic 9: 编辑与持久化（Notes / Mindmap / Chapters / Keyframe Binding）
用户可以编辑章节、笔记、导图与关键帧关联并保存，刷新/重启后仍可恢复继续编辑。
**FRs covered:** FR31, FR32, FR33, FR34, FR35, FR36
**Implementation notes:** 保存语义为覆盖式更新（MVP）；前端 debounced autosave + flush；需要更新冲突最小策略（updatedAt/ETag）。

### Epic 10: 搜索与模型设置（MVP 轻量）
高级用户可以配置模型提供方与参数并获得可理解的错误提示；用户可进行轻量搜索定位到项目/章节。
**FRs covered:** FR40, FR41, FR42, FR43, FR44
**Implementation notes:** API key 不通过 HTTP 落盘；搜索 MVP 可从标题/摘要/派生文本开始，后续再演进 FTS5。

## Epic 1: 可安装可自检的基础系统（First Run & Health）

用户可以在源码/Docker 形态下启动服务，并通过健康检查确认关键依赖就绪，避免“跑不起来”（可并行：Backend=services/core，Frontend=apps/web）。

### Story 1.1: [BE/core] 健康检查接口与依赖自检

As a 运维/高级用户,
I want 调用健康检查接口即可看到服务与依赖就绪状态,
So that 我能快速定位“不能分析”的原因。

**Acceptance Criteria:**

**Given** 服务启动完成
**When** 我请求 `GET /api/v1/health`
**Then** 返回 HTTP 200 且响应包含服务状态与依赖检查结果（至少覆盖 ffmpeg、yt-dlp；可选包含 provider connectivity）
**And** 所有时间戳字段使用 Unix epoch milliseconds（如有）

**Given** ffmpeg 或 yt-dlp 缺失
**When** 我请求 `GET /api/v1/health`
**Then** 返回 HTTP 200 但在 payload 中明确标记缺失项与可行动建议
**And** 不返回任何主机绝对路径或敏感信息

### Story 1.2: [FE/web] 启动自检提示（Health Banner）

As a 用户,
I want 在创建分析前就看到依赖是否就绪的提示,
So that 我不会提交后才发现缺依赖。

**Acceptance Criteria:**

**Given** 前端可访问后端
**When** 我进入导入/创建任务页面
**Then** 页面会调用 `GET /api/v1/health` 并展示“可分析/不可分析”的清晰状态
**And** 不阻塞页面其它交互（异步加载 + skeleton）

**Given** 健康检查显示缺依赖
**When** 我查看提示
**Then** 我能看到可行动的修复建议（例如安装 ffmpeg/yt-dlp，或检查模型配置）

## Epic 2: 项目库（Projects）— 创建/列表/详情/删除 + latest_result

用户可以管理多个视频项目，并快速打开最新结果（可并行：Backend=services/core，Frontend=apps/web）。

### Story 2.1: [BE/core] Project 持久化与项目查询 API（list/detail）

As a 用户,
I want 查看项目列表与项目详情,
So that 我能管理多个视频并随时打开。

**Acceptance Criteria:**

**Given** 数据库为空
**When** 我请求项目列表接口（cursor pagination）
**Then** 返回 `{ items: [], nextCursor: null }`
**And** 响应字段使用 camelCase（例如 `projectId`, `updatedAtMs`, `latestResultId`）

**Given** 存在多个项目
**When** 我以 `limit` 获取项目列表
**Then** 返回 items 数量不超过 limit 且包含稳定排序与 `nextCursor`
**And** `nextCursor` 可用于获取下一页且不会重复/漏项（以游标语义为准）

**Given** 我请求不存在的项目详情
**When** 服务处理请求
**Then** 返回统一错误 envelope：`{ "error": { "code", "message", "details"? } }`

### Story 2.2: [FE/web] 项目列表页与项目详情页（含分页/虚拟化）

As a 用户,
I want 在 Web 端浏览项目列表并进入项目详情,
So that 我可以快速切换不同视频的复习资产。

**Acceptance Criteria:**

**Given** 项目数量较多
**When** 我滚动项目列表
**Then** 列表使用虚拟化或分段加载，保持交互流畅（主观不明显卡顿）
**And** 翻页使用 cursor（而非 offset），并正确追加/替换数据

**Given** 某项目存在 `latestResultId`
**When** 我在列表/详情中点击“打开”
**Then** 我会被路由到该项目的结果页入口（若结果未就绪则显示状态页）

### Story 2.3: [BE/core] 删除项目（级联清理 DB + DATA_DIR 资源）

As a 用户,
I want 删除一个项目并清理其关联数据与资源,
So that 本地空间不会被长期占用。

**Acceptance Criteria:**

**Given** 项目存在且包含 results/assets/chapters 等关联记录
**When** 我请求删除项目接口
**Then** 关联 DB 记录被删除或标记不可见（按设计一致）
**And** `DATA_DIR` 下该项目目录被安全删除（不允许删除越界路径）

**Given** 删除过程中出现文件占用/权限问题
**When** 服务处理删除
**Then** 返回结构化错误 envelope 且不泄露绝对路径

### Story 2.4: [FE/web] 删除项目交互（确认、反馈、回收列表状态）

As a 用户,
I want 在 UI 中安全地删除项目,
So that 我不误删且能明确看到结果。

**Acceptance Criteria:**

**Given** 我点击“删除项目”
**When** 弹出确认对话框
**Then** 我必须确认后才会发起删除请求
**And** 删除成功后项目从列表/缓存中移除并提示成功

**Given** 删除失败
**When** UI 接收到错误 envelope
**Then** UI 显示可理解提示并允许重试

## Epic 3: 导入视频并创建分析任务（URL/上传）

用户可以通过外链或上传文件创建分析任务（系统自动创建 Project + Job）（可并行：Backend=services/core，Frontend=apps/web）。

### Story 3.1: [BE/core] 创建 Job（URL 输入的 JSON 形态）

As a 用户,
I want 粘贴 YouTube/B 站链接即可创建分析任务,
So that 我能开始自动分析流程。

**Acceptance Criteria:**

**Given** 我提交 `POST /api/v1/jobs`（`application/json`，包含 `sourceType` 与 `sourceUrl`）
**When** 输入合法
**Then** 返回 HTTP 200 且响应包含 `jobId`, `projectId`, `status=queued`, `createdAtMs`
**And** 同时创建并持久化对应 Project 与 Job 记录

**Given** `sourceUrl` 非法或 `sourceType` 不支持
**When** 服务校验请求
**Then** 返回统一错误 envelope，错误 code 可区分“输入不合法/平台不支持”

### Story 3.2: [BE/core] 创建 Job（上传文件的 multipart 形态）

As a 用户,
I want 通过 Web 上传视频文件并创建分析任务,
So that 我不用依赖本地路径作为真相。

**Acceptance Criteria:**

**Given** 我提交 `POST /api/v1/jobs`（`multipart/form-data`，包含 `sourceType=upload` 与 `file`）
**When** 文件类型与大小符合服务端限制
**Then** 服务把文件落盘到 `DATA_DIR` 下的受控目录并创建 Project + Job
**And** DB 中只保存相对路径（不保存绝对路径）

**Given** 上传文件类型不支持
**When** 服务校验
**Then** 返回统一错误 envelope 且 message 可理解

### Story 3.3: [FE/web] 导入页（URL/上传双入口）

As a 用户,
I want 在一个页面里选择“粘贴链接”或“上传文件”创建分析,
So that 我能用最适合我的方式导入视频。

**Acceptance Criteria:**

**Given** 我选择“粘贴链接”
**When** 我提交表单
**Then** UI 调用 `POST /api/v1/jobs` JSON 并跳转到 Job 详情/进度页

**Given** 我选择“上传文件”
**When** 我提交表单
**Then** UI 发起 multipart 请求并显示上传中状态与错误提示

### Story 3.4: [BE/core] 视频元信息抽取与持久化（duration/format）

As a 用户,
I want 项目详情能显示视频时长等基础信息,
So that 我能预期分析与复习成本。

**Acceptance Criteria:**

**Given** Job 创建完成
**When** 服务对视频执行元信息抽取
**Then** 将 durationMs/format 等元数据持久化到 Project 或关联表
**And** 任何失败返回可归因的错误 code（例如依赖缺失/文件不可读）

## Epic 4: 任务进度、日志与失败恢复（SSE + 轮询降级）

用户可以可靠地观察进度、查看日志、在失败时获得可行动建议，并可取消/重试（可并行：Backend=services/core，Frontend=apps/web）。

### Story 4.1: [BE/core] Job 状态查询 API（轮询降级基础）

As a 用户,
I want 查询 Job 的 status/stage/progress,
So that 在 SSE 不可用时仍可恢复进度展示。

**Acceptance Criteria:**

**Given** Job 存在
**When** 我请求 `GET /api/v1/jobs/{jobId}`
**Then** 返回包含 `status`, `stage`, `progress`, `error`, `updatedAtMs` 的 job DTO
**And** `stage` 使用稳定命名（与 api.md 约束一致）

**Given** Job 不存在
**When** 我请求 `GET /api/v1/jobs/{jobId}`
**Then** 返回统一错误 envelope（如 `JOB_NOT_FOUND`）

### Story 4.2: [BE/core] Job SSE 事件流（含心跳与 Last-Event-ID）

As a 用户,
I want 订阅 Job 的 SSE 事件流获取 progress/log/state,
So that 我能实时看到分析推进且不中断。

**Acceptance Criteria:**

**Given** 我连接 `GET /api/v1/jobs/{jobId}/events`
**When** Job 执行中
**Then** 服务周期性发送 `heartbeat` 事件
**And** `progress/log/state` 事件类型与 payload 字段严格符合 api.md（camelCase，含 `eventId`, `tsMs`, `jobId`, `projectId`, `stage`）

**Given** 我带 `Last-Event-ID` 重连
**When** 服务可 best-effort 获取后续事件
**Then** 尽量从该 eventId 之后继续推送（无法续传时也不得崩溃，应从当前状态继续）

### Story 4.3: [FE/web] SSE 消费与轮询降级（React Query 驱动）

As a 用户,
I want 前端默认用 SSE 展示进度并在断线时自动降级轮询,
So that 页面刷新/网络波动也能持续可用。

**Acceptance Criteria:**

**Given** SSE 连接正常
**When** 收到 `progress/state/log` 事件
**Then** 前端更新 React Query 中对应 job 的缓存状态
**And** UI 只从缓存派生展示（避免双状态源）

**Given** SSE 连接关闭或超时未收到事件
**When** 前端判定不可用
**Then** 自动切换到轮询 `GET /api/v1/jobs/{jobId}` 并维持可见进度更新

### Story 4.4: [BE/core] Job 日志 tail API（cursor）

As a 用户,
I want 在 Job 运行/失败时查看可分页的日志尾部,
So that 我能理解失败原因并自助排查。

**Acceptance Criteria:**

**Given** Job 有日志输出
**When** 我请求 `GET /api/v1/jobs/{jobId}/logs?limit=200&cursor=...`
**Then** 返回 `{ items, nextCursor }` 且 items 每条包含 `tsMs`, `level`, `message`, `stage`
**And** cursor 为 opaque，不泄露文件路径/偏移细节

### Story 4.5: [FE/web] Job 详情页（进度条 + 阶段 + 日志）

As a 用户,
I want 在 Job 详情页看到阶段化进度与日志,
So that 我能判断是否卡住、失败该怎么做。

**Acceptance Criteria:**

**Given** Job 运行中
**When** 我打开 Job 详情页
**Then** 我能看到 `status/stage/progress` 的可视化展示
**And** 我能看到日志 tail（按需加载/自动追尾）

**Given** Job 失败且返回 error envelope
**When** UI 展示错误
**Then** UI 显示可行动建议并提供“重试”入口（若 API 支持）

### Story 4.6: [BE/core] 取消与重试（可选取消 + 失败重试）

As a 用户,
I want 取消正在运行的任务并对失败任务发起重试,
So that 我能在资源不足或配置修复后继续完成闭环。

**Acceptance Criteria:**

**Given** Job 状态为 running
**When** 我请求 `POST /api/v1/jobs/{jobId}/cancel`
**Then** 返回 `{ ok: true }` 且 Job 最终进入 `canceled`
**And** 后端尽力终止相关 subprocess 并停止调度后续 stages

**Given** Job 状态为 failed
**When** 我请求重试接口（需在 api.md 明确路径与请求体）
**Then** 系统在同一 Project 下创建新的 Job（新 jobId）并返回 queued
**And** 错误/进度契约与普通 Job 一致

## Epic 5: 转写与章节切片（Chapters 作为唯一准则）

用户可以获得稳定的章节结构（唯一准则），为后续 highlights/mindmap/keyframes/跳转打地基（主要 Backend=services/core）。

### Story 5.1: [BE/core] Worker 队列与并发控制（MAX_CONCURRENT_JOBS=2）

As a 维护者,
I want 后端以应用层队列执行 Job 并限制并发,
So that 在单机环境下稳定运行且可恢复。

**Acceptance Criteria:**

**Given** 多个 Job 被创建为 queued
**When** worker loop 运行
**Then** 同时最多处理 `MAX_CONCURRENT_JOBS` 个 running Job（默认 2）
**And** Job claim 机制避免重复消费（DB-backed best-effort）

**Given** 服务重启
**When** worker loop 恢复
**Then** queued/running/failed/succeeded 状态可被重新读取并继续展示（至少可查询，不丢失）

### Story 5.2: [BE/core] 转写 stage（transcribe）产出 transcript

As a 用户,
I want 系统对视频执行转写并产出带时间戳的 transcript,
So that 后续可以进行章节切片与重点提炼。

**Acceptance Criteria:**

**Given** Job 进入 transcribe stage
**When** 转写成功
**Then** transcript 被持久化（DB 或文件 + DB 引用）且时间戳单位为 ms
**And** stage/progress 通过状态接口与 SSE 事件可观察

**Given** 转写失败（依赖/模型/资源不足/内容异常）
**When** 任务处理失败
**Then** Job 进入 failed 且 error envelope code 可归因并带可行动建议

### Story 5.3: [BE/core] 章节切片 stage（segment）产出 Chapters

As a 用户,
I want 系统基于 transcript 生成章节列表,
So that 章节成为 UI 跳转与所有产物的唯一准则。

**Acceptance Criteria:**

**Given** transcript 已存在
**When** segment 成功
**Then** 生成 Chapters 列表（包含 `chapterId`, `startMs`, `endMs`, `title`, `summary`）并持久化
**And** 保证 `startMs < endMs` 且章节顺序稳定（idx 或按 startMs 排序）

### Story 5.4: [BE/core] Stage 命名与进度映射对齐（api.md）

As a 前端开发者,
I want 后端 stage 命名与进度事件稳定一致,
So that 前端无需猜测流程即可正确展示。

**Acceptance Criteria:**

**Given** Job 运行经历 ingest/transcribe/segment/... 等阶段
**When** 我观察 `GET /api/v1/jobs/{jobId}` 与 SSE `progress` 事件
**Then** `stage` 字段只使用已约定的稳定名称集合
**And** `progress` 在 0..1 范围内（可为空但不可越界）

## Epic 6: 每章重点与关键帧产出（Highlights + Keyframes）

用户可以获得每章重点与关键帧，并能追溯到章节与时间点（主要 Backend=services/core）。

### Story 6.1: [BE/core] 关键帧抽取与 assets 持久化

As a 用户,
I want 系统为每章生成关键帧截图并可关联到时间点,
So that 我能用视觉锚点快速回忆上下文。

**Acceptance Criteria:**

**Given** Chapters 已生成
**When** 执行 extract_keyframes
**Then** 关键帧图片被生成并存储在 `DATA_DIR` 下受控目录
**And** DB 中为每个 keyframe 创建 asset 记录（仅相对路径）并关联 `projectId`/`chapterId`/可选 `timeMs`

**Given** ffmpeg 不可用
**When** 关键帧抽取执行
**Then** Job 失败并返回可归因错误 code（可与 health 结果一致）

### Story 6.2: [BE/core] 每章重点摘要（highlights）生成与持久化

As a 用户,
I want 每章都有可复习的重点摘要,
So that 我能快速定位需要复听的部分。

**Acceptance Criteria:**

**Given** Chapters 已生成
**When** 执行 analyze（highlights）
**Then** 为每章生成 highlights 列表并持久化，且每条 highlight 可关联 `chapterId` 或 `timeMs`
**And** 失败时返回结构化错误并提供建议动作（例如检查模型配置/降低并发/缩短视频）

## Epic 7: 思维导图产出（Mindmap）

用户可以获得基于章节的思维导图 graph（主要 Backend=services/core）。

### Story 7.1: [BE/core] Mindmap schema 定义与生成（nodes/edges）

As a 用户,
I want 系统生成可视化的思维导图,
So that 我能以结构化方式理解视频内容。

**Acceptance Criteria:**

**Given** Chapters 已生成
**When** 执行 analyze（mindmap）
**Then** 生成 mindmap graph（nodes/edges）并持久化到 Result 或关联表
**And** 节点必须可追溯到 `chapterId`（至少 root/章节点具备关联）

## Epic 8: 结果汇总与复习体验（Results & Review）

用户可以在结果页完成“章节跳转/看重点/看关键帧/看导图”的核心复习闭环，并安全访问 assets（可并行：Backend=services/core，Frontend=apps/web）。

### Story 8.1: [Contract] 固化 Result/Assets 读取契约（补全 api.md 并锁定字段）

As a 开发团队,
I want 在 api.md 中把 Result 与 Assets 的读取接口写成可复制的契约,
So that 前后端/多 agent 并行实现不会漂移。

**Acceptance Criteria:**

**Given** 当前 api.md 仅有部分接口与表结构草案
**When** 我补全 Result 与 Assets 的读取接口（路径、请求参数、响应 schema 与示例）
**Then** api.md 明确“获取项目最新 Result”的 endpoint 与响应字段（包含 chapters/highlights/mindmap/note/asset refs）
**And** api.md 明确 assets 的 metadata 与 content endpoint（与架构约束一致：project scope + safe path）

### Story 8.2: [BE/core] Assets API：metadata + content（安全路径 + 可选 Range）

As a 用户,
I want 前端能通过受控接口获取关键帧图片内容,
So that 不暴露绝对路径且避免目录穿越。

**Acceptance Criteria:**

**Given** assetId 存在且属于 projectId
**When** 我请求 assets content endpoint
**Then** 服务返回正确的图片内容流
**And** 文件解析必须通过单一 safe-join 工具限制在 `DATA_DIR` 内

**Given** assetId 不属于 projectId 或路径越界
**When** 我请求 content
**Then** 返回统一错误 envelope（不泄露路径）

### Story 8.3: [BE/core] Result 汇总落库与读取（latest Result 可渲染）

As a 用户,
I want 分析完成后能读取项目最新结果,
So that 刷新/重启后仍能直接渲染复习页面。

**Acceptance Criteria:**

**Given** pipeline 已生成 chapters/highlights/mindmap/keyframes
**When** assemble_result 执行成功
**Then** 将 Result 落库并更新 `projects.latest_result_id`
**And** 通过“获取最新 Result”接口可一次性拿到渲染所需数据（或最小必要引用）

### Story 8.4: [FE/web] 结果页三栏布局（Tri-Pane Focus）与基础渲染

As a 用户,
I want 在结果页同时看到视频与笔记/导图,
So that 我能边看边整理并快速复习。

**Acceptance Criteria:**

**Given** 我打开项目结果页
**When** latest Result 可用
**Then** 页面以 Tri-Pane Focus 布局渲染：左侧视频/导图区域，右侧笔记区域
**And** 章节列表、重点、关键帧、导图至少有一种可见入口（tabs 或分区）

### Story 8.5: [FE/web] 智能悬浮播放器（Intersection Observer）

As a 用户,
I want 当我滚动到笔记/导图区时视频自动悬浮,
So that 我不会丢失上下文。

**Acceptance Criteria:**

**Given** 主播放器滚出视口顶部
**When** Intersection Observer 触发
**Then** 播放器进入悬浮态（右下角、固定尺寸 16:9、带最小控制）
**And** 点击 Expand 可平滑滚动回顶部并恢复原位

### Story 8.6: [FE/web] 章节跳转播放 + 关键帧跳转

As a 用户,
I want 点击章节或关键帧即可跳转到对应时间播放,
So that 复习不再依赖拖进度条。

**Acceptance Criteria:**

**Given** chapters 列表存在 startMs/endMs
**When** 我点击某章节
**Then** 播放器跳转到该章节的 startMs 并开始/继续播放（按产品默认）

**Given** 关键帧 asset 关联 timeMs
**When** 我点击某关键帧
**Then** 播放器跳转到对应 timeMs

## Epic 9: 编辑与持久化（Notes / Mindmap / Chapters / Keyframe Binding）

用户可以编辑笔记/导图/章节并保存，刷新/重启后仍可恢复编辑态（可并行：Backend=services/core，Frontend=apps/web）。

### Story 9.1: [BE/core] 笔记保存 API（覆盖式更新 + updatedAtMs）

As a 用户,
I want 编辑笔记后可以保存并在下次打开时恢复,
So that 我的复习提纲不会丢。

**Acceptance Criteria:**

**Given** 我提交笔记保存请求（tiptap JSON）
**When** 保存成功
**Then** 服务覆盖更新当前 result 的 note 字段并返回 updatedAtMs（或等价字段）
**And** 请求/响应不包含敏感信息或绝对路径

### Story 9.2: [FE/web] TipTap 编辑器集成与自动保存（debounce + flush）

As a 用户,
I want 在结果页编辑笔记并自动保存,
So that 我能流畅整理知识卡片。

**Acceptance Criteria:**

**Given** 我在编辑器中输入
**When** 我停止输入超过 800–1500ms
**Then** 前端自动触发保存并显示“保存中/已保存/保存失败”状态

**Given** 我关闭页面或切换路由
**When** 有未提交的变更
**Then** 前端会 flush 一次保存（best-effort）

### Story 9.3: [BE/core] 思维导图保存 API（nodes/edges 覆盖式更新）

As a 用户,
I want 编辑思维导图并保存,
So that 我能把自己的理解补充进去。

**Acceptance Criteria:**

**Given** 我提交 mindmap 保存请求（nodes/edges）
**When** 保存成功
**Then** 服务覆盖更新当前 result 的 mindmap graph 并返回 updatedAtMs（或等价字段）

### Story 9.4: [FE/web] React Flow 编辑器集成与自动保存

As a 用户,
I want 在导图画布上增删改节点/连线并自动保存,
So that 我能持续完善知识结构。

**Acceptance Criteria:**

**Given** 我编辑节点或连线
**When** 变更发生
**Then** 前端以 debounce 方式保存，并在失败时提示并允许重试

### Story 9.5: [BE/core] 章节编辑 API（保证章节唯一准则一致性）

As a 用户,
I want 编辑章节标题（可选时间范围/顺序）,
So that 章节更贴合我的复习习惯且不破坏跳转。

**Acceptance Criteria:**

**Given** 我仅修改章节标题
**When** 保存成功
**Then** 不影响章节 start/end 与已有产物引用关系（chapterId 稳定）

**Given** 我修改章节时间范围（若允许）
**When** 保存成功
**Then** 系统保持章节序与不重叠规则（或给出可理解错误），并确保跳转逻辑仍成立

### Story 9.6: [BE/core] 关键帧/图片关联更新 API（绑定/替换/排序）

As a 用户,
I want 调整关键帧与章节/笔记模块的关联关系,
So that 我能把最有用的画面固定在对应章节。

**Acceptance Criteria:**

**Given** 我提交关键帧绑定更新请求
**When** 请求合法
**Then** 服务更新关联关系并在下次读取 Result 时可见
**And** 不能把 asset 绑定到不属于该项目的章节

## Epic 10: 搜索与模型设置（MVP 轻量）

用户可以轻量搜索定位项目/章节；高级用户可以配置模型提供方并获得可理解的校验与错误提示（可并行：Backend=services/core，Frontend=apps/web）。

### Story 10.1: [BE/core] 搜索 API（MVP：title/summary/派生文本）

As a 用户,
I want 用关键词搜索项目/笔记摘要,
So that 我能快速找到需要复习的内容。

**Acceptance Criteria:**

**Given** 我请求搜索接口并提供 query
**When** 有匹配结果
**Then** 返回 `{ items, nextCursor }` 且 items 至少包含 `projectId`（可选包含 `chapterId`）以便定位

### Story 10.2: [FE/web] 搜索 UI（输入、结果列表、定位跳转）

As a 用户,
I want 在 UI 中搜索并跳转到对应项目/章节,
So that 我能用“检索”替代翻找。

**Acceptance Criteria:**

**Given** 我输入关键词并提交
**When** 返回结果
**Then** 我能点击结果打开对应项目（或定位到章节）

### Story 10.3: [BE/core] 模型/Provider 设置读取与校验（非敏感）

As a 运维/高级用户,
I want 配置 provider/baseUrl/model 等参数并在无效时得到明确提示,
So that 分析失败可归因且可行动。

**Acceptance Criteria:**

**Given** 我读取设置
**When** 服务返回设置
**Then** 仅返回非敏感字段（不返回/不落盘 API key）

**Given** 配置无效
**When** 我发起分析
**Then** 系统要么阻止启动并返回可理解错误，要么在失败时归因明确（error code + message）

### Story 10.4: [FE/web] 设置页（provider/model 参数 + 可理解提示）

As a 运维/高级用户,
I want 在 Web 端配置模型提供方与参数,
So that 我能在不同环境下跑通分析。

**Acceptance Criteria:**

**Given** 我填写 provider/baseUrl/model 等参数
**When** 保存成功
**Then** 我能看到立即生效的提示，并能通过健康检查或下一次 job 失败信息进行验证
