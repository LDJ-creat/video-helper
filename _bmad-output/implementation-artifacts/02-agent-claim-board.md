# video-helper — Agent 领取表（语义化命名）& 推荐并行启动顺序

本文件把 [01-worktree-branch-assignment.md](01-worktree-branch-assignment.md) 的 worktree/branch 计划落到“谁来做什么 + 先做什么”。

原则（简版）：
- **契约/枚举/DTO/错误码/阶段映射**只能由一个 owner 推进（WT-00），否则一定漂移。
- 其它 worktree 按“模块聚合 2–4 个紧密 story”并行。
- 启动顺序以“最小可用闭环（可见性/导入/项目）”优先，其它能力可后补。

技术决策（补充）：
- **ASR（transcribe）实现选型：faster-whisper（本地）**。Phase 4/早期允许 placeholder 先跑通闭环；进入“真实视频分析闭环”前，需把 5-2 的转写 provider 切换为 faster-whisper，并保留 placeholder 作为降级路径。
- **音频前处理：ffmpeg**。从视频抽取/重采样音频（如 16kHz mono PCM）后送入 ASR；转写产出必须带 ms 时间戳，作为 chapters/highlights/mindmap 的唯一对齐基准。

---

## 1) Agent 角色定义（语义化命名）

- **Contract Steward（契约管理员）**：冻结 contracts、stage 映射、错误码注册表、核心 DTO。
- **Platform/DB Owner（平台与数据基座）**：FastAPI 骨架、中间件、DB schema/Alembic、基础存储与路径安全。
- **Jobs Observability Owner（作业可观测性）**：Job 查询/SSE/日志 tail/取消重试；保障“跑起来且看得见”。
- **Pipeline Owner（流水线执行）**：worker/queue + transcribe/segment/analyze stages 的执行闭环。
- **Results & Assets Owner（结果与资源）**：assets API + result assemble；对接前端 results。
- **Web App Shell Owner（Web 外壳与路由）**：Next.js 工程骨架、布局、状态管理与通用组件规范。
- **Web Jobs UI Owner（Web 作业体验）**：ingest 页面、job 详情页、SSE/fallback 体验。
- **Web Projects/Results UI Owner（Web 资产与结果体验）**：projects 列表/详情/删除，results 页面 + 悬浮播放器 + 跳转。
- **Editing UX Owner（编辑体验）**：TipTap/ReactFlow 编辑与 autosave。
- **Search/Settings Owner（搜索/设置）**：search + settings 前后端闭环。

> 实际上一个人可以兼任多个角色；但 **Contract Steward 必须单 owner**。

---

## 2) 领取表（按 worktree/branch）

### WT-00（必须单 owner）：契约冻结
- **Agent**：Contract Steward
- **Branch**：`feat/contract/freeze-contracts`
- **Stories**：
  - 8-1-contract-result-assets-api
  - 5-4-be-core-stage-mapping
  -（同一 worktree 内）错误码注册表 + 基础 DTO/响应 envelope 约束
- **交付门槛（Done）**：
  - stage 稳定集合与对外映射写死（含 SSE/state/progress 语义）
  - error codes 注册表可被 BE/FE 引用（至少含 00-standards 列表）
  - Result/Assets/Jobs/Projects 核心字段 camelCase 明确（示例 payload）

### WT-BE-01：health + diagnostics
- **Agent**：Platform/DB Owner
- **Branch**：`feat/be/health-and-diagnostics`
- **Stories**：1-1-be-core-health-check
- **依赖**：WT-00（错误码/health schema 冻结）

### WT-BE-02：projects（list/detail/delete）
- **Agent**：Platform/DB Owner
- **Branch**：`feat/be/projects-core`
- **Stories**：2-1-be-core-project-list-detail、2-3-be-core-delete-project
- **依赖**：WT-00（分页/DTO/错误码）

### WT-BE-03：jobs ingest（create job + upload + metadata）
- **Agent**：Pipeline Owner（或 Jobs Observability Owner 兼任）
- **Branch**：`feat/be/jobs-ingest`
- **Stories**：3-1-be-core-create-job-url、3-2-be-core-create-job-upload、3-4-be-core-video-metadata
- **依赖**：WT-00（DTO/路径安全规则）

