# Story 9.1: [BE/core] 笔记保存 API（覆盖式更新 + updatedAtMs）

Status: review

## Story

As a 用户,
I want 编辑笔记后可以保存并在下次打开时恢复,
so that 我的复习提纲不会丢。

## Acceptance Criteria

1. Given 提交笔记保存请求（TipTap JSON）When 保存成功 Then 覆盖更新当前 Result 的 note 字段并返回 `updatedAtMs`（或等价）。
2. Then 请求/响应不包含敏感信息或绝对路径；失败返回统一错误 envelope。

## Tasks / Subtasks

- [x] 定义 note schema（存 JSON）与 API 路径（以 8.1 契约/约定为准）(AC: 1)
- [x] 覆盖式更新语义：以 projectId/latestResultId 定位写入 (AC: 1)
- [x] updatedAtMs/ETag（可选）用于前端对账与最小冲突处理 (AC: 1)
- [x] 错误处理：result 不存在/项目不存在/校验失败 (AC: 2)

## Dev Notes

- MVP 不做结果版本化：保存覆盖当前 result。

### References

- _bmad-output/planning-artifacts/epics.md

## Dev Agent Record

### Agent Model Used

GPT-5.2

### Completion Notes

- 新增 `PUT /api/v1/projects/{projectId}/results/latest/note`：覆盖写入当前 latest result 的 `note`，返回 `updatedAtMs`，并通过响应头 `ETag` 提供轻量对账。
- 统一错误 envelope：项目/结果不存在走 `PROJECT_NOT_FOUND`/`RESULT_NOT_FOUND`；payload 校验失败走 `VALIDATION_ERROR`。

### Tests

- `services/core/tests/test_editing_apis.py::TestEditingAPIs::test_save_note_overwrites_and_returns_updated_at`

## File List

- services/core/src/core/app/api/editing.py
- services/core/src/core/schemas/editing.py
- services/core/src/core/contracts/error_codes.py
- services/core/src/core/db/models/result.py
- services/core/src/core/db/session.py
- services/core/src/core/pipeline/stages/assemble_result.py
- services/core/src/core/main.py
- services/core/tests/test_editing_apis.py
- _bmad-output/implementation-artifacts/9-1-be-core-note-save.md

## Change Log

- 2026-02-04：新增 note 保存 API（覆盖式更新 + updatedAtMs/ETag）并补齐测试。

