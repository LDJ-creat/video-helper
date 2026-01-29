# Story 6.1: [BE/core] 关键帧抽取与 assets 持久化

Status: ready-for-dev

## Story

As a 用户,
I want 系统为每章生成关键帧截图并可关联到时间点,
so that 我能用视觉锚点快速回忆上下文。

## Acceptance Criteria

1. Given Chapters 已生成 When 执行 `extract_keyframes` Then 关键帧图片生成并落在 `DATA_DIR` 受控目录；DB 为每张图创建 asset 记录（仅相对路径）并关联 `projectId/chapterId` 与可选 `timeMs`。
2. Given ffmpeg 不可用 When 抽取关键帧 Then Job 失败并返回可归因错误 code（与 health 自检一致）。

## Tasks / Subtasks

- [ ] 定义 keyframe asset 记录字段：`assetId, projectId, chapterId, timeMs?, relPath, mimeType, width?, height?, createdAtMs` (AC: 1)
- [ ] 关键帧抽取策略（MVP）：每章 N 帧（例如 3-5）或按时间间隔采样；输出稳定可复现 (AC: 1)
- [ ] 落盘路径：`DATA_DIR/projects/{projectId}/assets/...`（仅相对路径入库）(AC: 1)
- [ ] 错误归因：缺 ffmpeg/执行失败/输出不可读等 (AC: 2)

## Dev Notes

- 路径安全与 assets 访问路由在 8.2 完成；本 story 只负责产出与落库。
- 统一标准见：_bmad-output/implementation-artifacts/00-standards-and-parallel-plan.md

### References

- _bmad-output/planning-artifacts/epics.md

## Dev Agent Record

### Agent Model Used

GPT-5.2
