# Story 1.1: [BE/core] 健康检查接口与依赖自检

Status: review

## Story

As a 运维/高级用户,
I want 调用健康检查接口即可看到服务与依赖就绪状态,
so that 我能快速定位“不能分析”的原因。

## Acceptance Criteria

1. Given 服务启动完成 When 请求 `GET /api/v1/health` Then 返回 HTTP 200 且包含依赖检查（至少 ffmpeg、yt-dlp；可选 provider connectivity），不得泄露敏感信息/绝对路径。
2. Given ffmpeg 或 yt-dlp 缺失 When 请求健康检查 Then 仍返回 HTTP 200，但 payload 明确标记缺失项与可行动建议。

## Tasks / Subtasks

- [x] 定义健康检查响应 schema（与统一标准对齐）(AC: 1,2)
- [x] 实现 `/api/v1/health`：检查 ffmpeg、yt-dlp 可执行性与版本（best-effort）(AC: 1,2)
- [x] 输出缺失项与建议动作（install/配置/权限）(AC: 2)
- [x] 确保不输出绝对路径、API Key、stacktrace（health 仍为 200）(AC: 1,2)

## Dev Notes

- 统一标准见：_bmad-output/implementation-artifacts/00-standards-and-parallel-plan.md
- 建议把依赖探测做成可复用函数（后续 keyframes/ingest 复用）。

### Project Structure Notes

- 后端建议新增：`services/core/app/api/v1/health.py`（或同等路由组织）
- 依赖探测工具建议集中：`services/core/app/diagnostics/*`

### References

- _bmad-output/planning-artifacts/epics.md
- api.md

## Dev Agent Record

### Agent Model Used

GPT-5.2

### Debug Log References

- Tests: `services/core` -> `$env:PYTHONPATH="...\services\core\src"; python -m unittest discover -s tests -p "test_*.py" -v`

### Completion Notes List

- Added frozen 200-only health response schema (camelCase) in `core.contracts.health`.
- Implemented reusable executable probes for ffmpeg + yt-dlp (best-effort version, no path/stacktrace leakage).
- Updated `GET /api/v1/health` to always return 200 with `status/ready/tsMs/dependencies`.
- Added unittest coverage for missing deps (still 200), version parsing, and no absolute path leaks.

### File List

- services/core/src/core/contracts/health.py
- services/core/src/core/app/diagnostics/__init__.py
- services/core/src/core/app/diagnostics/executables.py
- services/core/src/core/app/api/health.py
- services/core/tests/test_health.py
- _bmad-output/implementation-artifacts/sprint-status.yaml
