# Story 1.2: [FE/web] 启动自检提示（Health Banner）

Status: review

## Story

As a 用户,
I want 在创建分析前就看到依赖是否就绪的提示,
so that 我不会提交后才发现缺依赖。

## Acceptance Criteria

1. Given 前端可访问后端 When 进入导入/创建任务页面 Then 调用 `GET /api/v1/health` 并展示清晰状态；异步加载不阻塞其它交互。
2. Given 健康检查缺依赖 When 查看提示 Then 显示可行动建议（安装 ffmpeg/yt-dlp 或检查模型配置）。

## Tasks / Subtasks

- [x] 增加 health 查询（React Query）与缓存策略（页面进入即触发）(AC: 1)
- [x] 实现 Health Banner 组件：loading/success/warn/error（网络不可用也要可理解）(AC: 1)
- [x] 文案映射：按后端健康检查返回项渲染建议动作 (AC: 2)

## Dev Notes

- 统一标准见：_bmad-output/implementation-artifacts/00-standards-and-parallel-plan.md

### Project Structure Notes

- 前端建议：`apps/web/src/lib/api/*` 封装 health fetch
- 组件建议：`apps/web/src/components/HealthBanner.tsx`

### References

- _bmad-output/planning-artifacts/epics.md
- api.md

## Dev Agent Record

### Agent Model Used

Gemini 2.0 Flash Thinking (2026-02-01)

### Implementation Plan

实现了健康检查横幅组件，用于在导入页面显示系统依赖状态：

1. **类型定义**: 创建 `healthTypes.ts`，定义 Health API 的响应结构
2. **API 层**: 实现 `healthApi.ts` 和 `healthQueries.ts`，使用 React Query 进行健康检查
3. **UI 组件**: 实现 `HealthBanner.tsx`，支持 loading/error/warning/healthy 四种状态

### Completion Notes

✅ 所有 AC 已满足：
- AC1: Health Banner 在页面加载时异步调用 `/api/v1/health`，不阻塞其他交互
- AC2: 缺少依赖时显示可操作建议（ffmpeg/yt-dlp/whisper）

技术实现：
- 使用 React Query 的 `useQuery` hook，配置 30s 缓存和 3 次重试
- 组件支持用户关闭横幅（dismissed 状态）
- 网络错误时显示友好提示
- 根据健康状态自动选择颜色主题（red/yellow）

## File List

- `apps/web/src/lib/contracts/healthTypes.ts` (新增)
- `apps/web/src/lib/api/endpoints.ts` (修改)
- `apps/web/src/lib/api/healthApi.ts` (新增)
- `apps/web/src/lib/api/healthQueries.ts` (新增)
- `apps/web/src/components/HealthBanner.tsx` (新增)

## Change Log

- 2026-02-01: 实现 Health Banner 组件和相关 API 集成

