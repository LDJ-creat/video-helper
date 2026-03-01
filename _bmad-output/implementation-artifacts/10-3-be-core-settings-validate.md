# Story 10.3: [BE/core] 模型/Provider 设置读取与校验（非敏感）

Status: ready-for-dev

## Story

As a 运维/高级用户,
I want 配置 provider/baseUrl/model 等参数并在无效时得到明确提示,
so that 分析失败可归因且可行动。

## Acceptance Criteria

1. Given 读取设置 When 服务返回 Then 仅返回非敏感字段（不返回/不落盘 API key）。
2. Given 配置无效 When 发起分析 Then 要么阻止启动并返回可理解错误，要么在失败时归因明确（error code + message）。

## Tasks / Subtasks

- [x] 定义 settings 存储方式（非敏感字段可落盘/入库；Key 只从 env 或请求头读取，按架构约束）(AC: 1)
- [x] 实现 settings 读取 endpoint（返回 provider/baseUrl/model 等）(AC: 1)
- [x] 校验策略：在 job 启动前做最小校验（格式/必填）+ 运行时失败归因 (AC: 2)
- [x] 确保日志/错误 details 不泄露 Key (AC: 1,2)

## Dev Notes

- “Key 不落盘”是硬约束；如果需要 UI 配置 Key，建议仅存于运行态或由用户自行通过环境变量注入。

### References

- _bmad-output/planning-artifacts/epics.md
- _bmad-output/planning-artifacts/prd.md

## Dev Agent Record

### Agent Model Used

GPT-5.2

### Implementation Notes

- Settings 存储：使用 `DATA_DIR/settings.json`，只支持非敏感字段（provider/baseUrl/model/timeoutS/allowRulesFallback/debug）。
- Key 来源：仅运行态读取（env: LLM_API_KEY；可选请求头: X-LLM-API-KEY），不落盘、不在 settings endpoint 返回。
- Settings 读取 endpoint：`GET /api/v1/settings/analyze` 返回生效的非敏感字段；settings.json 解析失败返回 error envelope（VALIDATION_ERROR）。
- 校验与归因：新增 runtime provider builder，对 baseUrl（http/https URL）、model、apiKey 做最小校验；失败抛 AnalyzeError 并带 reason 字段（invalid_settings / missing_credentials / invalid_settings_file）。
- Pipeline 接入：highlights/mindmap 在 stage 开始前解析 settings 并做校验；当允许 ANALYZE_ALLOW_RULES_FALLBACK 时继续走 rules fallback。

### Tests

- `pytest` 全量通过（新增 settings store/API 测试与 runtime 校验测试）。

### File List

- services/core/src/core/settings.py
- services/core/src/core/app/api/settings.py
- services/core/src/core/schemas/settings.py
- services/core/src/core/schemas/__init__.py
- services/core/src/core/main.py
- services/core/src/core/app/pipeline/analyze_provider.py
- services/core/src/core/app/pipeline/highlights.py
- services/core/src/core/app/pipeline/mindmap.py
- services/core/tests/test_settings_store.py
- services/core/tests/test_settings_api.py
- services/core/tests/test_analyze_llm.py
