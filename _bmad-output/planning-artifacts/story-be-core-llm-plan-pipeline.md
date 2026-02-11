# Story: BE-Core LLM-Plan 驱动的视频分析流水线改造（统一产物一致性）

## 背景 / 问题
当前流水线存在割裂：
- 章节切分主要是 rules（固定 3 段），见 `app/pipeline/segment.py`
- 关键帧时间点是章内等距采样，见 `app/pipeline/keyframes.py`
- highlights/mindmap 即使走 LLM，也依赖上游不准确的章节，导致整体一致性差

目标是引入一个 **LLM-plan（单一事实源）**：由同一次规划输出统一的 `chapters + contentBlocks + highlights + mindmapGraph + keyframeTimes`，后续阶段只负责“执行 plan”（抽帧、落库、组装 Result）。

## 目标
- 在 `transcribe` 之后引入 `plan` 阶段：基于 transcript（必要时基于 chunk summaries）生成可渲染的结构化计划。
- 计划输出需保证：
  - mindmap 节点能引用 `targetBlockId`（用于定位内容块）
  - tiptap 内容块（contentBlocks）内同时包含 highlights 与 keyframes（时间点列表 + 资产引用）
  - 全链路时间单位一致（ms）
- keyframes 抽取改为使用 plan 给出的 `timeMs` 列表（不再等距采样）。
- Result schema 升级：新增 `contentBlocks`（并保持对旧字段的兼容策略）。
- 更新对外接口契约文档 `api.md`（仅契约，前端实现不在本 story 范围）。

## 非目标
- 不在本 story 实现前端联动。
- 不做多版本结果管理（仍写 latest result）。

## 设计概述
### 1) 新的 plan 输出（严格 JSON）
建议将 plan 输出作为 Result 的“生成真相”，并支持后续用户编辑 overlay。

**Plan 核心结构（建议）**
```json
{
  "schemaVersion": "2026-02-06",
  "contentBlocks": [
    {
      "blockId":"b01",
      "idx":0,
      "title":"...",
      "startMs":0,
      "endMs":60000,
      "highlights": [
        {
          "highlightId":"h01",
          "idx":0,
          "text":"...",
          "startMs":12000,
          "endMs":18000,
          "startMs":12000,
          "endMs":18000,
          "keyframes": [{"timeMs":15000}]
        }
      ]
    }
  ],
  "mindmap": {
    "nodes": [
      {"id":"n0","type":"root","label":"视频主题","level":0,"data":{}},
      {"id":"n1","type":"topic","label":"...","level":1,"data":{"targetBlockId":"b01"}},
      {"id":"n2","type":"detail","label":"...","level":2,"data":{"targetBlockId":"b01","targetHighlightId":"h01"}}
    ],
    "edges": [
      {"id":"e1","source":"n0","target":"n1"},
      {"id":"e2","source":"n1","target":"n2","label":"(optional)"}
    ]
  }
}
```

约束：
- `mindmap.nodes[*].type` 必须是 `root`、`topic` 或 `detail`。
- 恰好 1 个 `root` 节点（level=0），无 `targetBlockId`。
- `topic` 节点（level=1）**必须**包含 `data.targetBlockId`，引用 `contentBlocks[].blockId`。
- `detail` 节点（level=2）**必须**包含 `data.targetBlockId`，**可选** `data.targetHighlightId`（引用 `highlights[].highlightId`）。
- `edges[*].source` / `target` 必须引用已存在的 `nodes[].id`。`label` 可选。
- 拓扑为 DAG：root → topics → details。root 无入边。
- `mindmap.nodes[*].data.targetBlockId` 必须引用一个已存在的 `contentBlocks[].blockId`。
- （可选）`mindmap.nodes[*].data.targetHighlightId`：用于更细粒度节点定位，必须引用一个已存在的 `contentBlocks[].highlights[].highlightId`。

### 2) Worker 流水线改造（阶段编排）
在 `PipelineJobProcessor`（`app/worker/worker_loop.py`）中：
- 保持：`speech_to_text`（`run_real_transcribe`）
- 新增：`plan` 内部阶段（建议 internal stage name `plan`，映射到 PublicStage 可复用 `segment` 或 `analyze`）：
  - 输入：
    - 优先使用 chunk summaries（来自压缩 story）
    - 若无 summaries，则对 transcript 做轻量裁剪后直喂
  - 输出：`plan` JSON（内含 contentBlocks/mindmap + highlight.keyframe.timeMs）
