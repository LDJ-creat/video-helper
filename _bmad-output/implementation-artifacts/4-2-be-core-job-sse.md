# Story 4.2: [BE/core] Job SSE 事件流（含心跳与 Last-Event-ID）

Status: ready-for-dev

## Story

As a 用户,
I want 订阅 Job 的 SSE 事件流获取 progress/log/state,
so that 我能实时看到分析推进且不中断。

## Acceptance Criteria

1. Given 连接 `GET /api/v1/jobs/{jobId}/events` When Job 执行中 Then 周期性发送 `heartbeat` 事件。
2. `progress/log/state` 事件类型与 payload 字段严格符合统一契约：camelCase 且至少包含 `eventId, tsMs, jobId, projectId, stage`；可选 `progress, message`。
3. Given 带 `Last-Event-ID` 重连 When 服务可续传 Then best-effort 从该 eventId 之后继续；若不可续传也不得崩溃，应从当前状态继续。

## Tasks / Subtasks

- [ ] 定义 SSE event schema（后端 contracts）并在实现中强约束字段 (AC: 2)
- [ ] 实现 SSE endpoint：正确设置 headers（`text/event-stream`、禁缓存、心跳）(AC: 1)
- [ ] 设计 eventId 生成策略（单 job 单调递增或时间+序号；保证可比较）(AC: 2,3)
- [ ] 实现 Last-Event-ID best-effort（可先不回放完整日志，但至少不报错）(AC: 3)
- [ ] Job 不存在/无权限：返回统一错误 envelope（注意 SSE 语境下的响应时机）(AC: 1)

## Dev Notes

- 这是“可见性闭环”的核心；前端 4.3 会依赖此契约。
- 统一标准见：_bmad-output/implementation-artifacts/00-standards-and-parallel-plan.md

### References

- _bmad-output/planning-artifacts/epics.md
- api.md

## Dev Agent Record

### Agent Model Used

GPT-5.2
