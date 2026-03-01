# Story 9.5: [BE/core] 章节编辑 API（保证章节唯一准则一致性）

Status: review

## Story

As a 用户,
I want 编辑章节标题（可选时间范围/顺序）,
so that 章节更贴合我的复习习惯且不破坏跳转。

## Acceptance Criteria

1. Given 仅修改章节标题 When 保存成功 Then 不影响 start/end 与已有产物引用关系（chapterId 稳定）。
2. Given 修改章节时间范围（若允许）When 保存成功 Then 系统保持章节序与不重叠规则（或返回可理解错误），并确保跳转仍成立。

## Tasks / Subtasks

- [x] 设计章节编辑 API（标题必做；时间范围可选开关）(AC: 1,2)
- [x] 保证 chapterId 稳定；仅修改可变字段（title/order/startMs/endMs）(AC: 1)
- [x] 校验规则：start<end、章节不重叠、顺序一致；失败返回错误码 (AC: 2)

## Dev Notes

- 章节是唯一准则：任何“重切片”都可能影响 highlights/keyframes/mindmap 引用，MVP 优先只允许改 title。

### References

- _bmad-output/planning-artifacts/epics.md
- _bmad-output/planning-artifacts/prd.md

## Dev Agent Record

### Agent Model Used

GPT-5.2

### Completion Notes

- 新增 `PATCH /api/v1/projects/{projectId}/results/latest/chapters/{chapterId}`：默认支持改 `title`/`idx`（顺序），确保 `chapterId` 稳定且不改动 keyframes 引用。
- 时间范围编辑通过环境变量开关 `ALLOW_CHAPTER_TIME_EDIT=1` 启用；关闭时返回 `CHAPTER_TIME_EDIT_DISABLED`。
- 启用时间编辑时做约束校验：`startMs < endMs`、按 idx 顺序不重叠（重叠返回 `CHAPTER_OVERLAP`）。

### Tests

- `services/core/tests/test_editing_apis.py::TestEditingAPIs::test_edit_chapter_title_does_not_change_time`

## File List

- services/core/src/core/app/api/editing.py
- services/core/src/core/schemas/editing.py
- services/core/src/core/contracts/error_codes.py
- services/core/src/core/db/models/result.py
- services/core/src/core/db/session.py
- services/core/src/core/pipeline/stages/assemble_result.py
- services/core/src/core/main.py
- services/core/tests/test_editing_apis.py
- _bmad-output/implementation-artifacts/9-5-be-core-chapter-edit.md

## Change Log

- 2026-02-04：新增章节编辑 API（标题必做 + 时间范围 feature-flag）并补齐校验与测试。

