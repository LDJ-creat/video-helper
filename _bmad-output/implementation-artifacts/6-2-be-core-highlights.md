# Story 6.2: [BE/core] 每章重点摘要（highlights）生成与持久化

Status: ready-for-dev

## Story

As a 用户,
I want 每章都有可复习的重点摘要,
so that 我能快速定位需要复听的部分。

## Acceptance Criteria

1. Given Chapters 已生成 When 执行 `analyze`（highlights）Then 为每章生成 highlights 列表并持久化，每条 highlight 关联 `chapterId` 或 `timeMs`。
2. Given 模型/资源/内容异常 When 失败 Then 返回结构化错误并给出建议动作（检查模型配置/降低并发/缩短视频等）。

## Tasks / Subtasks

- [ ] 定义 highlights schema：`chapterId`, `items[]`，item 至少含 `text`，可选 `timeMs`, `confidence?` (AC: 1)
- [ ] 生成策略（MVP）：基于 transcript+chapter 范围提炼要点（先保证可用与可解释失败）(AC: 1)
- [ ] 持久化位置：Result 组合前可存中间产物表或 job artifacts (AC: 1)
- [ ] 错误码与建议动作：provider/key/资源不足/内容异常 (AC: 2)

## Dev Notes

- Chapters 为唯一准则：任何 highlight 必须可追溯到 chapterId/timeMs。
- 统一标准见：_bmad-output/implementation-artifacts/00-standards-and-parallel-plan.md

### References

- _bmad-output/planning-artifacts/epics.md
- _bmad-output/planning-artifacts/prd.md

## Dev Agent Record

### Agent Model Used

GPT-5.2
