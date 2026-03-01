# Story 4.3: [FE/web] SSE 消费与轮询降级（React Query 驱动）

Status: done

## Story

As a 用户,
I want 前端默认用 SSE 展示进度并在断线时自动降级轮询,
so that 页面刷新/网络波动也能持续可用。

## Acceptance Criteria

1. Given SSE 正常 When 收到 progress/state/log 事件 Then 更新 React Query 中对应 job 的缓存；UI 只从缓存派生展示。
2. Given SSE 断线/超时 When 判定不可用 Then 自动切换到轮询 `GET /api/v1/jobs/{jobId}` 继续更新。

## Tasks / Subtasks

- [x] 实现 SSE client（EventSource/自定义 fetch stream）并解析 event type/payload (AC: 1)
- [x] React Query：维护 job query + logs query（如需要），SSE 事件驱动 cache 更新 (AC: 1)
- [x] 断线策略：心跳超时/close/error → fallback polling；恢复后可切回 SSE（可选）(AC: 2)
- [x] 错误 envelope 统一展示：网络错误 vs 业务错误（failed）区分 (AC: 1,2)

## Dev Notes

- SSE payload 契约与字段名不可自创；严格跟随统一标准。
- 统一标准见：_bmad-output/implementation-artifacts/00-standards-and-parallel-plan.md

### References

- _bmad-output/planning-artifacts/epics.md
- api.md

## Dev Agent Record

### Agent Model Used

Gemini 2.0 Flash Thinking Experimental

### Implementation Summary

实现了完整的 SSE 客户端与轮询降级策略：

1. **SSE Client** (`sseClient.ts`)：封装 EventSource，支持心跳超时检测和自动断线处理
2. **useJobSse Hook** (`useJobSse.ts`)：集成 SSE 与 React Query，自动更新缓存，断线降级到轮询
3. **Job Queries** (`jobQueries.ts`, `jobApi.ts`)：实现带轮询的 Job 查询和 Logs 查询
4. **React Query Provider** (`providers.tsx`)：配置全局 QueryClient

### Files Changed

- [NEW] `src/lib/sse/sseClient.ts` - SSE 客户端核心逻辑
- [MODIFY] `src/lib/sse/useJobSse.ts` - SSE hook 实现
- [NEW] `src/lib/api/jobQueries.ts` - React Query hooks
- [NEW] `src/lib/api/jobApi.ts` - Job API 调用函数
- [MODIFY] `src/lib/api/endpoints.ts` - 添加 Job 相关端点
- [MODIFY] `src/lib/api/queryKeys.ts` - 添加 job/logs query keys
- [NEW] `src/lib/contracts/types.ts` - Job 和 Log 类型定义
- [NEW] `src/lib/constants/stageMapping.ts` - Stage 中文映射
- [NEW] `src/lib/constants/errorMessages.ts` - 错误建议映射
- [NEW] `src/app/providers.tsx` - React Query Provider
- [MODIFY] `src/app/layout.tsx` - 集成 Providers
- [MODIFY] `package.json` - 添加 @tanstack/react-query 依赖

### Tests

TypeScript 编译通过 ✓
