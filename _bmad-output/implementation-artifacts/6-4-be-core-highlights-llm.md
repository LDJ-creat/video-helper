# Story 6.4: [BE/core] 真实 LLM 生成 highlights（analyze/highlights）

Status: ready-for-dev

## Story

As a 用户,
I want 系统基于 transcript + chapters 调用 LLM 生成每章 highlights,
so that highlights 能真实反映内容而非仅规则采样。

## Acceptance Criteria

1. Given transcript + chapters 已存在 When 执行 analyze(highlights) 且 `ANALYZE_PROVIDER=llm` Then 生成并持久化 highlights 列表：每条至少包含 `highlightId/chapterId/idx/text`，可选 `timeMs`，且 `chapterId` 必须来自既有 chapters（不允许新增未知 chapterId）。
2. Given LLM 返回不合法 JSON/字段缺失 When 解析失败 Then analyze 失败返回 `error.code=JOB_STAGE_FAILED`，`error.details.reason=invalid_llm_output`，并保留安全的 debug 摘要（不含敏感信息）。
3. Given `ANALYZE_PROVIDER!=llm` 或 LLM 不可用且 `ANALYZE_ALLOW_RULES_FALLBACK=1` When 执行 Then 使用 rules fallback 生成 highlights，确保 pipeline 可继续跑通（仍满足 6.2 schema）。
4. Given 任一 highlight 带 `timeMs` When 返回/落库 Then `timeMs` 必须落在对应 chapter 的 `[startMs, endMs)` 范围内；否则要被纠正为 `null` 或触发失败（策略需在实现中固定）。
5. 单元测试覆盖：
   - LLM 正常返回：highlights shape/idx 连续、chapterId 归属正确。
   - LLM 返回脏数据：触发 `invalid_llm_output`。
   - fallback 生效：无 key 时可在开关开启情况下继续产出。

## Tasks / Subtasks

- [ ] 定义 prompt 输入：按 chapter 切片提供（章节标题+时间范围+该章 transcript 文本）(AC: 1)
- [ ] 定义 LLM 输出 JSON schema（仅内部约束，不入 contracts）：`items:[{text,timeMs?}]` 或直接生成 ResultDTO 的 `highlights[]` (AC: 1)
- [ ] 输出规范化：生成稳定 `highlightId`（例如 `h_{chapterId}_{idx}`）与 `idx` (AC: 1)
- [ ] 质量/安全：限制输入长度（token/字符裁剪），避免超大视频直接 OOM/超时 (AC: 1,2)
- [ ] fallback：规则化提取实现（必须 deterministic）(AC: 3)

## Dev Notes

- 本 story **不修改 contracts**：对外 schema 仍以现有 ResultDTO/HighlightDTO 为准。
- stage 映射：internal stage 使用 `highlights`（public stage=analyze）。

### References

- _bmad-output/implementation-artifacts/6-2-be-core-highlights.md
- services/core/src/core/schemas/results.py

## Dev Agent Record

### Agent Model Used

GPT-5.2
