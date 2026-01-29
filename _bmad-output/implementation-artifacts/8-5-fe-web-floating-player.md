# Story 8.5: [FE/web] 智能悬浮播放器（Intersection Observer）

Status: ready-for-dev

## Story

As a 用户,
I want 当我滚动到笔记/导图区时视频自动悬浮,
so that 我不会丢失上下文。

## Acceptance Criteria

1. Given 主播放器滚出视口顶部 When Intersection Observer 触发 Then 播放器进入悬浮态（右下角、固定尺寸 16:9、带最小控制）。
2. When 点击 Expand Then 平滑滚动回顶部并恢复原位。

## Tasks / Subtasks

- [ ] 用 Intersection Observer 监听主播放器容器可见性 (AC: 1)
- [ ] 实现悬浮 player 容器（position fixed）与最小 controls (AC: 1)
- [ ] Expand 行为：scroll into view + focus 管理 (AC: 2)

## Dev Notes

- 需要保证不会造成重复音视频实例：建议复用同一个 player instance 或在悬浮/原位间切换容器。

### References

- _bmad-output/planning-artifacts/ux-design-specification.md
- _bmad-output/planning-artifacts/epics.md

## Dev Agent Record

### Agent Model Used

GPT-5.2
