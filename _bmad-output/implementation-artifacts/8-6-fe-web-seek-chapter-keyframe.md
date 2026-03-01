# Story 8.6: [FE/web] 章节跳转播放 + 关键帧跳转

Status: completed

## Story

As a 用户,
I want 点击章节或关键帧即可跳转到对应时间播放,
so that 复习不再依赖拖进度条。

## Acceptance Criteria

1. Given chapters 存在 startMs/endMs When 点击章节 Then 播放器 seek 到 startMs 并继续播放（按产品默认）。
2. Given keyframe asset 关联 timeMs When 点击关键帧 Then 播放器 seek 到 timeMs。

## Tasks / Subtasks

- [x] 章节列表点击：调用 player seek API（ms→seconds 转换准确）(AC: 1)
- [x] 关键帧卡片点击：读取 timeMs 并 seek (AC: 2)
- [x] UI 状态：当前章节高亮/滚动到可视区域（可选）(AC: 1)

## Dev Notes

- 时间单位统一：后端 ms，前端播放器通常 seconds；转换必须单点封装。

### References

- _bmad-output/planning-artifacts/epics.md

## Dev Agent Record

### Agent Model Used

Claude 3.7 Sonnet (Antigravity)

### Implementation Summary

- 创建 `timeUtils.ts` 封装时间转换函数：`msToSeconds()`, `secondsToMs()`, `formatTime()`
- `VideoPlayer` 组件暴露 `seekTo(timeMs)` 方法（内部转换 ms → seconds）
- `ChapterList` 和 `KeyframeGrid` 组件的 `onClick` 触发 `handleSeek(timeMs)`
- `results/page.tsx` 中统一处理：`videoPlayerRef.current?.seekTo(timeMs)` + `play()`
- 当前章节高亮：根据 `currentTimeMs` 判断在哪个章节范围内（`startMs <= currentTimeMs < endMs`）

### Technical Decisions

- **时间转换单点封装**：所有 ms/seconds 转换统一在 `timeUtils.ts`
- **自动播放**：章节/关键帧跳转后自动调用 `play()`，符合用户预期
- **高亮逻辑**：实时计算当前章节，橙色背景 + 脉冲点
- **滚动到可视区域**：标记为可选（当前点击即可跳转，交互已足够）

## File List

- apps/web/src/lib/utils/timeUtils.ts
- apps/web/src/components/features/VideoPlayer.tsx
- apps/web/src/components/features/ChapterList.tsx
- apps/web/src/components/features/KeyframeGrid.tsx
- apps/web/src/app/(main)/projects/[projectId]/results/page.tsx
