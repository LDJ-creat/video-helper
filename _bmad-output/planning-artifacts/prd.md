---
stepsCompleted:
  - step-01-init
  - step-02-discovery
  - step-03-success
  - step-04-journeys
  - step-05-domain
  - step-06-innovation
  - step-07-project-type
  - step-08-scoping
  - step-09-functional
  - step-10-nonfunctional
  - step-11-polish
  - step-12-complete
inputDocuments:
  - develop_design.md
  - api.md
documentCounts:
  briefCount: 0
  researchCount: 0
  brainstormingCount: 0
  projectDocsCount: 2
classification:
  projectType: web_app
  domain: general
  complexity: low
  projectContext: greenfield
workflowType: 'prd'
---

# Product Requirements Document - video-helper

**Author:** LDJ
**Date:** 2026-01-28

## Executive Summary

- **目标用户**：备考/进修/网课学习者（高频需求：章节跳转、抓重点、看关键帧回忆上下文）。
- **核心问题**：长视频复习成本高，用户被迫反复拖进度条，难以快速定位“关键内容”。
- **核心价值**：把单个视频变成“可复习资产”：章节结构（唯一准则）+ 每章重点 + 关键帧 + 可编辑笔记与思维导图。
- **差异化与一致性约束**：Chapters 是唯一准则；思维导图/重点/关键帧必须可追溯到 `chapter_id` 或 `time_ms`。
- **MVP 形态**：Web/Docker 优先；必须支持 Web 端上传文件与外链导入（YouTube/B 站）。
- **成功门槛**：10–30 分钟视频端到端 ≤10 分钟；Completion Rate ≥80%；WAU（3 个月）≥200；失败可归因且可行动（依赖/Key/网络/受限/资源不足）。

## Success Criteria

### User Success

- 用户在 **≤10 分钟**内完成一次闭环：导入 → 分析完成 → 结果可渲染且可编辑。
- MVP 最低保证视频规模：**10–30 分钟**视频可稳定完成全流程。
- “Aha 时刻”：用户在结果页通过“每章重点 + 关键帧”快速定位关键内容，并一键跳转到对应时间段。
- 编辑闭环：笔记与思维导图修改后可保存；再次打开仍可恢复并继续编辑。

### Business Success

- 3 个月目标（开源/获客导向）：
  - **WAU ≥ 200**（参考：≥50 可视为“存活”，≥500 可视为“起势”）。
  - **Completion Rate ≥ 80%**（完成一次分析闭环的占比）。

### Technical & Quality Gates

- 可恢复性：刷新/重启后仍可查询 Job 状态并读取最终 Result；失败后可重试（进行中断点续跑非 MVP 硬要求）。
- 失败可理解且可行动（MVP 必覆盖）：链接受限/需要登录、依赖缺失（如 FFmpeg）、网络/下载失败、模型/Key 不可用、转写/切片失败（资源不足/内容异常）。
- 一致性：Chapters 为唯一准则；导图/重点/关键帧可回溯到 `chapter_id` 或 `time_ms`。
- 部署形态：Web/Docker 必须支持服务端上传分析（不依赖客户端本地路径）。
- 可测量门槛（MVP）：10–30 分钟视频端到端 **≤10 分钟**；结果页可仅凭 Result 数据独立渲染与恢复编辑态。

## Product Scope

### MVP - Minimum Viable Product

- 导入：支持 **本地视频上传** + 外部链接（YouTube、B 站）。
- Job：创建分析任务、查询状态（轮询降级）、SSE 进度推送（含 stage/progress/错误）。
- 分析流水线：导入/预处理 → 转写 → 章节切片（唯一准则）→ 两子流程并发产物（mindmap + highlights/keyframes）→ 汇总 Result 落库。
- 产物渲染：章节列表 + 思维导图 + 重点摘要 + 关键帧（可跳转到对应时间段）。
- 编辑与持久化：笔记（富文本）与思维导图可编辑保存；多项目列表/打开最新结果；离线可浏览历史结果。

### Growth Features (Post-MVP)

- 桌面端（Tauri sidecar）一键启动/本地能力增强。
- 进行中 Job 断点续跑、更强的任务恢复与重试策略。
- 更强搜索（FTS5/向量检索、章节级检索）。
- 导出形态（PDF/Notion/Markdown 等）。

### Vision (Future)

- 云同步/账号体系、多端协作。
- 更完整的 RAG/知识库、跨项目检索与引用。
- 插件化提供方/模型策略（本地/云端灵活切换、成本与质量控制）。

## User Journeys

