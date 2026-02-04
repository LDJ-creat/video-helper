# Story 6.3: [BE/core] LLM Analyze Provider 封装（highlights/mindmap 可复用）

Status: review

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

- [x] 定义 analyze provider 接口：`generate_json(task_name, input_dict) -> dict`（或等价签名）(AC: 1)
- [x] 增加 env 配置约定（不入 contracts）：`ANALYZE_PROVIDER`, `LLM_API_BASE`, `LLM_API_KEY`, `LLM_MODEL`, `LLM_TIMEOUT_S` (AC: 1,2,3)
- [x] 实现最小 HTTP client（requests/httpx 二选一；必须可注入 fake transport）(AC: 1,5)
- [x] 错误映射策略（timeout/rate limit/quota/invalid response）→ `error.details.reason` (AC: 2,3)
- [x] 日志脱敏与 prompt/response 采样策略（默认不落全文，仅允许 debug 开关且脱敏）(AC: 1,5)

## Dev Notes

- 本 story **不修改 contracts**：只新增内部 env 与实现文件。
- 产物 schema 由调用方 story（6.4/7.2）约束；provider 只负责“拿到 JSON”。

### References

- _bmad-output/implementation-artifacts/6-2-be-core-highlights.md
- _bmad-output/implementation-artifacts/7-1-be-core-mindmap.md

## Dev Agent Record

### Agent Model Used

GPT-5.2

### Implementation Notes

- 新增可复用 LLM provider：OpenAI-compatible `POST {LLM_API_BASE}/v1/chat/completions`（若 `LLM_API_BASE` 已含路径则直接使用）。
- 统一错误映射：
	- `401` → `JOB_STAGE_FAILED`, `reason=missing_credentials`
	- `429` → `JOB_STAGE_FAILED`, `reason=rate_limited`
	- `402/403` → `RESOURCE_EXHAUSTED`, `reason=quota_exhausted`
	- timeout → `JOB_STAGE_FAILED`, `reason=timeout`
	- 非法 JSON/响应 → `JOB_STAGE_FAILED`, `reason=invalid_llm_output`
- 安全：`AnalyzeError.__str__` 只返回安全 message；可选 `LLM_DEBUG=1` 时仅在 `error.details.debug` 记录 hash/len/endpoint/model，不记录原始 prompt/response。

### Tests

- `services/core/tests/test_analyze_llm.py` 覆盖：请求构造、429 映射、missing credentials、以及不泄露 key（断言字符串不包含 key）。

## File List

- services/core/src/core/app/pipeline/analyze_provider.py
- services/core/app/worker/worker_loop.py
- services/core/tests/test_analyze_llm.py
- .gitignore

## Change Log

- 2026-02-03: 新增 LLM Analyze provider 封装（httpx + 可注入 transport），并补齐单测与脱敏策略。
