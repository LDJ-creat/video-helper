# Story 12.2: [BE/core] 删除旧流水线实现（保留 LLM-plan 新流水线）

Status: review

## Story

As a 用户,
I want 后端仅保留 LLM-plan 驱动的新视频分析流水线实现,
so that 代码库去除旧的 rules+LLM 混用实现与死代码，降低维护成本且不影响新流水线运行。

## Acceptance Criteria

1. 删除旧流水线实现代码后：核心服务可启动、worker 可正常跑完整 job（见 smoke phase6）。
2. 新流水线（LLM-plan）运行不受影响：plan 驱动的 keyframes / contentBlocks / mindmap 产物依旧可落库并可被 latest result API 读取。
3. 被删除的旧实现不再被任何运行路径引用：静态 import / stage 编排 / 运行时分支均无残留引用。
4. 测试与冒烟：`pytest` 全部通过；并成功跑一次 [scripts/smoke-phase6-closed-loop.ps1](scripts/smoke-phase6-closed-loop.ps1)。

## Tasks / Subtasks

- [x] 盘点旧流水线实现入口与引用点：列出将要删除/改写的文件与符号（AC: 3）
- [x] 删除旧 rules-based segmentation/chapters 实现（若已被 plan 替代且无引用），并清理相关引用（AC: 3）
- [x] 删除旧 keyframes 等距采样路径（若已被 plan timeMs 替代且无引用），并清理相关引用（AC: 3）
- [x] 删除旧 highlights/mindmap（非 plan 输出）实现路径（若无引用），并清理相关引用（AC: 3）
- [x] 补充/更新测试：对“旧模块已移除/不可再引用”添加回归测试；并确保新流水线关键入口可 import（AC: 3,2）
- [x] 跑全量测试：pytest（AC: 4）
- [x] 跑闭环冒烟：phase6 closed-loop（AC: 1,4）

## Dev Notes

- 新流水线设计与验收基准：
  - _bmad-output/implementation-artifacts/12-1-be-core-llm-plan-pipeline.md
  - _bmad-output/planning-artifacts/story-be-core-llm-plan-pipeline.md
- 冒烟脚本：
  - scripts/smoke-phase6-closed-loop.ps1
- 约束：不新增依赖；只做“删除旧实现 + 清理引用 + 必要测试/文档修正”。

## Dev Agent Record

### Agent Model Used

GPT-5.2

### Debug Log

- 清理 legacy 导出：移除 `core.app.pipeline.segment` 的 `__init__` 导出，避免残留 import。
- 删除 legacy pipeline 文件：`segment/highlights/mindmap` 以及无引用的 `core.pipeline.stages/*` 占位 stage。
- keyframes 收敛到 plan 驱动：删除按 chapter 等距采样路径，仅保留 `extract_keyframes_at_times()`。
- 迁移测试：将原先 highlights/mindmap 相关 LLM 测试迁移为 `llm_plan.validate_plan/generate_plan` 的回归测试。


### Completion Notes

- 旧流水线（rules+LLM 混用）实现已移除，且无运行时引用残留。
- 新流水线（LLM-plan）保持：plan -> keyframes(times_ms) -> assemble_result 的闭环可跑通。


### Tests

- `pytest`（core）：61 passed
- `scripts/smoke-phase6-closed-loop.ps1`：closed-loop smoke succeeded（创建 URL job -> succeeded -> latest result 可读 -> asset contentUrl Range 读取返回 206）


## File List

- _bmad-output/implementation-artifacts/12-2-be-core-remove-legacy-pipeline.md
- _bmad-output/implementation-artifacts/sprint-status.yaml
- services/core/src/core/app/pipeline/__init__.py
- services/core/src/core/app/pipeline/keyframes.py
- services/core/tests/test_analyze_llm.py
- services/core/tests/test_remove_legacy_pipeline.py
- services/core/src/core/app/pipeline/segment.py (deleted)
- services/core/src/core/app/pipeline/highlights.py (deleted)
- services/core/src/core/app/pipeline/mindmap.py (deleted)
- services/core/src/core/pipeline/stages/segment.py (deleted)
- services/core/src/core/pipeline/stages/ingest.py (deleted)
- services/core/src/core/pipeline/stages/transcribe.py (deleted)
- services/core/src/core/pipeline/stages/analyze.py (deleted)

## Change Log

- 2026-02-07：创建 story 12.2（删除旧流水线实现）。
- 2026-02-07：删除 legacy pipeline 实现与无引用 stage；收敛 keyframes 到 plan times；迁移/更新测试；pytest 与 phase6 closed-loop smoke 通过。
