# Story 6.3: [BE/core] LLM Analyze Provider 封装（highlights/mindmap 可复用）

Status: ready-for-dev

## Story

As a 后端开发者,
I want 一个可替换的 LLM 调用封装（provider abstraction）,
so that highlights/mindmap 生成可以接入真实 LLM 且不污染 pipeline 主流程。

## Acceptance Criteria

1. Given `ANALYZE_PROVIDER=llm` When 执行 analyze 调用 Then 能通过统一接口完成一次 LLM 请求并返回结构化 JSON（由调用方定义 schema），且**不在日志/错误中泄露 API Key/敏感提示词**。
2. Given 未配置 Key/Endpoint When `ANALYZE_PROVIDER=llm` Then analyze 失败返回 `error.code=JOB_STAGE_FAILED`，并在 `error.details` 中给出可归因信息（如 `reason=missing_credentials`）与建议动作。
3. Given LLM 请求超时/限流/额度不足 When 失败 Then 返回 `error.code` 为 `JOB_STAGE_FAILED` 或 `RESOURCE_EXHAUSTED`（不新增 error code），并在 `error.details` 中标注 `reason=timeout|rate_limited|quota_exhausted`。
4. Given `ANALYZE_PROVIDER` 非 llm（如 `rules`/空）When 调用 provider Then 不触发外部网络请求（允许后续 story 走 rules fallback）。
5. 单元测试覆盖：用 fake transport/stub client 断言（a）请求参数被正确构造（b）超时/限流等错误被映射为稳定 `error.details.reason`（c）日志输出不包含 key 字符串。

## Tasks / Subtasks

- [ ] 定义 analyze provider 接口：`generate_json(task_name, input_dict) -> dict`（或等价签名）(AC: 1)
- [ ] 增加 env 配置约定（不入 contracts）：`ANALYZE_PROVIDER`, `LLM_API_BASE`, `LLM_API_KEY`, `LLM_MODEL`, `LLM_TIMEOUT_S` (AC: 1,2,3)
- [ ] 实现最小 HTTP client（requests/httpx 二选一；必须可注入 fake transport）(AC: 1,5)
- [ ] 错误映射策略（timeout/rate limit/quota/invalid response）→ `error.details.reason` (AC: 2,3)
- [ ] 日志脱敏与 prompt/response 采样策略（默认不落全文，仅允许 debug 开关且脱敏）(AC: 1,5)

## Dev Notes

- 本 story **不修改 contracts**：只新增内部 env 与实现文件。
- 产物 schema 由调用方 story（6.4/7.2）约束；provider 只负责“拿到 JSON”。

### References

- _bmad-output/implementation-artifacts/6-2-be-core-highlights.md
- _bmad-output/implementation-artifacts/7-1-be-core-mindmap.md

## Dev Agent Record

### Agent Model Used

GPT-5.2
