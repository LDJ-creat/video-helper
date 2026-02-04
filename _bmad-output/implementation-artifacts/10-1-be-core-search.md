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

- [x] 设计 search endpoint：`GET /api/v1/search?query=...&cursor=...&limit=...`（或按 api.md）(AC: 1)
- [x] 搜索范围（MVP）：project title/summary/notes 派生文本（先能用）(AC: 1)
- [x] cursor 分页与排序稳定 (AC: 1)

## Dev Notes

- MVP 可先不用 FTS5；后续再演进。

### References

- _bmad-output/planning-artifacts/epics.md
- _bmad-output/planning-artifacts/prd.md

## Dev Agent Record

### Agent Model Used

GPT-5.2

### Implementation Notes

- Endpoint：`GET /api/v1/search?query=...&cursor=...&limit=...`，返回 `{ items, nextCursor }`。
- 搜索范围（MVP）：
	- project.title（case-insensitive LIKE）
	- latest result 的 JSON 文本（chapters/highlights/note 的 cast-to-text LIKE）
- items 定位：必含 projectId；若 query 命中 chapters.title/summary 或 highlights.text，则尽力返回 chapterId（否则为 null）。
- 分页：稳定排序 `(projects.updated_at_ms desc, projects.project_id desc)`，cursor 编码最后一条的 `(updatedAtMs, projectId)`。
- 参数校验：空 query 返回 400 + error envelope（VALIDATION_ERROR, reason=invalid_query）。

### Tests

- 新增 search API 测试（title 命中、chapterId 推断、cursor 分页稳定、空 query 错误）。
- `pytest` 全量通过。

### File List

- services/core/src/core/app/api/search.py
- services/core/src/core/db/repositories/search.py
- services/core/src/core/schemas/search.py
- services/core/src/core/main.py
- services/core/tests/test_search_api.py
