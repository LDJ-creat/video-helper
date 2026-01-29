# Story 10.2: [FE/web] 搜索 UI（输入、结果列表、定位跳转）

Status: ready-for-dev

## Story

As a 用户,
I want 在 UI 中搜索并跳转到对应项目/章节,
so that 我能用“检索”替代翻找。

## Acceptance Criteria

1. Given 输入关键词并提交 When 返回结果 Then 可点击打开对应项目（或定位到章节）。

## Tasks / Subtasks

- [ ] 搜索输入框 + debounce（可选）+ 提交 (AC: 1)
- [ ] 结果列表：分页/加载更多（cursor）(AC: 1)
- [ ] 点击结果：跳转到 project 或带 chapter 定位参数 (AC: 1)

## Dev Notes

- 搜索结果 DTO 与分页形态必须与统一标准一致。

### References

- _bmad-output/planning-artifacts/epics.md

## Dev Agent Record

### Agent Model Used

GPT-5.2
