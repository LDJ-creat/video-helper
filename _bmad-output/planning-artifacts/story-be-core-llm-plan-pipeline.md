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
  - tiptap 内容块（contentBlocks）内同时包含 highlights 与 keyframes（时间点 + 资产引用）
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
          "keyframe": {"timeMs":15000,"caption":"(optional)"}
        }
      ]
    }
  ],
  "mindmap": {
    "nodes": [
      {"id":"n1","type":"topic","label":"...","data":{"targetBlockId":"b01"}},
      {"id":"n2","type":"detail","label":"...","data":{"targetHighlightId":"h01"}}
    ],
    "edges": [{"id":"e1","source":"n1","target":"n2"}]
  }
}
```

约束：
- `mindmap.nodes[*].data.targetBlockId` 必须引用一个已存在的 `contentBlocks[].blockId`。
- （可选）`mindmap.nodes[*].data.targetHighlightId`：用于更细粒度节点定位，必须引用一个已存在的 `contentBlocks[].highlights[].highlightId`。
- `contentBlocks` 必须按 `idx` 连续，且时间范围不重叠（MVP：允许轻微 gap，但不 overlap）。
- `contentBlocks[].highlights[]` 必须按 `idx` 连续（每个 block 内独立计数）。
- `contentBlocks[].highlights[].startMs/endMs` 必须落在所属 block 的 `[startMs,endMs)`。
- `contentBlocks[].highlights[].keyframe.timeMs`（若提供）必须落在所属 block 的 `[startMs,endMs)`。

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
  - 抽帧后回填：将 `assetId` 与 `contentUrl` 写回 `contentBlocks[].highlights[].keyframe`（`contentUrl` 形如 `/api/v1/assets/{assetId}/content`）
- assemble_result：
  - 新 schemaVersion
  - 持久化 `contentBlocks`、`mindmap`、`assetRefs`（方案A：不再持久化顶层 chapters/highlights）

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
  - 新增 JSON 列 `content_blocks`（如果选择显式列），或复用 `note` / `chapters` 字段不建议。
  - MVP 可先将 `contentBlocks` 存入 `note` 不合适；建议增加列并迁移。

## 数据迁移策略（MVP）
- SQLite 增加 `results.content_blocks` JSON 列（nullable=false with default `[]` 或 nullable=true + 读时补默认）。
- 旧结果读取：缺失 `contentBlocks` 时，后端可 best-effort 从 `chapters/highlights/keyframes` 组合生成一个简化 `contentBlocks` 以保持 API 稳定（可选）。

## 验收标准（Acceptance Criteria）
- 新建 job 成功跑完后：
  - Result 中存在 `contentBlocks`，每个 block 含 `highlights`；若 highlight 有 keyframe，则 `highlight.keyframe.assetId` 存在。
  - `mindmap.nodes[*].data.targetBlockId` 指向有效 block。
  - （若使用 `targetHighlightId`）指向有效 highlight。
  - `highlight.keyframe.timeMs`（若提供）落在对应 block 时间范围。
- 缺 key / LLM 不可用 / 输出不合法：job 失败，`job.error.details.reason` 指示 `missing_credentials` 或 `invalid_llm_output`。

## 测试建议
- 单元测试：plan JSON 校验（引用一致性、时间范围合法性）。
- 单元测试：keyframes 显式 times 抽帧（对 `_sample_times_ms` 逻辑的替代）。
- 端到端：smoke 脚本跑一条 URL 和一条 upload，验证 Result schemaVersion 更新且可反序列化。
