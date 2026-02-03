# Story 7.1: [BE/core] Mindmap schema 定义与生成（nodes/edges）

Status: review

## Story

As a 用户,
I want 系统生成可视化的思维导图,
so that 我能以结构化方式理解视频内容。

## Acceptance Criteria

1. Given Chapters 已生成 When 执行 `analyze`（mindmap）Then 生成 mindmap graph（nodes/edges）并持久化到 Result 或中间产物。
2. 节点必须可追溯到 `chapterId`（至少章节点/根节点具备关联），字段结构稳定，避免前后端各自发挥。

## Tasks / Subtasks

- [x] 冻结最小 mindmap schema：
  - node：`id, type, label, chapterId?, position?, data?`
  - edge：`id, source, target, label?`
  (AC: 1,2)
- [x] 生成策略（MVP）：先保证“章 → 要点 → 子要点”层级可渲染；布局可后续优化 (AC: 1)
- [x] 持久化：与 Result 组合字段兼容（8.3）(AC: 1)

## Dev Notes

- 强烈建议把 schema 放到统一 contracts 中（后端+前端一致）。
- 统一标准见：_bmad-output/implementation-artifacts/00-standards-and-parallel-plan.md

### References

- _bmad-output/planning-artifacts/epics.md

## Dev Agent Record

### Agent Model Used

GPT-5.2
