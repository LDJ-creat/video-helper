# Story 2.3: [BE/core] 删除项目（级联清理 DB + DATA_DIR 资源）

Status: ready-for-dev

## Story

As a 用户,
I want 删除一个项目并清理其关联数据与资源,
so that 本地空间不会被长期占用。

## Acceptance Criteria

1. Given 项目存在且包含 results/assets/chapters 等关联记录 When 删除项目 Then 关联 DB 记录被删除/标记不可见，并安全删除 DATA_DIR 下项目目录（不允许越界）。
2. Given 删除过程中出现文件占用/权限问题 When 处理删除 Then 返回结构化错误 envelope 且不泄露绝对路径。

## Tasks / Subtasks

- [ ] 实现项目删除 endpoint（路径与 api.md/统一约束对齐）(AC: 1,2)
- [ ] DB 级联策略：事务内删除记录 + best-effort 文件清理 (AC: 1)
- [ ] safe-delete：仅允许 DATA_DIR 内相对路径 (AC: 1)
- [ ] 错误 code：权限/占用/不存在等清晰可归因 (AC: 2)

## Dev Notes

- 路径安全规则：_bmad-output/implementation-artifacts/00-standards-and-parallel-plan.md

### References

- _bmad-output/planning-artifacts/epics.md

## Dev Agent Record

### Agent Model Used

GPT-5.2
