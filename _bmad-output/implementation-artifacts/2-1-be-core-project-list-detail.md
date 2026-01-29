# Story 2.1: [BE/core] Project 持久化与项目查询 API（list/detail）

Status: ready-for-dev

## Story

As a 用户,
I want 查看项目列表与项目详情,
so that 我能管理多个视频并随时打开。

## Acceptance Criteria

1. Given 数据库为空 When 请求项目列表（cursor pagination）Then 返回 `{ items: [], nextCursor: null }`。
2. Given 多个项目 When 以 `limit` 获取列表 Then items 不超过 limit，返回稳定排序与 `nextCursor`（opaque，可继续翻页不重复/漏项）。
3. Given 请求不存在的项目详情 When 服务处理 Then 返回统一错误 envelope。

## Tasks / Subtasks

- [ ] 设计并实现 projects 表（含 `latestResultId` 指针、created/updated 时间戳 ms）(AC: 1,2,3)
- [ ] 实现 `GET /api/v1/projects` cursor 分页（统一 `{items,nextCursor}`）(AC: 1,2)
- [ ] 实现 `GET /api/v1/projects/{projectId}`，not found 用统一错误 envelope (AC: 3)
- [ ] DTO 输出字段 camelCase（对外）(AC: 1,2,3)

## Dev Notes

- 统一分页/错误/ID/时间戳：_bmad-output/implementation-artifacts/00-standards-and-parallel-plan.md

### References

- _bmad-output/planning-artifacts/epics.md
- _bmad-output/planning-artifacts/prd.md

## Dev Agent Record

### Agent Model Used

GPT-5.2
