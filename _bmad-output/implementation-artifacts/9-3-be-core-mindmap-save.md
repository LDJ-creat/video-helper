# Story 9.3: [BE/core] 思维导图保存 API（nodes/edges 覆盖式更新）

Status: review

## Story

As a 用户,
I want 编辑思维导图并保存,
so that 我能把自己的理解补充进去。

## Acceptance Criteria

1. Given 提交 mindmap 保存请求 When 保存成功 Then 覆盖更新当前 Result 的 mindmap graph 并返回 `updatedAtMs`。

## Tasks / Subtasks

- [x] 定义 mindmap save API（路径/请求体以 8.1 契约为准）(AC: 1)
- [x] 覆盖式更新 nodes/edges，并校验 schema（最小校验：id/引用完整）(AC: 1)
- [x] 返回 updatedAtMs/ETag（可选） (AC: 1)

## Dev Notes

- mindmap schema 来源于 7.1；保存时不要让前端自由扩展字段导致不可控。

### References

- _bmad-output/planning-artifacts/epics.md

## Dev Agent Record

### Agent Model Used

GPT-5.2

### Completion Notes

- 新增 `PUT /api/v1/projects/{projectId}/results/latest/mindmap`：覆盖写入当前 latest result 的 `mindmap`，返回 `updatedAtMs` + `ETag`。
- Mindmap 保存做最小但可控的 schema 校验：nodes/edges 类型正确、node id 唯一、edge 引用完整；同时对 node/edge 字段做白名单限制，防止前端自由扩展字段。

### Tests

- `services/core/tests/test_editing_apis.py::TestEditingAPIs::test_save_mindmap_validates_and_overwrites`

## File List

- services/core/src/core/app/api/editing.py
- services/core/src/core/schemas/editing.py
- services/core/src/core/contracts/error_codes.py
- services/core/src/core/db/models/result.py
- services/core/src/core/db/session.py
- services/core/src/core/pipeline/stages/assemble_result.py
- services/core/src/core/main.py
- services/core/tests/test_editing_apis.py
- _bmad-output/implementation-artifacts/9-3-be-core-mindmap-save.md

## Change Log

- 2026-02-04：新增 mindmap 保存 API（nodes/edges 覆盖式更新 + 校验 + updatedAtMs/ETag）并补齐测试。