### Journey 1: 主用户（备考/进修）- 外链导入到可复习的“章节 + 重点 + 关键帧”

**Opening Scene**

小周是备考学生/职场进修者，日常主要通过 B 站/YouTube 看网课。她最痛苦的是：视频太长、重点分散，复习时要反复拖进度条，效率很低。

**Rising Action**

她打开 Web 页面，新建一个项目，把课程链接粘贴进去并发起分析。页面显示 Job 进度与阶段（例如导入/转写/切片/产物生成）。在等待过程中，她能看到清晰的状态变化与耗时预期，不需要猜测“是不是卡住了”。

**Climax**

分析完成后进入结果页：

- 章节列表出现，点击任一章节即可跳转到该时间段播放。
- 每章“重点 + 关键帧”卡片让她快速锁定该章核心内容，关键帧帮助她用视觉锚点回忆讲解上下文。

她第一次感到“复习终于不是在刷进度条”。

**Resolution**

她把每章重点整理成自己的复习提纲/知识卡片（笔记编辑），并在思维导图里补充自己的理解。保存后，下次打开项目，编辑内容与产物仍可稳定恢复。

---

### Journey 2: 主用户（备考/进修）- Web 端上传本地视频并完成闭环

**Opening Scene**

小林在校园网盘里有一份录屏课程，本地文件观看方便，但复习很难定位重点。

**Rising Action**

他在 Web 端通过上传控件选择本地视频并创建项目（避免依赖本地路径作为“真相”）。上传完成后启动分析，系统持续展示进度并允许断线后通过轮询恢复查看。

**Climax**

结果页出现章节结构与重点摘要，他主要使用 3 个操作：点击章节跳转、查看重点、查看关键帧。重点内容帮助他快速识别哪些部分要反复听，关键帧帮助他回忆当时板书/讲义画面。

**Resolution**

他把重点摘要改写为“知识卡片”，并保存。下一次复习时，他直接打开项目，跳到对应章节进行快速回顾。

---

### Journey 3: 主用户（边界/失败恢复）- 切片/转写失败（E）时仍可完成可理解的恢复路径

**Opening Scene**

用户提交视频分析后，在“转写/切片”阶段失败。用户最担心的是：是不是视频不支持？我该怎么办？我的上传白费了吗？

**Rising Action**

系统在 Job 详情中给出可理解的错误分类与建议行动：

- 如果是资源不足：提示降低并发/切换模型/缩短视频/先截取片段重试。
- 如果是模型/Key：提示去“设置”检查提供方与 Key。
- 如果是网络/下载：提示稍后重试并保留失败日志与重试入口。

同时，前端在 SSE 中断时自动降级为轮询，避免用户误判“页面坏了”。

**Climax**

用户点击“重试”或“重新分析”（可选择复用已有项目与资源），看到进度重新推进。失败不再是死胡同。

**Resolution**

用户最终获得章节、重点与关键帧，并继续编辑保存；即使失败过，项目仍能被再次打开并看到失败原因与历史记录。

---

### Journey 4: 管理/运维/排障用户（通常是作者本人）- 配置模型、排查失败与稳定交付

**Opening Scene**

作为维护者/高级用户，你需要让系统“在别人的电脑上也能跑”。你最关心的是：依赖是否齐、Key 是否有效、失败能否快速定位。

**Rising Action**

你打开设置页配置模型提供方与 Key，并通过健康检查/自检确认基础依赖可用。你能查看项目与 Job 列表，定位失败的 Job，并阅读结构化错误详情（error_code/error_message/error_details）。

**Climax**

当用户反馈“分析失败”，你能快速归因到链接受限/依赖缺失/网络波动/Key 错误/资源不足等类别，并给出可行动的解决路径。

**Resolution**

你通过改进错误提示与默认配置，把“第一次跑起来”成本降到最低；并通过稳定的持久化与可恢复机制，保证用户刷新/重启后仍能找回结果与状态。

### Journey Requirements Summary

- 项目与导入：创建项目；外链导入（YouTube/B 站）；Web 端本地视频上传。
- Job 体验：阶段化 stage + progress；SSE 推送与心跳；SSE 失败自动降级轮询；Job 详情页（日志/错误详情/重试）。
- 结果页核心动作：章节列表与跳转播放；每章重点摘要；关键帧卡片；三者基于同一章节切片（唯一准则）。
- 编辑与持久化：笔记（知识卡片/提纲）编辑保存；思维导图编辑保存；历史项目可再次打开。
- 失败恢复：覆盖 5 类错误；针对不同错误提供具体建议动作；可重试与可重复分析。
- 设置与运维：模型提供方与 Key 配置入口；健康检查/依赖自检；可查看任务失败原因并快速归因。

