# Story 8.3: [BE/core] Result 汇总落库与读取（latest Result 可渲染）

Status: ready-for-dev

## Story

As a 用户,
I want 分析完成后能读取项目最新结果,
so that 刷新/重启后仍能直接渲染复习页面。

## Acceptance Criteria

1. Given pipeline 已生成 chapters/highlights/mindmap/keyframes When `assemble_result` 成功 Then Result 落库并更新 `projects.latest_result_id`。
2. When 请求“获取最新 Result”接口 Then 可一次性拿到渲染所需数据（或最小必要引用）且字段名稳定（以 8.1 契约为准）。

## Tasks / Subtasks

- [ ] 设计 Result 表/结构：包含 chapters/highlights/mindmap/note（初始空）/assets 引用 + schemaVersion/pipelineVersion (AC: 1,2)
- [ ] assemble_result：聚合中间产物并写入 Result；更新 projects.latest_result_id (AC: 1)
- [ ] 实现 latest result endpoint（8.1 契约）(AC: 2)
- [ ] 失败归因：缺产物/不一致/写库失败 (AC: 1)

## Dev Notes

- “Result 可独立渲染”是可恢复性关键：前端不得依赖内存态。

### References

- _bmad-output/planning-artifacts/epics.md
- api.md

## Dev Agent Record

### Agent Model Used

GPT-5.2
