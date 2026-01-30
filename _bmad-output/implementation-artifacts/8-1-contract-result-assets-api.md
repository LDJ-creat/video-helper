# Story 8.1: [Contract] 固化 Result/Assets 读取契约（补全 api.md 并锁定字段）

Status: review

## Story

As a 开发团队,
I want 在 api.md 中把 Result 与 Assets 的读取接口写成可复制的契约,
so that 前后端/多 agent 并行实现不会漂移。

## Acceptance Criteria

1. Given 当前契约未完整 When 更新 `api.md` Then 明确“获取项目最新 Result”的 endpoint、请求参数、响应 schema（含 chapters/highlights/mindmap/note/asset refs）与示例。
2. Then 明确 assets 的 metadata 与 content endpoint（project scope + safe path），错误 envelope、权限（如启用 bearer）一致。
3. Then 明确 stage/事件字段名的一致性（引用统一标准），避免 snake/camel 混用。

## Tasks / Subtasks

- [x] 在 `api.md` 增补：
  - `GET /api/v1/projects/{projectId}/results/latest`
  - `GET /api/v1/assets/{assetId}`（metadata）
  - `GET /api/v1/assets/{assetId}/content`（stream）
  (AC: 1,2)
- [x] 写清字段名（camelCase）、ID/时间戳规则、错误 envelope (AC: 1,2)
- [x] 将 stage 集合与 SSE event schema 作为引用链接到统一标准 (AC: 3)

## Dev Notes

- 这是并行开发的“变更门”：必须先合并此 story，再实现 8.2/8.3/8.4/8.6。
- 统一标准见：_bmad-output/implementation-artifacts/00-standards-and-parallel-plan.md

### References

- api.md
- _bmad-output/planning-artifacts/epics.md
- _bmad-output/planning-artifacts/prd.md

## Dev Agent Record

### Agent Model Used

GPT-5.2

### Completion Notes

- `api.md` 补全 Result latest / Assets metadata+content 契约（含示例 payload）
- 统一错误 envelope 字段为 camelCase：`requestId`
- 在 SSE/stage 段落引用统一标准：`_bmad-output/implementation-artifacts/00-standards-and-parallel-plan.md`

### Tests

- `services/core/tests/test_contract_api_md.py`（回归锁定 api.md 关键契约片段）

## File List

- api.md
- _bmad-output/implementation-artifacts/sprint-status.yaml
- _bmad-output/implementation-artifacts/8-1-contract-result-assets-api.md
- services/core/tests/test_contract_api_md.py

## Change Log

- 2026-01-29：补全 Result/Assets 读取契约并锁定字段命名（camelCase）与标准引用。
