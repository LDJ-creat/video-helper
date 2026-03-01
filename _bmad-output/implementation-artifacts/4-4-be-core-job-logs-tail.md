# Story 4.4: [BE/core] Job 日志 tail API（cursor）

Status: review

## Story

As a 用户,
I want 在 Job 运行/失败时查看可分页的日志尾部,
so that 我能理解失败原因并自助排查。

## Acceptance Criteria

1. Given Job 有日志 When 请求 `GET /api/v1/jobs/{jobId}/logs?limit=200&cursor=...` Then 返回 `{ items, nextCursor }`。
2. items 每条至少包含 `tsMs`, `level`, `message`, `stage`，cursor 为 opaque，不泄露文件路径/偏移细节。

## Tasks / Subtasks

- [x] 选择日志落盘/落库策略（MVP 推荐文件落盘 + cursor）(AC: 1,2)
- [x] 定义 LogItem DTO（camelCase，tsMs/stage/level/message）(AC: 2)
- [x] 实现 logs tail endpoint：limit 与 cursor 语义明确、稳定、可重复请求 (AC: 1,2)
- [x] 权限/不存在/读取失败：统一错误 envelope；不泄露绝对路径 (AC: 1,2)

## Dev Notes

- cursor 设计建议：opaque token（例如 base64 编码的 offset+checksum），但对外只当字符串。
- 统一标准见：_bmad-output/implementation-artifacts/00-standards-and-parallel-plan.md

### References

- _bmad-output/planning-artifacts/epics.md
- api.md

## Dev Agent Record

### Agent Model Used

GPT-5.2

### Completion Notes

- Implemented `GET /api/v1/jobs/{jobId}/logs?limit=...&cursor=...` returning `{ items, nextCursor }`.
- MVP storage uses file-based JSONL at `DATA_DIR/logs/jobs/{jobId}.log`.
- Cursor is opaque + tamper-detected (base64url payload + HMAC), and does not include file paths.
- Behavior: no cursor → returns last `limit` items and cursor at EOF; cursor → returns new appended lines from that position.
- Read failures return unified error envelope `JOB_LOGS_UNAVAILABLE` without leaking absolute paths.

### File List

- services/core/src/core/app/logs/job_logs.py
- services/core/src/core/app/api/jobs.py
- services/core/src/core/schemas/logs.py
- services/core/tests/test_job_logs_tail.py