### WT-BE-04：jobs visibility（poll + sse + logs + cancel/retry）
- **Agent**：Jobs Observability Owner
- **Branch**：`feat/be/jobs-visibility`
- **Stories**：4-1-be-core-job-get、4-2-be-core-job-sse、4-4-be-core-job-logs-tail、4-6-be-core-job-cancel-retry
- **依赖**：WT-00（SSE schema/stage/错误码）

### WT-BE-05：worker/queue + pipeline 基座
- **Agent**：Pipeline Owner
- **Branch**：`feat/be/worker-queue`
- **Stories**：5-1-be-core-worker-queue
- **依赖**：WT-00（状态机/stage 约束）

### WT-BE-06：transcribe + segment
- **Agent**：Pipeline Owner
- **Branch**：`feat/be/pipeline-transcribe-segment`
- **Stories**：5-2-be-core-transcribe、5-3-be-core-segment-chapters
- **依赖**：WT-BE-05（worker）、WT-00（stage/错误码）
- **实现约束（补充）**：
  - 5-2（transcribe）优先落地 faster-whisper 本地 ASR：从 `projects.source_path` 或 URL 下载产物中定位媒体文件，使用 ffmpeg 解码/重采样后转写。
  - transcript 需输出分段 + `startMs/endMs`（ms）并持久化（DB 或文件 + DB 引用）；失败需可归因（依赖缺失/模型缺失/资源不足/内容异常）。
  - 保留 placeholder provider 作为 dev/CI 降级（无模型/无依赖时仍可跑通阶段与可观测性）。

### WT-BE-07：analyze artifacts（highlights/mindmap/keyframes）
- **Agent**：Pipeline Owner（可拆给 Results & Assets Owner）
- **Branch**：`feat/be/pipeline-artifacts`
- **Stories（MVP baseline）**：6-1-be-core-keyframes、6-2-be-core-highlights、7-1-be-core-mindmap
- **Stories（真实 LLM analyze，保持契约不变）**：6-3-be-core-analyze-llm-provider、6-4-be-core-highlights-llm、7-2-be-core-mindmap-llm
- **依赖**：WT-BE-06（chapters）、WT-BE-05（worker）、WT-00（stage/错误码）

### WT-BE-08：results + assets api + editing apis
- **Agent**：Results & Assets Owner
- **Branch**：`feat/be/results-assets-editing`
- **Stories**：8-2-be-core-assets-api、8-3-be-core-result-assemble、9-1-be-core-note-save、9-3-be-core-mindmap-save、9-5-be-core-chapter-edit、9-6-be-core-asset-binding
- **依赖**：WT-00（8.1 契约必须先合）、WT-BE-07（产物）

### WT-BE-09：search + settings
- **Agent**：Search/Settings Owner
- **Branch**：`feat/be/search-settings`
- **Stories**：10-1-be-core-search、10-3-be-core-settings-validate
- **依赖**：WT-00（错误码/分页）

---

### WT-FE-01：health + ingest
- **Agent**：Web Jobs UI Owner（或 Web App Shell Owner 兼任）
- **Branch**：`feat/fe/health-and-ingest`
- **Stories**：1-2-fe-web-health-banner、3-3-fe-web-ingest-page
- **依赖**：WT-00（health/ingest 契约冻结；可先 mock）

### WT-FE-02：projects
- **Agent**：Web Projects/Results UI Owner
- **Branch**：`feat/fe/projects-ui`
- **Stories**：2-2-fe-web-project-pages、2-4-fe-web-delete-project-ui
- **依赖**：WT-00（projects DTO/分页/错误 envelope；可先 mock）

### WT-FE-03：jobs（详情页 + SSE/fallback）
- **Agent**：Web Jobs UI Owner
- **Branch**：`feat/fe/jobs-ui`
- **Stories**：4-3-fe-web-sse-fallback、4-5-fe-web-job-page
- **依赖**：WT-00（SSE schema/stage；可先 mock）

### WT-FE-04：results（结果页 + 跳转 + 悬浮播放器）
- **Agent**：Web Projects/Results UI Owner
- **Branch**：`feat/fe/results-ui`
- **Stories**：8-4-fe-web-results-page、8-5-fe-web-floating-player、8-6-fe-web-seek-chapter-keyframe
- **依赖**：WT-00（8.1 契约先合；可先 mock 后接入）

