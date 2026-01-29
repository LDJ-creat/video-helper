# Story 8.6: [FE/web] 章节跳转播放 + 关键帧跳转

Status: ready-for-dev

## Story

As a 用户,
I want 点击章节或关键帧即可跳转到对应时间播放,
so that 复习不再依赖拖进度条。

## Acceptance Criteria

1. Given chapters 存在 startMs/endMs When 点击章节 Then 播放器 seek 到 startMs 并继续播放（按产品默认）。
2. Given keyframe asset 关联 timeMs When 点击关键帧 Then 播放器 seek 到 timeMs。

## Tasks / Subtasks

- [ ] 章节列表点击：调用 player seek API（ms→seconds 转换准确）(AC: 1)
- [ ] 关键帧卡片点击：读取 timeMs 并 seek (AC: 2)
- [ ] UI 状态：当前章节高亮/滚动到可视区域（可选）(AC: 1)

## Dev Notes

- 时间单位统一：后端 ms，前端播放器通常 seconds；转换必须单点封装。

### References

- _bmad-output/planning-artifacts/epics.md

## Dev Agent Record

### Agent Model Used

GPT-5.2
