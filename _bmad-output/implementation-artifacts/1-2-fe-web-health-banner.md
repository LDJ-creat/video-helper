# Story 1.2: [FE/web] 启动自检提示（Health Banner）

Status: ready-for-dev

## Story

As a 用户,
I want 在创建分析前就看到依赖是否就绪的提示,
so that 我不会提交后才发现缺依赖。

## Acceptance Criteria

1. Given 前端可访问后端 When 进入导入/创建任务页面 Then 调用 `GET /api/v1/health` 并展示清晰状态；异步加载不阻塞其它交互。
2. Given 健康检查缺依赖 When 查看提示 Then 显示可行动建议（安装 ffmpeg/yt-dlp 或检查模型配置）。

## Tasks / Subtasks

- [ ] 增加 health 查询（React Query）与缓存策略（页面进入即触发）(AC: 1)
- [ ] 实现 Health Banner 组件：loading/success/warn/error（网络不可用也要可理解）(AC: 1)
- [ ] 文案映射：按后端健康检查返回项渲染建议动作 (AC: 2)

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

GPT-5.2
