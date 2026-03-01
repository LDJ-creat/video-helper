# Story 7.2: [BE/core] 真实 LLM 生成 mindmap（analyze/mindmap）

Status: review

## Story

As a 用户,
I want 系统基于 chapters + highlights 调用 LLM 生成可渲染的 mindmap 图,
so that 我能以结构化导图理解视频内容。

## Acceptance Criteria

1. Given chapters + highlights 已生成 When 执行 analyze(mindmap) 且 `ANALYZE_PROVIDER=llm` Then 生成 mindmap：包含 `nodes[]/edges[]`，至少包含根节点与每章节点；章节点必须可追溯到 `chapterId`（字段或 data 内嵌均可，但必须稳定）。
2. Given mindmap 输出 schema 不合法（缺 nodes/edges、id 重复、edge 引用不存在节点）When 校验失败 Then analyze 失败返回 `error.code=JOB_STAGE_FAILED`，`error.details.reason=invalid_llm_output`。
3. Given `ANALYZE_PROVIDER!=llm` 或 LLM 不可用且 `ANALYZE_ALLOW_RULES_FALLBACK=1` When 执行 Then 用 rules fallback 生成 mindmap（root→chapter→highlights），确保可渲染。
4. mindmap 节点/边 id 必须稳定且可复现：同一输入重跑输出 id 不变（至少对 root/chapter 节点）。
5. 单元测试覆盖：
   - LLM 正常输出通过校验。
   - 脏输出（edge 指向不存在 node / 重复 id）触发 `invalid_llm_output`。
   - fallback mindmap 可渲染且章节点可追溯。

## Tasks / Subtasks

- [x] 定义 prompt 输入：章列表（chapterId/title/summary）+ highlights（按章聚合） (AC: 1)
- [x] 定义 LLM 输出 JSON schema（内部约束，不入 contracts） (AC: 1)
- [x] mindmap 校验器：nodes/edges 基本一致性校验 + 去重策略 (AC: 2)
- [x] fallback：root→chapter→highlight 节点生成（deterministic id） (AC: 3,4)

## Dev Notes

- 本 story **不修改 contracts**：输出仍符合现有 `MindmapDTO`（nodes/edges 为 list[dict]）。
- stage 映射：internal stage 使用 `mindmap`（public stage=analyze）。

### References

- _bmad-output/implementation-artifacts/7-1-be-core-mindmap.md
- services/core/src/core/schemas/results.py

## Dev Agent Record

### Agent Model Used

GPT-5.2

### Implementation Notes

- `ANALYZE_PROVIDER=llm` 时：先让 LLM 输出每章 topics 计划（内部 schema：`{chapters:[{chapterId, topics:[{label}]}]}`），再组装为可渲染 graph（`nodes[]/edges[]`）。
- 节点稳定性：root/chapter 节点 id 固定为 `node_root` / `node_ch_{chapterId}`；topic 节点/边 id 使用内容 hash 生成；topics 做 case-insensitive 去重。
- 校验器：
   - nodes/edges 必须为 list
   - node id 唯一
   - edge source/target 必须引用存在 node
   - 失败统一映射 `JOB_STAGE_FAILED` + `reason=invalid_llm_output`
- fallback：当 `ANALYZE_PROVIDER!=llm`，或 llm 不可用且 `ANALYZE_ALLOW_RULES_FALLBACK=1` 时，回退到 deterministic graph（root→chapter→highlights）。

### Tests

- `services/core/tests/test_analyze_llm.py` 覆盖：正常输出通过校验、非法 chapterId 输出触发 `invalid_llm_output`、fallback 可渲染。

## File List

- services/core/src/core/app/pipeline/mindmap.py
- services/core/src/core/app/worker/worker_loop.py
- services/core/tests/test_analyze_llm.py

## Change Log

- 2026-02-03: analyze(mindmap) 接入真实 LLM 调用、增加 mindmap 校验器与 fallback，并补齐单测。
