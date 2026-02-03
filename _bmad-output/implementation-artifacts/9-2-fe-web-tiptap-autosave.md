# Story 9.2: [FE/web] TipTap 编辑器集成与自动保存（debounce + flush）

Status: done

## Story

As a 用户,
I want 在结果页编辑笔记并自动保存,
so that 我能流畅整理知识卡片。

## Acceptance Criteria

1. Given 在编辑器输入 When 停止输入超过 800–1500ms Then 自动触发保存并显示“保存中/已保存/保存失败”。
2. Given 路由切换/关闭页面 When 有未提交变更 Then best-effort flush 一次保存。

## Tasks / Subtasks

- [x] 集成 TipTap（或既有编辑器组件）并输出 JSON 文档 (AC: 1)
- [x] debounce autosave（800–1500ms）+ 显示保存状态 (AC: 1)
- [x] beforeunload/route change flush 保存（避免丢失）(AC: 2)
- [x] 错误 envelope 展示与重试 (AC: 1)

## Dev Notes

- 编辑器本地状态不要放 React Query；只把 server-state 放进去（避免重渲染）。

### References

- _bmad-output/planning-artifacts/epics.md
- _bmad-output/planning-artifacts/prd.md

## Dev Agent Record

### Agent Model Used

GPT-5.2 (Gemini 2.0 Flash Thinking)

### Implementation Plan

1. 安装 TipTap 依赖 (@tiptap/react, @tiptap/starter-kit)
2. 创建笔记 API 契约和类型定义
3. 实现笔记保存 API 客户端函数 (PUT /api/v1/projects/${projectId}/results/${resultId}/note)
4. 创建 React Query mutation hook (useSaveNote)
5. 开发 NoteEditor 组件，包括：
   - TipTap 编辑器初始化
   - Debounce 自动保存 (1200ms)
   - 保存状态指示器 (idle/saving/saved/error)
   - beforeunload/unmount 时 flush 保存
   - 错误处理与重试功能
6. 集成编辑器到 results 页面

### Completion Notes

✅ 成功集成 TipTap 编辑器到结果页面
✅ 实现 debounce 自动保存机制 (1200ms，符合 AC 的 800-1500ms 范围)
✅ 实现保存状态显示 (保存中/已保存/保存失败) with timestamps
✅ 实现 beforeunload handler with sendBeacon for best-effort flush
✅ 实现错误显示与重试按钮
✅ 遵循 Dev Notes：编辑器本地状态不放 React Query,使用 useState 管理

## File List

### 新建
- apps/web/src/lib/contracts/notes.ts
- apps/web/src/lib/api/noteApi.ts
- apps/web/src/lib/api/noteQueries.ts
- apps/web/src/components/features/NoteEditor.tsx

### 修改
- apps/web/src/lib/api/endpoints.ts (新增 saveNote endpoint)
- apps/web/src/app/(main)/projects/[projectId]/results/page.tsx (集成 NoteEditor)
- apps/web/package.json (新增 TipTap 依赖)

## Change Log

- 2026-02-03 16:00: 完成 TipTap 编辑器集成与自动保存功能
  - 安装并配置 TipTap 编辑器
  - 实现debounce自动保存(1200ms)与保存状态显示
  - 实现 beforeunload flush 保存机制
  - 添加错误处理与重试功能
  - 集成到结果页面

- 2026-02-03 17:17: 代码审查修复 (Code Review)
  - ✅ FIX [HIGH]: 添加 Next.js 路由变更监听 (AC2 完全实现)
  - ✅ FIX [HIGH]: sendBeacon 改为 fetch with keepalive (支持 headers)
  - ✅ FIX [MEDIUM]: 修复保存 race condition (成功后才清除 pending)
  - ✅ FIX [MEDIUM]: 改进错误处理 (区分 401/403/404/400/500 错误类型)

