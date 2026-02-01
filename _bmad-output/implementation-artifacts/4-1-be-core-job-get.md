# Story 4.1: [BE/core] Job 状态查询 API（轮询降级基础）

Status: review

## Story

As a 用户,
I want 查询 Job 的 status/stage/progress,
so that 在 SSE 不可用时仍可恢复进度展示。

## Acceptance Criteria

1. Given Job 存在 When 请求 `GET /api/v1/jobs/{jobId}` Then 返回 job DTO，至少包含 `status`, `stage`, `progress`, `error`, `updatedAtMs`。
2. Given Job 不存在 When 请求 `GET /api/v1/jobs/{jobId}` Then 返回统一错误 envelope（例如 `JOB_NOT_FOUND`）。
3. `stage` 必须来自稳定集合（见统一标准），`progress` 在 0..1（可为空但不可越界）。

## Tasks / Subtasks

- [x] 定义 Job DTO（camelCase）与 error envelope（统一）(AC: 1,2)
- [x] 实现 `GET /api/v1/jobs/{jobId}`：从 DB 读取最新状态 (AC: 1)
- [x] 校验并规范化 stage/progress（避免越界/空值混乱）(AC: 3)
- [x] Not found / invalid id 走统一错误码与 envelope (AC: 2)

## Dev Notes

- 这是前端轮询降级与“刷新可恢复”的硬依赖。
- 统一标准见：_bmad-output/implementation-artifacts/00-standards-and-parallel-plan.md

### References

- _bmad-output/planning-artifacts/epics.md
- api.md

## Dev Agent Record

### Agent Model Used

GPT-5.2

### Completion Notes

- Implemented `GET /api/v1/jobs/{jobId}` with stable stage mapping and progress normalization.
- Added minimal DB model/session wiring to support the endpoint.
- Tests: `python -m unittest discover -s tests -p "test_*.py" -v` (PASS).

## File List

- services/core/src/core/app/api/jobs.py
- services/core/src/core/main.py
- services/core/src/core/schemas/jobs.py
- services/core/src/core/db/base.py
- services/core/src/core/db/session.py
- services/core/src/core/db/models/job.py
- services/core/src/core/db/models/__init__.py
- services/core/src/core/db/repositories/jobs.py
- services/core/src/core/db/repositories/__init__.py
- services/core/tests/test_job_get.py

## Change Log

- 2026-01-30: Add Job status GET API + unit tests.
