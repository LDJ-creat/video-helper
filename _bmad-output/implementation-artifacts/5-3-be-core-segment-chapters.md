# Story 5.3: [BE/core] 章节切片 stage（segment）产出 Chapters

Status: ready-for-dev

## Story

As a 用户,
I want 系统基于 transcript 生成章节列表,
so that 章节成为 UI 跳转与所有产物的唯一准则。

## Acceptance Criteria

1. Given transcript 已存在 When segment 成功 Then 生成 Chapters 列表并持久化，包含 `chapterId`, `startMs`, `endMs`, `title`, `summary`。
2. 保证 `startMs < endMs`，章节顺序稳定（idx 或按 startMs 排序），且 `chapterId` 在后续产物引用中保持稳定。

## Tasks / Subtasks

- [ ] 定义 Chapters schema 与持久化方式（表/JSON 字段）(AC: 1,2)
- [ ] 实现 segment 算法（先最小可用：按时长/话题粗分，后续可改进）(AC: 1)
- [ ] 数据校验：时间范围、排序、非重叠（选择策略并写清错误码）(AC: 2)
- [ ] stage/progress：对外 stage=segment，可观察推进 (AC: 1)

## Dev Notes

- Chapters 是唯一准则：highlights/mindmap/keyframes/跳转必须引用 chapterId/startMs/endMs。

### References

- _bmad-output/planning-artifacts/epics.md
- _bmad-output/planning-artifacts/prd.md

## Dev Agent Record

### Agent Model Used

GPT-5.2
