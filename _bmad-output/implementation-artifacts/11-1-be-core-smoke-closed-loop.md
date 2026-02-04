# Story 11.1: [BE/core] 闭环冒烟测试（bilibili URL → pipeline → latest result）

Status: review

## Story

As a 开发者,
I want 一个可重复执行的冒烟测试来跑通“下载→抽音频→转写→LLM analyze→assemble_result→assets/result 可读”的闭环,
so that 每次改动后能快速验证系统仍能正确产出可渲染结果。

## Acceptance Criteria

1. Given 后端可启动且 worker 启用 When 使用 bilibili URL 创建 job Then job 最终 `status=succeeded` 且 stage 走到 `assemble_result` 完成。
2. Given job 成功 When 调用 `GET /api/v1/projects/{projectId}/results/latest` Then 返回 200 且包含可渲染字段：`chapters`（>=1）、`highlights`（>=1）、`mindmap.nodes/edges`（nodes>=1）、`assetRefs`（>=1）。
3. Given result.assetRefs 非空 When 取任意一个 `assetId` 调用 `GET /api/v1/assets/{assetId}` Then 返回 200 且 `contentUrl` 可用；再对 `contentUrl` 发起 Range 请求（1KB）返回 200/206。
4. 冒烟测试脚本默认不打印/不回显任何敏感信息（尤其是 `LLM_API_KEY`）。

## Tasks / Subtasks

- [x] 新增闭环冒烟脚本：创建 bilibili URL job，轮询到完成，并校验 latest result + asset content 可读 (AC: 1,2,3,4)
- [x] 新增 Python 校验脚本（可被 PS1 调用）：对 jobs/result/assets 响应做结构化断言；提供可测的纯函数校验器 (AC: 2,3)
- [x] 新增单测：覆盖 result/assets 校验器（无真实网络）(AC: 2,3)
- [x] 增加 VS Code task：一键运行该 smoke（复用现有模式）(AC: 1)

## Dev Notes

- 视频样本（固定）：`https://www.bilibili.com/video/BV1jgifB7EAp/?spm_id_from=333.337.search-card.all.click&vd_source=8e03b1a6cd89d2b50af0c43b7de269ff`
- 环境变量：默认从 `services/core/.env` 读取；脚本只覆盖与 smoke 运行隔离相关的变量（如 `DATA_DIR`/`WORKER_ENABLE`/`MAX_CONCURRENT_JOBS`）。
- 参考实现：`scripts/smoke-phase4-transcribe.ps1`（启动/轮询/证据写出）、`services/core/tests/test_analyze_llm.py`（脱敏/错误映射风格）。
- 依赖：不得新增第三方依赖（复用 repo 现有 python deps）。

## Dev Agent Record

### Agent Model Used

GPT-5.2

### Completion Notes

- 增加闭环 smoke：PS1 负责启动后端/隔离 DATA_DIR；Python 负责创建 bilibili URL job、轮询完成，并验证 latest result 可渲染 + 任意 asset content Range 可读 (AC: 1,2,3)
- 安全：脚本输出仅包含 jobId/projectId/assetId 等非敏感信息，不回显 LLM key/prompt/response (AC: 4)

### Tests

- `D:/video-helper/services/core/.venv/Scripts/python.exe -m pytest -q`（全绿）

## File List

- scripts/smoke-phase6-closed-loop.ps1
- services/core/scripts/smoke_closed_loop.py
- services/core/src/core/app/smoke/__init__.py
- services/core/src/core/app/smoke/closed_loop.py
- services/core/tests/test_smoke_closed_loop_validate.py
- .vscode/tasks.json
- _bmad-output/implementation-artifacts/sprint-status.yaml
- _bmad-output/implementation-artifacts/11-1-be-core-smoke-closed-loop.md

## Change Log

- 2026-02-04: 新增 story（闭环冒烟测试）
