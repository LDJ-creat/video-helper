# Story 9.5: [BE/core] 章节编辑 API（保证章节唯一准则一致性）

Status: ready-for-dev

## Story

As a 用户,
I want 编辑章节标题（可选时间范围/顺序）,
so that 章节更贴合我的复习习惯且不破坏跳转。

## Acceptance Criteria

1. Given 仅修改章节标题 When 保存成功 Then 不影响 start/end 与已有产物引用关系（chapterId 稳定）。
2. Given 修改章节时间范围（若允许）When 保存成功 Then 系统保持章节序与不重叠规则（或返回可理解错误），并确保跳转仍成立。

## Tasks / Subtasks

- [ ] 设计章节编辑 API（标题必做；时间范围可选开关）(AC: 1,2)
- [ ] 保证 chapterId 稳定；仅修改可变字段（title/order/startMs/endMs）(AC: 1)
- [ ] 校验规则：start<end、章节不重叠、顺序一致；失败返回错误码 (AC: 2)

## Dev Notes

- 章节是唯一准则：任何“重切片”都可能影响 highlights/keyframes/mindmap 引用，MVP 优先只允许改 title。

### References

- _bmad-output/planning-artifacts/epics.md
- _bmad-output/planning-artifacts/prd.md

## Dev Agent Record

### Agent Model Used

GPT-5.2
