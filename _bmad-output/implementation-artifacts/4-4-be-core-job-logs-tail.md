# Story 4.4: [BE/core] Job 日志 tail API（cursor）

Status: ready-for-dev

## Story

As a 用户,
I want 在 Job 运行/失败时查看可分页的日志尾部,
so that 我能理解失败原因并自助排查。

## Acceptance Criteria

1. Given Job 有日志 When 请求 `GET /api/v1/jobs/{jobId}/logs?limit=200&cursor=...` Then 返回 `{ items, nextCursor }`。
2. items 每条至少包含 `tsMs`, `level`, `message`, `stage`，cursor 为 opaque，不泄露文件路径/偏移细节。

## Tasks / Subtasks

- [ ] 选择日志落盘/落库策略（MVP 推荐文件落盘 + cursor）(AC: 1,2)
- [ ] 定义 LogItem DTO（camelCase，tsMs/stage/level/message）(AC: 2)
- [ ] 实现 logs tail endpoint：limit 与 cursor 语义明确、稳定、可重复请求 (AC: 1,2)
- [ ] 权限/不存在/读取失败：统一错误 envelope；不泄露绝对路径 (AC: 1,2)

## Dev Notes

- cursor 设计建议：opaque token（例如 base64 编码的 offset+checksum），但对外只当字符串。
- 统一标准见：_bmad-output/implementation-artifacts/00-standards-and-parallel-plan.md

### References

- _bmad-output/planning-artifacts/epics.md
- api.md

## Dev Agent Record

### Agent Model Used

GPT-5.2
