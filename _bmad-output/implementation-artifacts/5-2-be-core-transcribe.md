# Story 5.2: [BE/core] 转写 stage（transcribe）产出 transcript

Status: ready-for-dev

## Story

As a 用户,
I want 系统对视频执行转写并产出带时间戳的 transcript,
so that 后续可以进行章节切片与重点提炼。

## Acceptance Criteria

1. Given Job 进入 transcribe stage When 转写成功 Then transcript 被持久化（DB 或文件 + DB 引用），时间戳单位为 ms；stage/progress 在状态接口与 SSE 可观察。
2. Given 转写失败 When 失败 Then Job 进入 failed 且 error code 可归因（依赖/模型/资源不足/内容异常）。

## Tasks / Subtasks

- [ ] 选择转写实现（先走最小可运行路径；可替换 provider）(AC: 1)
- [ ] transcript schema：分段+时间戳（ms），可支持后续 segment (AC: 1)
- [ ] stage/progress 更新：对外 stage=transcribe，progress 单调推进 (AC: 1)
- [ ] 失败归因错误码与建议动作（与 health/settings 对齐）(AC: 2)

## Dev Notes

- MVP 关键是“能跑通 + 可归因失败 + 可观测进度”，质量可后续迭代。
- 避免在日志/错误中泄露 Key。

### References

- _bmad-output/planning-artifacts/epics.md
- _bmad-output/planning-artifacts/prd.md

## Dev Agent Record

### Agent Model Used

GPT-5.2
