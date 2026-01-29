# Story 3.4: [BE/core] 视频元信息抽取与持久化（duration/format）

Status: ready-for-dev

## Story

As a 用户,
I want 项目详情能显示视频时长等基础信息,
so that 我能预期分析与复习成本。

## Acceptance Criteria

1. Given Job 创建完成 When 服务抽取元信息 Then durationMs/format 等元数据持久化到 Project 或关联表。
2. Given 抽取失败 When 失败 Then 返回可归因错误 code（依赖缺失/文件不可读等）。

## Tasks / Subtasks

- [ ] 选择元信息抽取方式（ffprobe/ffmpeg best-effort）(AC: 1)
- [ ] 持久化字段：durationMs/format（可选扩展 width/height/fps）(AC: 1)
- [ ] 失败归因：依赖缺失 vs 文件不可读 vs 解析失败 (AC: 2)

## Dev Notes

- health(1.1) 的依赖探测应复用；错误码保持一致。

### References

- _bmad-output/planning-artifacts/epics.md

## Dev Agent Record

### Agent Model Used

GPT-5.2