## Web App Specific Requirements

### Project-Type Overview

- 产品形态：以 Web/Docker 形态为第一版验收标准，定位为开源工具（可公开访问/可自部署）。
- 前端交互模式：以 **SPA 体验**为主（分析任务、结果渲染、编辑为核心交互场景）。
- 实时性边界：只要求 **Job 进度与阶段**实时（SSE + 心跳 + 断线降级轮询），不包含多人协作实时编辑。

### Technical Architecture Considerations

- 前端：Next.js（应用型交互为主），编辑器（TipTap）与思维导图（React Flow）属于状态复杂区域，需要明确“保存即真相”的数据流。
- 后端：FastAPI 提供项目/任务/结果/编辑/资源等 API，并承担上传文件接收与落盘（DATA_DIR）能力。
- 进度推送：SSE 为默认通道；当 SSE 不可用/断线时，前端必须无感降级为轮询，保证可恢复。
- 资源访问：关键帧/截图等 Asset 必须可通过受限的静态资源接口访问（路径需防目录穿越）。

### Browser Matrix

- MVP 支持：桌面端主流浏览器（Chrome/Edge/Safari/Firefox）最新两个大版本。
- 移动端：非 MVP 硬要求（可在后续迭代加入移动端适配与触控优化）。

### Responsive Design

- MVP：桌面端优先布局（章节列表/播放器/重点&关键帧/导图&笔记编辑器多区域布局）。
- 非 MVP：移动端与小屏布局优化（含侧栏折叠与触控手势）。

### Performance Targets

- 首次打开：在常见网络下可快速进入“创建项目/导入”主流程。
- 结果页渲染：章节/重点/关键帧应分页或虚拟列表，避免长视频导致一次性渲染卡顿。
- 编辑区：TipTap 与 React Flow 的状态更新应避免全量重渲染；保存操作需明确成功/失败反馈。

### SEO Strategy

- SEO 重要：作为开源工具，需要可被搜索引擎索引的公共页面（例如 landing/README/Docs）。
- 应用页（登录后/工具页）：SEO 不是重点，但需保证分享链接与基础 meta 信息可配置。

### Accessibility Level

- MVP：基础可用为准（键盘可操作关键按钮、足够对比度、可读性良好、表单/按钮具备语义与 aria 标签）。
- 非 MVP：对齐更高标准（例如 WCAG AA）可作为后续质量提升项。

### Implementation Considerations

- 上传：Web 端必须支持本地视频上传并在服务端持久化（避免把客户端本地路径作为唯一真相）。
- 跨域与部署：Docker 部署时前后端来源可能变化，CORS 与 API BaseURL 需要可配置。
- 健康检查：前端可通过 health 接口判断依赖（FFmpeg/yt-dlp/模型）是否就绪并给出可理解提示。

## Project Scoping & Phased Development

### MVP Strategy & Philosophy

**MVP Approach:** Platform MVP（先把后端流水线与数据契约做稳定，确保 Web/Docker 形态可自部署、可恢复、可迭代扩展到桌面端）。

**Resource Requirements:** 1 人（你）/ 4 周（时间盒）。

**策略含义（对范围的约束）：**

- 优先保证“端到端闭环 + 契约稳定 + 可恢复 + 可解释失败”。
- 产物范围维持“全都要”（章节 + 重点 + 关键帧 + 思维导图），但通过明确的阶段交付与质量门槛来控制复杂度（例如先实现可渲染的基础 mindmap，再做编辑与更复杂布局）。

### MVP Feature Set (Phase 1)

**Core User Journeys Supported:**

- 主用户外链导入（YouTube/B 站）→ 分析 → 章节跳转 → 看重点 → 看关键帧 → 保存编辑
- Web 端上传本地视频 → 分析 → 查看/编辑 → 下次可再打开
- 失败场景（转写/切片失败等）→ 可理解错误 → 可重试/可恢复
- 运维/高级用户：配置模型与 Key、查看 Job 失败原因、健康检查

**Must-Have Capabilities:**

