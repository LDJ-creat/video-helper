# Story 4.3: [FE/web] SSE 消费与轮询降级（React Query 驱动）

Status: ready-for-dev

## Story

As a 用户,
I want 前端默认用 SSE 展示进度并在断线时自动降级轮询,
so that 页面刷新/网络波动也能持续可用。

## Acceptance Criteria

1. Given SSE 正常 When 收到 progress/state/log 事件 Then 更新 React Query 中对应 job 的缓存；UI 只从缓存派生展示。
2. Given SSE 断线/超时 When 判定不可用 Then 自动切换到轮询 `GET /api/v1/jobs/{jobId}` 继续更新。

## Tasks / Subtasks

- [ ] 实现 SSE client（EventSource/自定义 fetch stream）并解析 event type/payload (AC: 1)
- [ ] React Query：维护 job query + logs query（如需要），SSE 事件驱动 cache 更新 (AC: 1)
- [ ] 断线策略：心跳超时/close/error → fallback polling；恢复后可切回 SSE（可选）(AC: 2)
- [ ] 错误 envelope 统一展示：网络错误 vs 业务错误（failed）区分 (AC: 1,2)

## Dev Notes

- SSE payload 契约与字段名不可自创；严格跟随统一标准。
- 统一标准见：_bmad-output/implementation-artifacts/00-standards-and-parallel-plan.md

### References

- _bmad-output/planning-artifacts/epics.md
- api.md

## Dev Agent Record

### Agent Model Used

GPT-5.2
