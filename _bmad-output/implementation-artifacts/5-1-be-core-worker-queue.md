# Story 5.1: [BE/core] Worker 队列与并发控制（MAX_CONCURRENT_JOBS=2）

Status: ready-for-dev

## Story

As a 维护者,
I want 后端以应用层队列执行 Job 并限制并发,
so that 在单机环境下稳定运行且可恢复。

## Acceptance Criteria

1. Given 多个 Job queued When worker loop 运行 Then 同时最多处理 `MAX_CONCURRENT_JOBS` 个 running Job（默认 2）。
2. Given 服务重启 When worker loop 恢复 Then queued/running/failed/succeeded 状态可被重新读取并继续展示（至少可查询，不丢失）。
3. 必须有 DB-backed claim 机制 best-effort 防止重复消费。

## Tasks / Subtasks

- [ ] 设计 Job 状态机字段（queued/running/succeeded/failed/canceled）与 stage/progress/error 持久化 (AC: 1,2)
- [ ] 实现 worker loop（后台任务/独立进程均可）扫描 queued 并 claim (AC: 1,3)
- [ ] 并发控制：限制 running 数量；资源不足时排队或明确错误 (AC: 1)
- [ ] 重启恢复：running 的处理策略（标记为 queued 重新跑 or 失败可归因）(AC: 2)

## Dev Notes

- 这是后续 transcribe/segment/analyze/... 所有 stage 的执行基座。
- 同时要为 SSE/轮询提供状态更新来源（DB 更新 + 可选事件 buffer）。

### References

- _bmad-output/planning-artifacts/epics.md
- _bmad-output/planning-artifacts/prd.md

## Dev Agent Record

### Agent Model Used

GPT-5.2