- Project：创建/列表/详情/删除（latest_result 指针可用）。
- Ingest：外链导入（YouTube/B 站）+ Web 端本地视频上传。
- Job：长任务状态机（queued/running/succeeded/failed/canceled）、stage/progress、SSE 推送（含心跳）与轮询降级。
- Pipeline：导入/预处理 → 转写 → 章节切片（唯一准则）→ 两子流程并发（mindmap + highlights/keyframes）→ 汇总 Result 落库。
- Result：一次分析结果可独立渲染（章节/重点/关键帧/思维导图/笔记），并可在刷新/重启后恢复。
- Editing：笔记与思维导图可编辑保存；保存失败可提示并可重试。
- Assets：关键帧/截图可访问（路径安全），并能关联到 chapter/time。
- Error UX：覆盖 A/B/C/D/E 五类错误，并给出可行动建议。

### Post-MVP Features

**Phase 2 (Growth):**

- 桌面端（Tauri sidecar）一键启动与本地能力增强。
- 进行中 Job 断点续跑、更强的重试/回滚策略。
- 结果版本化（多 result 版本切换/回滚），更完善的编辑冲突处理。
- 搜索增强（FTS5/章节级索引/向量检索）。
- 移动端适配与触控优化。

**Phase 3 (Expansion):**

- 导出到 PDF/Notion/Markdown 等更多形态。
- 云同步/账号体系、多端协作。
- 更完整的 RAG/知识库与跨项目引用。

### Risk Mitigation Strategy

**Technical Risks:**

- 最高风险优先验证：**转写/切片质量与耗时**（目标：10–30 分钟视频端到端 ≤10 分钟）。
- 对策：尽早在真实课程样本上压测；将 stage/progress 与日志打通；允许配置模型与并发策略；失败可归因且可重试。

**Market Risks:**

- 假设验证：用户是否真的因为“章节+重点+关键帧”而显著提升复习效率。
- 对策：以开源用户反馈为主（Issue/Discord/问卷）；跟踪 WAU 与 Completion Rate，并收集定性反馈。



## Functional Requirements

### Project & Library

- FR1: 用户可以创建一个 Project 来承载单个视频的分析与笔记资产。
- FR2: 用户可以查看 Project 列表（支持分页/排序）。
- FR3: 用户可以查看 Project 详情（含来源、更新时间、latest_result 指针等）。
- FR4: 用户可以删除 Project，并同时删除其关联数据与资源。
- FR5: 系统可以为 Project 维护“最新可渲染结果”的引用关系（latest_result）。

### Video Ingest（外链/上传）

- FR6: 用户可以通过粘贴外链创建分析任务，外链来源至少支持 YouTube 与 B 站。
- FR7: 用户可以在 Web 端上传本地视频文件并创建分析任务。
- FR8: 系统可以校验导入输入的合法性（例如链接格式/文件类型等），并在不合法时返回可理解提示。
- FR9: 系统可以抽取并持久化视频的基础元信息（例如时长/格式）并关联到 Project。

### Jobs（长任务模型）

- FR10: 用户可以为一个 Project 创建分析 Job（类型：analyze_video）。
- FR11: 用户可以查询 Job 状态（queued/running/succeeded/failed/canceled）、stage、progress。
- FR12: 用户可以订阅 Job 的进度事件流（SSE），并接收阶段与进度更新。
- FR13: 当事件流不可用或断线时，客户端可以通过轮询继续获取 Job 状态并恢复展示。
- FR14: 用户可以取消正在运行的 Job（可选）。
- FR15: 当 Job 失败时，系统可以返回结构化错误信息（error_code/error_message/error_details）。
- FR16: 用户可以对失败的 Job 发起重试（在同一 Project 语境下再次分析）。

### Analysis Pipeline & Result Assembly

- FR17: 系统可以对导入视频执行转写，产出带时间戳的 transcript（对外是否暴露可选）。
- FR18: 系统可以基于转写结果进行章节切片，并生成 Chapters 列表（start_ms/end_ms/title/summary）。
- FR19: 系统将 Chapters 作为后续产物生成与 UI 跳转的唯一结构与时间准则。
- FR20: 系统可以并发生成思维导图产物（nodes/edges），并与 chapter_id 具备可追溯关联。
- FR21: 系统可以为每章生成重点摘要（highlights 列表），并可关联 time_ms 或 chapter_id。
- FR22: 系统可以为每章生成并持久化关键帧截图（assets），并可关联 chapter_id 与可选 time_ms。
- FR23: 系统可以将章节/导图/笔记/重点/关键帧汇总为一次 Result，并落库可回放渲染。
- FR24: 系统可以为 Result 记录轻量版本标识（schema_version/pipeline_version 类字段）。

### Results（读取与播放联动）

