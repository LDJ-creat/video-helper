# video-helper — worktree/branch 分派清单（并行开发指导）

目标：最大化并行、最小化冲突与 worktree 管理开销。

## 结论：不要“一个 Story 一个 worktree”作为默认

推荐策略：
1) **契约/共享文件**（contracts、错误码、stage 枚举、DTO）必须由“单 owner worktree”推进。
2) **按模块聚合 story**：一个 worktree 覆盖 2–4 个紧密耦合 story（同一层/同一子域），减少频繁创建新 worktree。
3) **合并顺序**：先合入“变更门”（8.1 + 5.4 + 错误码/DTO），再并行合入 BE/FE 各模块。

## A) 必须单 owner 的 worktree（共享标准/契约）

### WT-00：contract/standards（唯一 owner）
- Branch：`feat/contract/freeze-contracts`
- 建议包含 story：
  - 8-1-contract-result-assets-api
  - 5-4-be-core-stage-mapping（冻结 stage 集合与对外映射）
  -（同一 worktree 内）落地 error code 注册表与基础 DTO 约束
- 原因：这些改动会被所有模块引用，多个 agent 并发改必然冲突。

## B) 后端 worktree 分派（按子域聚合）

### WT-BE-01：diagnostics + health
- Branch：`feat/be/health-and-diagnostics`
- Stories：1-1-be-core-health-check
- 依赖：WT-00（错误码/基础响应约束）

### WT-BE-02：projects（list/detail/delete）
- Branch：`feat/be/projects-core`
- Stories：2-1-be-core-project-list-detail、2-3-be-core-delete-project
- 依赖：WT-00（DTO/错误码/分页契约）

### WT-BE-03：jobs ingest（create job + upload + metadata）
- Branch：`feat/be/jobs-ingest`
- Stories：3-1-be-core-create-job-url、3-2-be-core-create-job-upload、3-4-be-core-video-metadata
- 依赖：WT-00（DTO/错误码/路径安全规则）

### WT-BE-04：jobs visibility（poll + sse + logs + cancel/retry）
- Branch：`feat/be/jobs-visibility`
- Stories：4-1-be-core-job-get、4-2-be-core-job-sse、4-4-be-core-job-logs-tail、4-6-be-core-job-cancel-retry
- 依赖：WT-00（SSE schema/stage/错误码）；并行依赖 WT-BE-05（worker/queue）可后补

### WT-BE-05：worker/queue + pipeline 基座
- Branch：`feat/be/worker-queue`
- Stories：5-1-be-core-worker-queue
- 依赖：WT-00（状态机/stage 约束）

### WT-BE-06：transcribe + segment
- Branch：`feat/be/pipeline-transcribe-segment`
- Stories：5-2-be-core-transcribe、5-3-be-core-segment-chapters
- 依赖：WT-BE-05（worker）、WT-00（stage/错误码）

### WT-BE-07：analyze artifacts（highlights/mindmap/keyframes）
- Branch：`feat/be/pipeline-artifacts`
- Stories：6-1-be-core-keyframes、6-2-be-core-highlights、7-1-be-core-mindmap
- 依赖：WT-BE-06（chapters）、WT-BE-05（worker）、WT-00（stage/错误码）

### WT-BE-08：results + assets api + editing apis
- Branch：`feat/be/results-assets-editing`
- Stories：8-2-be-core-assets-api、8-3-be-core-result-assemble、9-1-be-core-note-save、9-3-be-core-mindmap-save、9-5-be-core-chapter-edit、9-6-be-core-asset-binding
- 依赖：WT-00（8.1 契约必须先合）、WT-BE-07（产物）

### WT-BE-09：search + settings
- Branch：`feat/be/search-settings`
- Stories：10-1-be-core-search、10-3-be-core-settings-validate
- 依赖：WT-00（错误码/分页）

## C) 前端 worktree 分派（按页面聚合）

### WT-FE-01：health + ingest
- Branch：`feat/fe/health-and-ingest`
- Stories：1-2-fe-web-health-banner、3-3-fe-web-ingest-page
- 依赖：WT-00（health/ingest 契约冻结）

### WT-FE-02：projects
- Branch：`feat/fe/projects-ui`
- Stories：2-2-fe-web-project-pages、2-4-fe-web-delete-project-ui
- 依赖：WT-00（projects DTO/分页/错误 envelope）

### WT-FE-03：jobs（详情页 + SSE/fallback）
- Branch：`feat/fe/jobs-ui`
- Stories：4-3-fe-web-sse-fallback、4-5-fe-web-job-page
- 依赖：WT-00（SSE schema/stage）

### WT-FE-04：results（结果页 + 跳转 + 悬浮播放器）
- Branch：`feat/fe/results-ui`
- Stories：8-4-fe-web-results-page、8-5-fe-web-floating-player、8-6-fe-web-seek-chapter-keyframe
- 依赖：WT-00（8.1 契约先合）；并行可先 mock，后接入真实 API

### WT-FE-05：editing（笔记/导图自动保存）
- Branch：`feat/fe/editing-ui`
- Stories：9-2-fe-web-tiptap-autosave、9-4-fe-web-reactflow-autosave
- 依赖：WT-00（保存 API 契约）

### WT-FE-06：search + settings
- Branch：`feat/fe/search-settings-ui`
- Stories：10-2-fe-web-search-ui、10-4-fe-web-settings-page
- 依赖：WT-00（契约/错误码）

## D) 什么时候“一个模块一个 worktree”更合适？

满足任一条件就建议拆成独立 worktree（避免冲突/阻塞）：
- 会修改共享 contracts/枚举/错误码（只允许 WT-00）
- 需要大范围重构（目录结构、公共组件、DB schema）
- 预计开发周期 > 2 天且会频繁 rebase

## E) 快速决策：一个 agent 能否做多个任务？

可以，且建议“一个 agent 负责一个 worktree 的 2–4 个紧密 story”。
优点：减少 worktree 开销、上下文连续、减少 PR 数量。
风险：scope 变大、review 成本上升。

折中建议：
- 默认：**一个 worktree = 一个模块/子域（2–4 story）**
- 只有在 story 极大/跨域/涉及共享契约时，才拆分到“一个 story 一个 worktree”。

参考：_bmad-output/implementation-artifacts/00-standards-and-parallel-plan.md
