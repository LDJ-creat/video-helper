# Story 12.1: [BE/core] LLM-Plan 驱动的视频分析流水线（统一产物一致性）

Status: ready-for-dev

## Story

As a 用户,
I want 流水线由单次 LLM 规划输出统一的内容块/高亮/思维导图/关键帧时间点,
so that 章节、关键帧与下游 highlights/mindmap 一致且可稳定渲染。

## Acceptance Criteria

1. Given transcribe 已完成 When 进入 plan 阶段 Then 生成严格 JSON 的 plan，包含 `contentBlocks` 与 `mindmap`，且满足：
   - `mindmap.nodes[*].data.targetBlockId` 引用有效的 `contentBlocks[].blockId`
   - （若提供）`targetHighlightId` 引用有效 highlight
   - 全链路时间单位统一为 `ms` 且落在所属 block 范围内
2. Given plan 已生成 When 执行 keyframes 阶段 Then 抽帧时间点来自 plan（不再等距采样），并将 `assetId` 与 `contentUrl` 回填至 `contentBlocks[].highlights[].keyframe`。
3. Given job 运行 When plan 阶段开始/结束 Then `job.stage="plan"`、`job.progress`、`job.updated_at_ms` 持久化并通过 SSE 发出 progress/state/log（与现有 SSE/轮询兼容）。
4. Given result 落库 When 读取 latest result Then 响应包含 `contentBlocks` 与 `mindmap`，并保持对 legacy 字段的兼容策略（必要时 best-effort 派生 `contentBlocks`）。
5. Given 缺 key/LLM 不可用/输出不合法 When plan 生成失败 Then job 失败且 `job.error.details.reason` 为 `missing_credentials` 或 `invalid_llm_output`。
6. `api.md` 更新：`GET /api/v1/projects/{projectId}/results/latest` 契约包含 `contentBlocks` 作为渲染主入口与 mindmap 的锚点字段。

## Tasks / Subtasks

- [ ] 新增 plan schema + 校验：pydantic models（引用一致性、idx 连续、时间范围合法）(AC: 1)
- [ ] 新增 `llm_plan` 生成：基于 transcript（可选 summaries）单次调用输出 plan；失败归因 `missing_credentials/invalid_llm_output` (AC: 1,5)
- [ ] Worker 插入 plan 阶段：stage/progress/SSE 持久化与对外 stage 映射（plan -> PublicStage.ANALYZE 或等价稳定映射）(AC: 3)
- [ ] Keyframes 改为 plan 驱动：显式 `timeMs` 列表抽帧；回填 asset 引用至 plan 的 keyframe 字段 (AC: 2)
- [ ] Result schema 升级与迁移：新增 `content_blocks/mindmap/note_json/asset_refs`；必要时重建 results 表并对旧结果派生回填 `contentBlocks` (AC: 4)
- [ ] latest result 读路径兼容：当 `content_blocks` 为空时按 legacy 派生兜底（可选写回）(AC: 4)
- [ ] 更新 `api.md` 契约（仅契约，不做前端实现）(AC: 6)
- [ ] 测试：plan JSON 校验；keyframes 显式 times；results 迁移/派生与 latest API 反序列化 (AC: 1,2,4,5)

## Dev Notes

- 设计稿：_bmad-output/planning-artifacts/story-be-core-llm-plan-pipeline.md
- 相关实现参考：
  - _bmad-output/implementation-artifacts/5-4-be-core-stage-mapping.md
  - _bmad-output/implementation-artifacts/6-1-be-core-keyframes.md
  - _bmad-output/implementation-artifacts/6-4-be-core-highlights-llm.md
  - _bmad-output/implementation-artifacts/7-2-be-core-mindmap-llm.md
  - _bmad-output/implementation-artifacts/8-3-be-core-result-assemble.md

## Dev Agent Record

### Agent Model Used

GPT-5.2

### Debug Log


### Completion Notes


### Tests


## File List

- _bmad-output/implementation-artifacts/12-1-be-core-llm-plan-pipeline.md

## Change Log

- 2026-02-06：创建 story 12.1（从 planning-artifacts 设计稿派生）。
