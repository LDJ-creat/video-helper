# Story 8.3: [BE/core] Result 汇总落库与读取（latest Result 可渲染）

Status: review

## Story

As a 用户,
I want 分析完成后能读取项目最新结果,
so that 刷新/重启后仍能直接渲染复习页面。

## Acceptance Criteria

1. Given pipeline 已生成 chapters/highlights/mindmap/keyframes When `assemble_result` 成功 Then Result 落库并更新 `projects.latest_result_id`。
2. When 请求“获取最新 Result”接口 Then 可一次性拿到渲染所需数据（或最小必要引用）且字段名稳定（以 8.1 契约为准）。

## Tasks / Subtasks

- [x] 设计 Result 表/结构：包含 chapters/highlights/mindmap/note（初始空）/assets 引用 + schemaVersion/pipelineVersion (AC: 1,2)
- [x] assemble_result：聚合中间产物并写入 Result；更新 projects.latest_result_id (AC: 1)
- [x] 实现 latest result endpoint（8.1 契约）(AC: 2)
- [x] 失败归因：缺产物/不一致/写库失败 (AC: 1)

## Dev Notes

- “Result 可独立渲染”是可恢复性关键：前端不得依赖内存态。

### References

- _bmad-output/planning-artifacts/epics.md
- api.md

## Dev Agent Record

### Agent Model Used

GPT-5.2

### Completion Notes

- 新增 `results` 表，持久化可独立渲染的 Result（chapters/highlights/mindmap/note/assetRefs + versions）
- 实现 `assemble_result()`：写入 Result 并更新 `projects.latest_result_id`（含失败归因）
- 实现 `GET /api/v1/projects/{projectId}/results/latest`（项目/结果不存在按统一错误 envelope 返回）

### Tests

- `services/core/tests/test_results_latest_api.py`

## File List

- services/core/src/core/main.py
- services/core/src/core/app/api/results.py
- services/core/src/core/db/models/result.py
- services/core/src/core/db/repositories/results.py
- services/core/src/core/db/session.py
- services/core/src/core/pipeline/stages/assemble_result.py
- services/core/src/core/schemas/results.py
- services/core/tests/test_results_latest_api.py
- _bmad-output/implementation-artifacts/sprint-status.yaml
- _bmad-output/implementation-artifacts/8-3-be-core-result-assemble.md

## Change Log

- 2026-02-02：实现 Result 落库与 latest result 读取接口，并补齐单测。
