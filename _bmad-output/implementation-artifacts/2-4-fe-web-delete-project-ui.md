# Story 2.4: [FE/web] 删除项目交互（确认、反馈、回收列表状态）

Status: ready-for-dev

## Story

As a 用户,
I want 在 UI 中安全地删除项目,
so that 我不误删且能明确看到结果。

## Acceptance Criteria

1. Given 点击“删除项目” When 弹出确认对话框 Then 必须确认后才发起删除请求；成功后项目从列表/缓存移除并提示成功。
2. Given 删除失败 When 接收错误 envelope Then UI 显示可理解提示并允许重试。

## Tasks / Subtasks

- [ ] 删除按钮 + confirm dialog (AC: 1)
- [ ] 成功后更新 React Query cache / invalidate (AC: 1)
- [ ] 错误 envelope 展示与重试 (AC: 2)

## Dev Notes

- 错误 envelope/字段命名：_bmad-output/implementation-artifacts/00-standards-and-parallel-plan.md

### References

- _bmad-output/planning-artifacts/epics.md

## Dev Agent Record

### Agent Model Used

GPT-5.2
