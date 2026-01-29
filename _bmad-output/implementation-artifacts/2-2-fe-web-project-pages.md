# Story 2.2: [FE/web] 项目列表页与项目详情页（含分页/虚拟化）

Status: ready-for-dev

## Story

As a 用户,
I want 在 Web 端浏览项目列表并进入项目详情,
so that 我可以快速切换不同视频的复习资产。

## Acceptance Criteria

1. Given 项目数量较多 When 滚动项目列表 Then 使用虚拟化或分段加载，保持交互流畅；翻页使用 cursor。
2. Given 某项目存在 `latestResultId` When 点击“打开” Then 路由到该项目结果页入口（未就绪则显示状态页）。

## Tasks / Subtasks

- [ ] Projects 列表页：React Query + cursor；必要时虚拟化/增量加载 (AC: 1)
- [ ] 项目详情页：展示来源/更新时间/latestResultId 等 (AC: 2)
- [ ] 打开按钮路由：latestResultId 有/无分支逻辑 (AC: 2)

## Dev Notes

- 可先按契约 mock；统一契约见：_bmad-output/implementation-artifacts/00-standards-and-parallel-plan.md

### References

- _bmad-output/planning-artifacts/epics.md
- _bmad-output/planning-artifacts/ux-design-specification.md

## Dev Agent Record

### Agent Model Used

GPT-5.2
