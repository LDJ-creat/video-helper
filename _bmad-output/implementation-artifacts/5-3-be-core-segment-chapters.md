# Story 5.3: [BE/core] 章节切片 stage（segment）产出 Chapters

Status: review

## Story

As a 用户,
I want 系统基于 transcript 生成章节列表,
so that 章节成为 UI 跳转与所有产物的唯一准则。

## Acceptance Criteria

1. Given transcript 已存在 When segment 成功 Then 生成 Chapters 列表并持久化，包含 `chapterId`, `startMs`, `endMs`, `title`, `summary`。
2. 保证 `startMs < endMs`，章节顺序稳定（idx 或按 startMs 排序），且 `chapterId` 在后续产物引用中保持稳定。

## Tasks / Subtasks

- [x] 定义 Chapters schema 与持久化方式（表/JSON 字段）(AC: 1,2)
- [x] 实现 segment 算法（先最小可用：按时长/话题粗分，后续可改进）(AC: 1)
- [x] 数据校验：时间范围、排序、非重叠（选择策略并写清错误码）(AC: 2)
- [x] stage/progress：对外 stage=segment，可观察推进 (AC: 1)

## Dev Notes

- Chapters 是唯一准则：highlights/mindmap/keyframes/跳转必须引用 chapterId/startMs/endMs。

### References

- _bmad-output/planning-artifacts/epics.md
- _bmad-output/planning-artifacts/prd.md

## Dev Agent Record

### Agent Model Used

GPT-5.2

### Completion Notes

- Chapters 持久化为 jobs.chapters（JSON），结构包含 chapterId/startMs/endMs/title/summary，单位 ms (AC: 1)
- segment MVP 算法按时长均分生成章节，chapterId 采用 deterministic "ch_{idx}"，保证重跑稳定 (AC: 2)
- 校验策略：必须非空、按 startMs 单调排序、startMs < endMs、章节不重叠；失败写入 jobs.error（code=JOB_STAGE_FAILED + details.reason）(AC: 2)
- worker 执行时 internal stage 置为 chapters（对外映射为 segment），SSE 可观察进度推进 (AC: 1)

### Tests

- 运行：`python -m unittest discover -s tests -p "test_*.py"`（全绿）

## File List

- services/core/src/core/app/pipeline/segment.py
- services/core/src/core/app/worker/worker_loop.py
- services/core/src/core/db/models/job.py
- services/core/src/core/db/session.py
- services/core/tests/test_pipeline_transcribe_segment.py

## Change Log

- 2026-02-02: 增加 segment stage（chapters 产出 + 校验 + chapterId 稳定）
