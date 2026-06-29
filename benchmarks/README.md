# Video Helper Benchmarks

量化评估体系：L0 契约测试 → L1 性能 → L2 结构质量 → L3 语义质量（Golden Set）。

## 快速开始

```bash
# 主动 benchmark（需 core 已启动 + LLM 已配置）
make core-benchmark PROFILE=short-local

# 对已有 Job 生成报告（不重跑分析）
make core-benchmark-report JOB_ID=<uuid> PROJECT_ID=<uuid>

# 人工 rubric 交互打分
make core-benchmark-rubric PROFILE=short-local JOB_ID=<uuid> PROJECT_ID=<uuid>

# 扫描 DATA_DIR 内 succeeded jobs
make core-metrics DATA_DIR=./data
```

## 报告落盘

- **目录**：`benchmarks/results/`
- **Schema**：`jobMetrics` + `structureScore` + `baselineDiff` + `environment` + `keyframeVerify`（+ 可选 `semanticScore`、`humanRubric`）
- **格式**：同前缀 `.json`、`.md`、`.html`（HTML 为可读可视化，含分阶段耗时、结构检查、LLM judge / 人工 rubric）
- **文件名**：
  - 主动：`{date}_{git_sha}_{profile}.json`
  - 历史 Job：`{date}_{git_sha}_job-{jobId}.json`

## 指标阈值（初版）

| 层级 | 指标 | 通过线 |
|------|------|--------|
| L1 | speedFactor | 见 `profiles.yaml` 各 profile |
| L2 | structure.score | ≥ 0.85 |
| L2 | keyframe_coverage | ≥ 0.5 |
| L2 | timestamp_in_range | 100% |
| L3 | chapter_boundary_f1 | ≥ 0.7（有标注时） |
| L3 | keyframeVerify.confidenceP50 | ≥ 0.5（verify 开启且有 artifact 时） |
| L3 | keyframeVerify.keepRate | ≥ 0.6（verify 开启且有 artifact 时） |
| L3 | semanticScore.highlightFaithfulness.supportedRate | ≥ 0.8（`--with-llm-judge`） |
| L3 | humanRubric.meanScore | ≥ 3.5（`--merge-rubric` 时） |

`keyframeVerify.enabled=false`（默认 verify 关闭）**不 fail** benchmark。

## Keyframe verify（可选）

在 profile 中配置 `keyframeVerify.mode` 后，closed-loop 脚本会在启动 backend 前注入 `KEYFRAME_VERIFY_MODE`。  
Artifact：`DATA_DIR/.../keyframe_verify/results.jsonl`。

## LLM judge

```bash
uv run python scripts/run_benchmark.py --mode report \
  --job-id <uuid> --with-semantic --with-llm-judge
```

`--judge-full` 评判全部 highlight（成本高，仅发版前）。

## 人工 rubric

模板：`benchmarks/golden/rubric.template.json`  
分数落盘：`benchmarks/golden/{profile}/scores/`（本地 gitignore）

合并报告：`make core-benchmark-report JOB_ID=... MERGE_RUBRIC=1`

## 更新 baseline

1. 各 profile 跑 3 次取中位数
2. 编辑 `benchmarks/results/baseline.json`
3. 记录 `environment`（GPU、TRANSCRIBE_MODEL_SIZE、LLM_MODEL）

详见 [`docs/evaluation.md`](../docs/evaluation.md)。