- FR25: 用户可以获取某 Project 的最新 Result。
- FR26: 用户可以在结果页查看章节列表，并基于章节进行时间跳转（start_ms/end_ms）。
- FR27: 用户可以在结果页查看每章重点摘要。
- FR28: 用户可以在结果页查看每章关键帧，并将关键帧作为视觉锚点辅助定位与复习。
- FR29: 用户可以在结果页查看思维导图（graph: nodes/edges）。
- FR30: 用户可以在结果页进行“章节跳转/看重点/看关键帧”的高频复习操作闭环。

### Chapter Editing（章节作为唯一准则的可编辑性）

- FR31: 用户可以编辑章节信息（至少包含章节标题；可选包含章节时间范围与章节顺序）。
- FR32: 系统在章节被用户编辑后，仍能保证“章节作为唯一准则”的一致性要求对外成立（例如章节跳转与章节索引不失效）。

### Editing（笔记/导图/资源关联）

- FR33: 用户可以编辑并保存笔记内容（富文本结构化数据）。
- FR34: 用户可以编辑并保存思维导图（节点/连线的增删改）。
- FR35: 用户可以更新关键帧/图片与章节或笔记模块的关联关系（绑定/替换/排序）。
- FR36: 保存后系统可以将用户编辑内容持久化，并在再次打开项目时恢复编辑态。

### Assets & Resource Access

- FR37: 系统可以管理项目资源（assets），并将资源与 Project/Chapter 关联。
- FR38: 系统可以提供资源访问接口以供前端渲染图片/截图。
- FR39: 系统在资源访问时应限制路径范围以防止目录穿越。

### Search（MVP 轻量）

- FR40: 用户可以基于关键词搜索项目/笔记内容（MVP 可先支持标题/摘要/派生文本）。
- FR41: 系统可以返回可定位到 Project/Chapter 的搜索结果（至少能打开到对应项目）。

### Model & Provider Settings（运维/高级用户）

- FR42: 运维/高级用户可以配置模型提供方与参数（provider/base_url/model 等）。
- FR43: 运维/高级用户可以配置 API Key 的使用方式（至少支持传入并在服务端使用；是否落盘由实现决定）。
- FR44: 系统可以在模型配置无效时给出可理解提示，并阻止启动分析或在失败时归因明确。

### Health & Diagnostics

- FR45: 客户端可以调用健康检查接口判断服务可用性与关键依赖就绪状态。
- FR46: 当分析失败时，用户可以看到可理解的失败原因分类与建议行动（与错误码体系一致）。

## Non-Functional Requirements

### Performance

- NFR1: Web 端关键交互的主观响应应流畅：常规操作（切换章节/展开卡片/保存按钮点击等）在常见设备上应达到约 **≤200ms** 的界面反馈（以“不明显卡顿”为准）。
- NFR2: 对 10–30 分钟视频，端到端分析完成时间目标 **≤10 分钟**（作为 MVP 目标，测试条件需可复现：模型配置、是否 GPU、并发设置）。
- NFR3: 结果页在长内容下应避免一次性渲染导致卡顿，列表型内容需要支持分段加载/虚拟化，保证滚动与交互可用。

### Reliability

- NFR4: Job 进度推送应默认通过 SSE 工作，并通过心跳降低“假断线”风险。
- NFR5: SSE 不可用或断线时，客户端必须自动降级为轮询，且用户仍能继续看到 job 的最新状态与错误信息。
- NFR6: 刷新/重启后，用户应能恢复到：
  - Project 列表与详情可读
  - Job 详情仍可查看阶段、错误详情、以及重试入口
  - Result 可重新渲染（不依赖前端内存状态）

### Security & Privacy

- NFR7: 默认本地优先：持久化数据与资源应存于本机 DATA_DIR 范围内，对外不暴露绝对路径。
- NFR8: 静态资源访问必须进行路径限制，防止目录穿越与任意文件读取。
- NFR9: API Key 不应以明文持久化到磁盘；同时日志与错误详情中不应泄露 Key 等敏感信息。

### Accessibility

- NFR10: MVP 达到基础可访问性：主流程支持键盘操作、按钮/表单具备语义与必要的 aria 标签、文本对比度与可读性满足基本可用。

### Deployment & Portability

- NFR11: 同时支持源码运行与 Docker 运行（Web/Docker 作为第一版验收标准），部署相关配置（API base url、CORS、DATA_DIR、模型配置）应可通过环境变量或配置文件进行调整。

### Scalability (Lightweight)

- NFR12: 自部署场景下默认支持 **同时 2 个 Job** 并发运行；当资源不足时，应以可理解错误或排队策略反馈，而不是无响应。