### WT-FE-05：editing（笔记/导图自动保存）
- **Agent**：Editing UX Owner
- **Branch**：`feat/fe/editing-ui`
- **Stories**：9-2-fe-web-tiptap-autosave、9-4-fe-web-reactflow-autosave
- **依赖**：WT-00（保存 API 契约；可先本地持久化 mock）

### WT-FE-06：search + settings
- **Agent**：Search/Settings Owner（或 Web App Shell Owner 兼任）
- **Branch**：`feat/fe/search-settings-ui`
- **Stories**：10-2-fe-web-search-ui、10-4-fe-web-settings-page
- **依赖**：WT-00（契约/错误码；可先 mock）

---

## 3) 推荐并行启动顺序（可直接照做）

### Phase 0（Day 0）：冻结“变更门”
1) **Contract Steward** 启动 WT-00：先把 8.1 + 5.4 + error codes/DTO 冻结并合入主分支
2) 同步在 [00-standards-and-parallel-plan.md](00-standards-and-parallel-plan.md) 标记“冻结完成”的版本点（可写一个日期/小版本号）

> 目标：其它所有 worktree 从这一点开始再并行，避免返工。

### Phase 1（Day 1）：可见性闭环优先（先让系统“可运行且可观测”）
并行启动：
- **Jobs Observability Owner**：WT-BE-04（job get + sse + logs + cancel/retry）
- **Web Jobs UI Owner**：WT-FE-03（job page + SSE/fallback；先 mock，再接 BE）
- **Platform/DB Owner**：WT-BE-01（health），用于 smoke test/依赖诊断

合并顺序建议：BE-01 → BE-04 → FE-03（或 FE-03 并行，但接入等 BE-04）

### Phase 2（Day 1~2）：导入闭环（产生 job）
并行启动：
- **Pipeline Owner**：WT-BE-03（ingest create/upload/metadata）
- **Web Jobs UI Owner**：WT-FE-01（ingest page）

> 目标：能创建 job，并在 job page 看到 ingest 进度。

### Phase 3（Day 2）：项目闭环（管理 project）
并行启动：
- **Platform/DB Owner**：WT-BE-02（projects list/detail/delete）
- **Web Projects/Results UI Owner**：WT-FE-02（projects UI）

### Phase 4（Day 2~3）：最小流水线闭环（能产出结果）
并行启动：
- **Pipeline Owner**：WT-BE-05（worker/queue）→ WT-BE-06（transcribe/segment）
- **Results & Assets Owner**：WT-BE-08（assets api + assemble_result 的最小实现）
- **Web Projects/Results UI Owner**：WT-FE-04（results UI，先 mock）

注：Phase 4 的“可跑通闭环”允许 transcribe/segment 使用 placeholder；但若要进入“真实视频分析闭环”，需在 Phase 4→5 的过渡中完成 faster-whisper ASR 接入与产物对齐。

合并顺序建议：BE-05 → BE-06 → BE-08 → FE-04

### Phase 5（Day 3+）：体验增强与编辑持久化
- **Pipeline Owner**：WT-BE-07（keyframes/highlights/mindmap）
- **Editing UX Owner**：WT-FE-05（tiptap/reactflow autosave）
- **Results & Assets Owner**：补齐编辑类 API（WT-BE-08 内已包含 9.x BE）

### Phase 5.5（Day 3+）：真实 LLM 分析闭环（可选但推荐）
- **Pipeline Owner**：WT-BE-07（6-3 provider + 6-4 highlights LLM + 7-2 mindmap LLM；无 Key 时允许 rules fallback）

### Phase 6（尾段）：搜索/设置
- **Search/Settings Owner**：WT-BE-09 + WT-FE-06

---

## 4) 领取执行小提示（减少冲突）

- 所有人在开工前先从主分支 `git pull` 到“WT-00 已合入”的基线点。
- 任何人发现契约需要调整：先提到 WT-00 的 PR/issue，**不要在自己的 worktree 私自改 contracts**。
- FE 允许先 mock，但必须对齐 WT-00 的字段/错误 envelope/SSE schema。
