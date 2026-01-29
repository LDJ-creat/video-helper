# Story 3.1: [BE/core] 创建 Job（URL 输入的 JSON 形态）

Status: ready-for-dev

## Story

As a 用户,
I want 粘贴 YouTube/B 站链接即可创建分析任务,
so that 我能开始自动分析流程。

## Acceptance Criteria

1. Given 提交 `POST /api/v1/jobs`（`application/json`，含 `sourceType` 与 `sourceUrl`）When 输入合法 Then 返回 `jobId, projectId, status=queued, createdAtMs`，并持久化 Project + Job。
2. Given `sourceUrl` 非法或 `sourceType` 不支持 When 校验 Then 返回统一错误 envelope，错误 code 可区分输入不合法/平台不支持。

## Tasks / Subtasks

- [ ] 定义 CreateJobRequest(JSON) / Job DTO（camelCase）(AC: 1)
- [ ] 校验 sourceType/sourceUrl（YouTube/B 站）并归因错误码 (AC: 2)
- [ ] 创建 Project（如需）+ Job（queued）并返回 (AC: 1)
- [ ] Web/Docker 禁止 `source_file_path` 成为真相 (AC: 1)

## Dev Notes

- 契约/错误码/分页/ID：_bmad-output/implementation-artifacts/00-standards-and-parallel-plan.md

### References

- _bmad-output/planning-artifacts/epics.md
- api.md

## Dev Agent Record

### Agent Model Used

GPT-5.2
