# Story 9.3: [BE/core] 思维导图保存 API（nodes/edges 覆盖式更新）

Status: ready-for-dev

## Story

As a 用户,
I want 编辑思维导图并保存,
so that 我能把自己的理解补充进去。

## Acceptance Criteria

1. Given 提交 mindmap 保存请求 When 保存成功 Then 覆盖更新当前 Result 的 mindmap graph 并返回 `updatedAtMs`。

## Tasks / Subtasks

- [ ] 定义 mindmap save API（路径/请求体以 8.1 契约为准）(AC: 1)
- [ ] 覆盖式更新 nodes/edges，并校验 schema（最小校验：id/引用完整）(AC: 1)
- [ ] 返回 updatedAtMs/ETag（可选） (AC: 1)

## Dev Notes

- mindmap schema 来源于 7.1；保存时不要让前端自由扩展字段导致不可控。

### References

- _bmad-output/planning-artifacts/epics.md

## Dev Agent Record

### Agent Model Used

GPT-5.2
