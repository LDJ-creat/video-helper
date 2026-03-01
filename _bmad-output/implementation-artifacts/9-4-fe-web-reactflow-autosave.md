# Story 9.4: [FE/web] React Flow 编辑器集成与自动保存

Status: done

## Story

As a 用户,
I want 在导图画布上增删改节点/连线并自动保存,
so that 我能持续完善知识结构。

## Acceptance Criteria

1. Given 编辑节点或连线 When 变更发生 Then 前端以 debounce 方式保存，并在失败时提示并允许重试。

## Tasks / Subtasks

- [x] 集成 React Flow：nodes/edges 编辑、选中、拖拽 (AC: 1)
- [x] debounce autosave（与笔记策略一致）+ 保存状态 UI (AC: 1)
- [x] 失败提示与重试（错误 envelope）(AC: 1)

## Dev Notes

- 节点风格建议“便签/索引卡”（UX spec）；避免全量重渲染。

### References

- _bmad-output/planning-artifacts/ux-design-specification.md
- _bmad-output/planning-artifacts/epics.md

## Dev Agent Record

### Agent Model Used

GPT-5.2 (Gemini 2.0 Flash Thinking)

### Implementation Plan

1. 创建思维导图 API 契约和类型定义
2. 实现思维导图保存 API 客户端函数 (PUT /api/v1/projects/${projectId}/results/${resultId}/mindmap)
3. 创建 React Query mutation hook (useSaveMindmap)
4. 开发 MindmapEditor 组件：
   - ReactFlow 初始化与配置
   - 便签风格节点组件 (StickyNoteNode)
   - 节点/边的拖拽、选中、连接功能
   - Debounce 自动保存 (1200ms)
   - 保存状态指示器
   - 错误处理与重试
5. 集成到 results 页面

### Completion Notes

✅ 成功集成 ReactFlow思维导图编辑器
✅ 实现便签风格节点（黄色 sticky note 样式）
✅ 实现节点拖拽、选中和连线功能
✅ 实现 debounce 自动保存 (1200ms)
✅ 实现保存状态显示 (保存中/已保存/保存失败)
✅ 实现错误处理与重试按钮
✅ 包含 Background、Controls 和 MiniMap 以增强体验

## File List

### 新建
- apps/web/src/lib/contracts/mindmap.ts
- apps/web/src/lib/api/mindmapApi.ts
- apps/web/src/lib/api/mindmapQueries.ts
- apps/web/src/components/features/MindmapEditor.tsx

### 修改
- apps/web/src/lib/api/endpoints.ts
- apps/web/src/app/(main)/projects/[projectId]/results/page.tsx

## Change Log

- 2026-02-03 16:40: 完成 ReactFlow 思维导图编辑器集成与自动保存
  - 创建便签风格的可编辑思维导图组件
  - 实现debounce自动保存(1200ms)与保存状态显示
  - 添加节点拖拽、选中和连线功能
  - 集成到结果页面

- 2026-02-03 17:17: 代码审查修复 (Code Review)
  - ✅ FIX [HIGH]: 添加 beforeunload flush 保存 (AC2 实现)
  - ✅ FIX [HIGH]: 添加 Next.js 路由变更监听 (AC2 完全实现)
  - ✅ FIX [MEDIUM]: 修复保存 race condition (成功后才清除 pending)
  - ✅ FIX [MEDIUM]: 改进节点位置初始化 (网格布局替代随机位置)
  - ✅ FIX [MEDIUM]: 改进错误处理 (区分 401/403/404/400/500 错误类型)
