# Story 9.2: [FE/web] TipTap 编辑器集成与自动保存（debounce + flush）

Status: ready-for-dev

## Story

As a 用户,
I want 在结果页编辑笔记并自动保存,
so that 我能流畅整理知识卡片。

## Acceptance Criteria

1. Given 在编辑器输入 When 停止输入超过 800–1500ms Then 自动触发保存并显示“保存中/已保存/保存失败”。
2. Given 路由切换/关闭页面 When 有未提交变更 Then best-effort flush 一次保存。

## Tasks / Subtasks

- [ ] 集成 TipTap（或既有编辑器组件）并输出 JSON 文档 (AC: 1)
- [ ] debounce autosave（800–1500ms）+ 显示保存状态 (AC: 1)
- [ ] beforeunload/route change flush 保存（避免丢失）(AC: 2)
- [ ] 错误 envelope 展示与重试 (AC: 1)

## Dev Notes

- 编辑器本地状态不要放 React Query；只把 server-state 放进去（避免重渲染）。

### References

- _bmad-output/planning-artifacts/epics.md
- _bmad-output/planning-artifacts/prd.md

## Dev Agent Record

### Agent Model Used

GPT-5.2
