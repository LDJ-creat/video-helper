# Story 9.4: [FE/web] React Flow 编辑器集成与自动保存

Status: ready-for-dev

## Story

As a 用户,
I want 在导图画布上增删改节点/连线并自动保存,
so that 我能持续完善知识结构。

## Acceptance Criteria

1. Given 编辑节点或连线 When 变更发生 Then 前端以 debounce 方式保存，并在失败时提示并允许重试。

## Tasks / Subtasks

- [ ] 集成 React Flow：nodes/edges 编辑、选中、拖拽 (AC: 1)
- [ ] debounce autosave（与笔记策略一致）+ 保存状态 UI (AC: 1)
- [ ] 失败提示与重试（错误 envelope）(AC: 1)

## Dev Notes

- 节点风格建议“便签/索引卡”（UX spec）；避免全量重渲染。

### References

- _bmad-output/planning-artifacts/ux-design-specification.md
- _bmad-output/planning-artifacts/epics.md

## Dev Agent Record

### Agent Model Used

GPT-5.2
