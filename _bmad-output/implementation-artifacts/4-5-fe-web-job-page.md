# Story 4.5: [FE/web] Job 详情页（进度条 + 阶段 + 日志）

Status: done

## Story

As a 用户,
I want 在 Job 详情页看到阶段化进度与日志,
so that 我能判断是否卡住、失败该怎么做。

## Acceptance Criteria

1. Given Job 运行中 When 打开 Job 详情页 Then 展示 `status/stage/progress` 的可视化与阶段说明。
2. Given Job 有日志 When 打开页面 Then 可按需加载并持续 tail 日志（滚动/自动追尾策略自定）。
3. Given Job 失败 When UI 展示错误 Then 显示可行动建议并提供“重试”入口（若后端支持）。

## Tasks / Subtasks

- [x] Job 详情页路由与数据加载（React Query：job + logs）(AC: 1,2)
- [x] 进度 UI：stage 映射到人类可读文案；progress bar (AC: 1)
- [x] 日志 UI：增量加载（cursor）+ 自动追尾（可选）(AC: 2)
- [x] 错误 envelope 展示：code/message/details 映射为建议动作 (AC: 3)
- [x] 重试按钮：调用后端重试接口（若实现 4.6）(AC: 3)

## Dev Notes

- 统一契约/字段名不可漂移，参见统一标准。

### References

- _bmad-output/planning-artifacts/epics.md
- _bmad-output/planning-artifacts/ux-design-specification.md

## Dev Agent Record

### Agent Model Used

Gemini 2.0 Flash Thinking Experimental

### Implementation Summary

实现了完整的 Job 详情页 UI：

1. **Job 详情页** (`(main)/jobs/[jobId]/page.tsx`)：集成所有组件，展示 Job 全貌
2. **JobProgress 组件** (`JobProgress.tsx`)：状态徽章 + 进度条
3. **JobError 组件** (`JobError.tsx`)：错误详情 + 重试按钮
4. **JobLogs 组件** (`JobLogs.tsx`)：增量日志加载 + 自动追尾

所有组件严格遵循统一契约和 AC 要求。

### Files Changed

- [NEW] `src/app/(main)/jobs/[jobId]/page.tsx` - Job 详情页路由
- [NEW] `src/components/JobProgress.tsx` - 进度组件
- [NEW] `src/components/JobError.tsx` - 错误展示组件
- [NEW] `src/components/JobLogs.tsx` - 日志组件

### Tests

TypeScript 编译通过 ✓
所有组件已标记 "use client" 指令 ✓
React 19 类型兼容性修复 ✓