- 修改：keyframes 阶段
  - 不再调用 `_sample_times_ms`；改为遍历 plan 给出的 keyframeTimes
  - 抽帧后回填：将 `assetId` 与 `contentUrl` 写回 `contentBlocks[].highlights[].keyframes`（`contentUrl` 形如 `/api/v1/assets/{assetId}/content`）
- assemble_result：
  - 新 schemaVersion
  - 持久化 `contentBlocks`、`mindmap`、`assetRefs`（方案A：不再持久化顶层 chapters/highlights）

可观测性/进度监测（必须满足现有 SSE + 轮询机制）：

- plan 阶段开始/结束时必须更新并持久化：`job.stage="plan"`、`job.progress=...`、`job.updated_at_ms`。
- 同步向 SSE 事件总线发送：`emit_state(status=running)`、`emit_progress(progress=...)`、必要的 `emit_log(...)`。
- 在对外 stage 映射表中加入 `plan -> PublicStage.ANALYZE`（或其它你认可的稳定 PublicStage），以保证 `GET /api/v1/jobs/{jobId}` 的 stage 可被前端稳定识别。

### 3) LLM 调用策略（一致性优先）
- Plan 阶段推荐 **单次串行调用**：一个 LLM 输出整个 plan，保证 ID/粒度统一。
- 可选两段式（仍串行）：当摘要材料不足时，先局部补料再修正 plan。
- 并发只用于非 LLM 重任务：ffmpeg 抽帧、多时间点处理。

## API 契约变更（文档更新）
- 更新 `GET /api/v1/projects/{projectId}/results/latest` 响应：
  - `contentBlocks` 作为渲染主入口（避免重复返回 `chapters/highlights`）
  - `mindmap.nodes[*].data.targetBlockId` / `targetHighlightId` 作为联动锚点
- 详见本 story 交付：更新 `api.md`。

## 代码改动点（建议文件）
- 新增：`services/core/src/core/app/pipeline/llm_plan.py`
  - `generate_plan(transcript, summaries?, provider)`
  - plan JSON 校验（pydantic models）
  - prompt 构建与输出修复（repair call，可选）
- 修改：`services/core/src/core/app/worker/worker_loop.py`
  - 插入 plan 阶段
  - keyframes 阶段改为 plan 驱动
  - result 组装改为写入 contentBlocks
- 修改：`services/core/src/core/app/pipeline/keyframes.py`
  - 增加从“显式 timeMs 列表”抽帧的路径（或新增函数 `extract_keyframes_at_times`）
- 修改：`services/core/src/core/pipeline/stages/assemble_result.py`
  - 允许存储 `contentBlocks`
- 可能修改：`services/core/src/core/db/models/result.py`
  - 新增 JSON 列 `content_blocks`（如果选择显式列）。


## 数据迁移策略（vNext，需与方案A一致）

目标：升级到“只持久化 `contentBlocks`（+ mindmap/note_json/asset_refs）”后：

- 新 Job 写入不再依赖 legacy 的 `results.chapters / results.highlights / results.note`，避免 NOT NULL legacy 列导致插入失败。
- 老库升级后，尽量不丢历史 Result 的可渲染性：至少能返回非空 `contentBlocks`（哪怕是 best-effort 派生）。

### 1) 结果表结构变更（SQLite）

落地目标（ORM 视角）：

- `results.content_blocks`（JSON，非空，默认 `[]`）
- `results.mindmap`（JSON，非空，默认 `{}`）
- `results.note_json`（JSON，非空，默认 `{}`；当前实现仍承载 tiptap doc，后续可演进为导出格式）
- `results.asset_refs`（JSON，非空，默认 `[]`；方案A 仅要求保留 video 引用，截图已内联在 highlight.keyframe.contentUrl）

不再写入（legacy）：

- `results.chapters`
- `results.highlights`
- `results.note`
- （legacy `highlight.keyframe` 已废弃，统一使用 `highlight.keyframes`）

