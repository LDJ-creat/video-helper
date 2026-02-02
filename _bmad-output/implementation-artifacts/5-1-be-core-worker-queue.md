# Story 5.1: [BE/core] Worker 队列与并发控制（MAX_CONCURRENT_JOBS=2）

Status: review

## Story

As a 维护者,
I want 后端以应用层队列执行 Job 并限制并发,
so that 在单机环境下稳定运行且可恢复。

## Acceptance Criteria

1. Given 多个 Job queued When worker loop 运行 Then 同时最多处理 `MAX_CONCURRENT_JOBS` 个 running Job（默认 2）。
2. Given 服务重启 When worker loop 恢复 Then queued/running/failed/succeeded 状态可被重新读取并继续展示（至少可查询，不丢失）。
3. 必须有 DB-backed claim 机制 best-effort 防止重复消费。

## Tasks / Subtasks

- [x] 设计 Job 状态机字段（queued/running/succeeded/failed/canceled）与 stage/progress/error 持久化 (AC: 1,2)
- [x] 实现 worker loop（后台任务/独立进程均可）扫描 queued 并 claim (AC: 1,3)
- [x] 并发控制：限制 running 数量；资源不足时排队或明确错误 (AC: 1)
- [x] 重启恢复：running 的处理策略（标记为 queued 重新跑 or 失败可归因）(AC: 2)

## Dev Notes

- 这是后续 transcribe/segment/analyze/... 所有 stage 的执行基座。
- 同时要为 SSE/轮询提供状态更新来源（DB 更新 + 可选事件 buffer）。

### References

- _bmad-output/planning-artifacts/epics.md
- _bmad-output/planning-artifacts/prd.md

## Dev Agent Record

### Agent Model Used

GPT-5.2

### Completion Notes

- 新增 jobs 表的 DB-backed claim/lease 字段，并在 sqlite 兼容升级中自动补列，确保重启后可读取并继续展示 (AC: 2,3)
- 实现 worker tick + 可选后台 WorkerService（默认关闭，通过 WORKER_ENABLE=1 启用），并发上限由 MAX_CONCURRENT_JOBS 控制 (AC: 1)
- 启动时将 running 任务 best-effort 重新置为 queued（清理 claim/lease），作为重启恢复策略 (AC: 2)

### Tests

- 运行：`python -m unittest discover -s tests -p "test_*.py"`（全绿）

## File List

- services/core/src/core/app/api/jobs.py
- services/core/src/core/app/worker/__init__.py
- services/core/src/core/app/worker/worker_loop.py
- services/core/src/core/db/models/job.py
- services/core/src/core/db/repositories/job_queue.py
- services/core/src/core/db/session.py
- services/core/src/core/main.py
- services/core/tests/test_worker_queue.py

## Change Log

- 2026-02-02: 实现 Worker 队列与并发控制基座（DB-backed claim + worker tick + 重启恢复）
