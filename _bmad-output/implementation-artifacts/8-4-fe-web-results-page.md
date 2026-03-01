# Story 8.4: [FE/web] 结果页三栏布局（Tri-Pane Focus）与基础渲染

Status: completed

## Story

As a 用户,
I want 在结果页同时看到视频与笔记/导图,
so that 我能边看边整理并快速复习。

## Acceptance Criteria

1. Given 打开项目结果页 When latest Result 可用 Then 以 Tri-Pane Focus 布局渲染：左侧视频/导图区域，右侧笔记区域。
2. Then 章节列表、重点、关键帧、导图至少有一种可见入口（tabs 或分区）。

## Tasks / Subtasks

- [x] 实现 results page 路由（项目维度）与数据加载（latest Result + assets refs）(AC: 1,2)
- [x] Tri-Pane layout：桌面优先；小屏可先降级为 tab/垂直堆叠（非 MVP 完整适配）(AC: 1)
- [x] 渲染 chapters/highlights/keyframes/mindmap（至少占位可用，逐步完善）(AC: 2)
- [x] 大列表内容：分页/虚拟化或分段渲染，避免卡顿 (AC: 2)

## Dev Notes

- UI 设计约束来源于 UX spec：Warm Minimalist、卡片/骨架屏、Tri-Pane Focus。
- Result/Assets 字段以 8.1 契约为准。

### References

- _bmad-output/planning-artifacts/ux-design-specification.md
- _bmad-output/planning-artifacts/epics.md

## Dev Agent Record

### Agent Model Used

Claude 3.7 Sonnet (Antigravity)

### Implementation Summary

- 创建 `/projects/:projectId/results` 路由，使用 `useLatestResult` hook 获取数据
- 实现 Tri-Pane 布局（grid-cols-12，左 7 列，右 5 列）
- 创建所有核心组件：ChapterList、KeyframeGrid、HighlightList、MindmapViewer
- 使用 React Flow 渲染思维导图（Sticky Notes 风格）
- 骨架屏加载状态、错误处理、重试功能
- 遵循 UX 规范的暖色调设计（#FDFBF7 背景，orange accent）

### Technical Decisions

- **Mindmap**: 使用 React Flow 库，只读模式，Root 节点橙色背景
- **Loading**: 骨架屏 + 中心加载指示器
- **Error Handling**: 友好错误提示 + 重试按钮

## File List

- apps/web/src/lib/contracts/resultTypes.ts
- apps/web/src/lib/api/resultApi.ts
- apps/web/src/lib/api/resultQueries.ts
- apps/web/src/lib/api/endpoints.ts
- apps/web/src/lib/api/queryKeys.ts
- apps/web/src/lib/utils/timeUtils.ts
- apps/web/src/components/features/ChapterList.tsx
- apps/web/src/components/features/KeyframeGrid.tsx
- apps/web/src/components/features/HighlightList.tsx
- apps/web/src/components/features/MindmapViewer.tsx
- apps/web/src/components/layout/ResultLayout.tsx
- apps/web/src/app/(main)/projects/[projectId]/results/page.tsx
- apps/web/package.json (新增 reactflow)