### 2) 启动时 schema-compat 升级策略（必须幂等）

后端启动时做 best-effort 兼容升级（当前代码已采用“检测列 → 必要时重建表”的策略）：

1) 读取 `PRAGMA table_info(results)`，判断是否存在 legacy NOT NULL 列（典型：`chapters/highlights/note`）。
2) 若存在：
   - `ALTER TABLE results RENAME TO results_old`
   - `CREATE TABLE results (...)` 仅包含 vNext 所需列（content_blocks/mindmap/note_json/asset_refs + version + timestamps）
   - 将 `results_old` 拷贝到新表：
     - `mindmap`：若旧表有则原样拷贝，否则填 `{}`
     - `asset_refs`：若旧表有则原样拷贝（可选：过滤仅保留 kind=video）
     - `note_json`：优先用 `note_json`，否则用 legacy `note`（避免丢失历史笔记 JSON）
     - `content_blocks`：
       - 若旧表已有 `content_blocks`：原样拷贝
       - 否则：执行“派生回填”（见下节 3）
   - `DROP TABLE results_old`
3) 若不存在 legacy 列：只需确保 vNext 列存在（`ALTER TABLE ADD COLUMN ... DEFAULT ...`）。

安全性建议：

- migration 仅在 SQLite 本地文件上执行，且应当“可重复运行无副作用”。
- 若重建失败：保留 `results_old` 作为人工恢复入口（或输出日志指引）。

### 3) 旧结果派生回填（关键：避免升级后历史结果变空）

当旧表无 `content_blocks` 但存在 `chapters/highlights/(chapter.keyframes)` 时，需要生成一个最小可渲染的 `contentBlocks`：

- 每个 chapter → 一个 block：
  - `blockId = "b_{chapterId}"`（确定性、可复现）
  - `idx/title/startMs/endMs` 来自 chapter
- chapter 下的 highlights → block.highlights：
  - `highlightId/idx/text` 来自 highlight
  - `startMs/endMs`：若只有 `timeMs`，按 `timeMs±5000ms` 夹紧到 block 范围
  - `keyframes`：从 chapter.keyframes 中选择与 highlight 时间最接近的一个（若存在），写成列表：
    - `[{assetId, contentUrl: "/api/v1/assets/{assetId}/content", timeMs}]`

说明：该派生逻辑必须与 assemble_result 的派生逻辑保持一致（作为“legacy→contentBlocks”单一规则源），以便：

- 升级迁移时（历史数据）派生
- 运行期兜底（当某条 Result 的 content_blocks 意外为空）派生

### 4) 兼容读路径（运行期）

即使完成迁移，也建议在运行期增加防御：

- 若 `results.content_blocks` 为空，但存在 legacy artifacts（仅在迁移保留 legacy 列或其它落盘处可取到时）：按上述派生算法生成并返回（可选：顺便写回 DB 进行 backfill）。

### 5) 回滚/排障建议

- 迁移前拷贝一份 `core.sqlite3`（或输出到 `DATA_DIR/_backup/`）。
- 发生异常时：优先检查是否残留 `results_old`，并通过 sqlite 客户端人工导出恢复。

## 验收标准（Acceptance Criteria）
- 新建 job 成功跑完后：
  - Result 中存在 `contentBlocks`，每个 block 含 `highlights`；若 highlight 有 keyframes，则 `highlight.keyframes[0].assetId` 存在。
  - `mindmap.nodes[*].data.targetBlockId` 指向有效 block。
  - （若使用 `targetHighlightId`）指向有效 highlight。
  - `highlight.keyframes[0].timeMs`（若提供）落在对应 block 时间范围。
- 缺 key / LLM 不可用 / 输出不合法：job 失败，`job.error.details.reason` 指示 `missing_credentials` 或 `invalid_llm_output`。

## 测试建议
- 单元测试：plan JSON 校验（引用一致性、时间范围合法性）。
- 单元测试：keyframes 显式 times 抽帧（对 `_sample_times_ms` 逻辑的替代）。
- 端到端：smoke 脚本跑一条 URL 和一条 upload，验证 Result schemaVersion 更新且可反序列化。
