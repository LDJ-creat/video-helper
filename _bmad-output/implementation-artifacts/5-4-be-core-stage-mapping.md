# Story 5.4: [BE/core] Stage 命名与进度映射对齐（api.md）

Status: ready-for-dev

## Story

As a 前端开发者,
I want 后端 stage 命名与进度事件稳定一致,
so that 前端无需猜测流程即可正确展示。

## Acceptance Criteria

1. Given Job 运行 When 观察 `GET /api/v1/jobs/{jobId}` 与 SSE `progress` 事件 Then `stage` 字段只使用已约定稳定名称集合。
2. `progress` 在 0..1 范围内（可为空但不可越界），并且对同一 stage 单调不回退（best-effort）。

## Tasks / Subtasks

- [ ] 冻结对外 stage 集合：`ingest/transcribe/segment/analyze/assemble_result/extract_keyframes` (AC: 1)
- [ ] 定义后端内部 stage → 对外 stage 的映射（如内部更细）(AC: 1)
- [ ] SSE progress 事件与 job 状态接口使用同一套 stage/progress 来源（避免漂移）(AC: 1,2)
- [ ] 前端文案映射建议输出（写入统一标准或 contracts）(AC: 1)

## Dev Notes

- 这是多 agent 并行的“冲突热点”，必须先冻结再开发其它 story。
- 统一标准见：_bmad-output/implementation-artifacts/00-standards-and-parallel-plan.md

### References

- _bmad-output/planning-artifacts/epics.md
- api.md

## Dev Agent Record

### Agent Model Used

GPT-5.2
