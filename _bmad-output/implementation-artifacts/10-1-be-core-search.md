# Story 10.1: [BE/core] 搜索 API（MVP：title/summary/派生文本）

Status: ready-for-dev

## Story

As a 用户,
I want 用关键词搜索项目/笔记摘要,
so that 我能快速找到需要复习的内容。

## Acceptance Criteria

1. Given 请求搜索并提供 query When 有匹配 Then 返回 `{ items, nextCursor }`。
2. items 至少包含 `projectId`（可选 `chapterId`）以便定位。

## Tasks / Subtasks

- [ ] 设计 search endpoint：`GET /api/v1/search?query=...&cursor=...&limit=...`（或按 api.md）(AC: 1)
- [ ] 搜索范围（MVP）：project title/summary/notes 派生文本（先能用）(AC: 1)
- [ ] cursor 分页与排序稳定 (AC: 1)

## Dev Notes

- MVP 可先不用 FTS5；后续再演进。

### References

- _bmad-output/planning-artifacts/epics.md
- _bmad-output/planning-artifacts/prd.md

## Dev Agent Record

### Agent Model Used

GPT-5.2
