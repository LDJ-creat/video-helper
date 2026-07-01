# Video Helper 评估体系

面向开源单机部署的量化评估：不依赖 Prometheus，复用 `DATA_DIR` + SQLite + benchmark 脚本。

## 四层指标

| 层级 | 内容 | 入口 |
|------|------|------|
| L0 | 契约 / pytest | `make core-test` |
| L1 | 性能（E2E、分阶段、speedFactor） | `collect_job_metrics.py` |
| L2 | Result 结构质量 | `score_result_structure.py` |
| L3 | Golden 语义（章节 F1、LLM judge、人工 rubric） | `run_benchmark.py --with-semantic` 等 |

## 运行方式

### 主动 benchmark

创建 Job → 等待完成 → 自动生成报告：

```bash
make core-benchmark PROFILE=short-local
# 或
cd services/core && uv run python scripts/run_benchmark.py --profile short-local --api-base http://127.0.0.1:8000
```

### 历史 Job 报告

```bash
make core-benchmark-report JOB_ID=<uuid> PROJECT_ID=<uuid>
# 合并人工 rubric 分数
make core-benchmark-report JOB_ID=<uuid> PROJECT_ID=<uuid> MERGE_RUBRIC=1
```

### 已有 JSON 转 HTML

```bash
cd services/core
uv run python scripts/render_benchmark_html.py path/to/report.json
# 或指定输出路径
uv run python scripts/render_benchmark_html.py report.json --out report.html
```

### 批量汇总

```bash
make core-metrics DATA_DIR=./data
```

## 报告格式

- 目录：`benchmarks/results/`
- 主动：`{date}_{git_sha}_{profile}.json`
- 历史：`{date}_{git_sha}_job-{jobId}.json`
- 字段：`jobMetrics`、`structureScore`、`baselineDiff`、`environment`、`keyframeVerify`（+ 可选 `semanticScore`、`humanRubric`）
- 同批次另生成 `.md` 摘要与 `.html` 可视化报告（流水线耗时瀑布图、结构检查卡片、LLM judge / 人工 rubric 区块）

## Keyframe verify 指标

默认 `KEYFRAME_VERIFY_MODE=off`，benchmark **仍可完整运行**。此时报告为：

```json
"keyframeVerify": {
  "enabled": false,
  "reason": "verify_mode_off_or_no_artifact",
  "confidenceP50": null,
  "keepRate": null
}
```

**不参与 `passed` 判定**，baseline 也不对缺失指标告警。

开启方式（专项 profile 或手动）：

```bash
export KEYFRAME_VERIFY_MODE=multimodal
# 或在 benchmarks/profiles.yaml 为 profile 配置 keyframeVerify.mode
```

Job 完成后 artifact：`DATA_DIR/{projectId}/artifacts/{jobId}/keyframe_verify/results.jsonl`（含 `phase`、`action`：`kept` / `retry_scheduled` / `retried_kept` / `retried_dropped` / `dropped`）。  
报告字段：`keepRate`（首次通过）、`overallKeepRate`（含重抽后保留）、`retryScheduledRate`、`secondVerifyPassRate`、`dropAfterRetryRate`、`confidenceP50`、`confidenceP90` 等。建议阈值：`confidenceP50 >= 0.5`、`keepRateMin` / `overallKeepRateMin >= 0.6`、`secondVerifyPassRateMin >= 0.5`（可在 profile `thresholds.keyframeVerify` 配置）。

环境变量（`services/core/.env`）：

```bash
KEYFRAME_VERIFY_MODE=off          # off | ocr | multimodal
KEYFRAME_VERIFY_CONFIDENCE_THRESHOLD=0.4
KEYFRAME_VERIFY_MAX_PER_JOB=5     # 单 Job LLM 调用上限（initial + retry 共享）
KEYFRAME_VERIFY_MAX_PER_HIGHLIGHT=1
KEYFRAME_RETRY_MAX_PER_HIGHLIGHT=1  # KEYFRAME_RETRY_MAX 仍可作为别名
KEYFRAME_LOCAL_SEARCH_WINDOW_MS=10000
KEYFRAME_VERIFY_CONCURRENCY=2
KEYFRAME_VERIFY_MAX_ATTEMPTS=2
KEYFRAME_VERIFY_IMAGE_MAX_BYTES=400000
```

## LLM judge（摘要忠实度）

可选、默认关闭（需 LLM API，有成本）：

```bash
cd services/core
uv run python scripts/run_benchmark.py --mode report \
  --job-id <uuid> --project-id <uuid> \
  --with-semantic --with-llm-judge
```

- 默认**确定性抽样** N=10（`BENCHMARK_JUDGE_SAMPLE_SIZE`），覆盖各 block
- `--judge-full`：评判全部 highlight（发版前手动）
- 报告：`semanticScore.highlightFaithfulness.supportedRate` / `meanScore`
- 默认通过线：`supportedRate >= 0.8` 且 `meanScore >= 0.75`

## 人工 rubric 月跑 SOP

定位：LLM judge 校准 + 导图可用性等主观维度。**非日常 CI 门禁**，建议月跑或发版前。

1. 完成 Golden benchmark：`make core-benchmark PROFILE=short-local`
2. （可选）浏览器打开 `/projects/{projectId}/results` 辅助判断
3. 交互打分：

```bash
make core-benchmark-rubric PROFILE=short-local JOB_ID=<uuid> PROJECT_ID=<uuid>
```

4. 按提示对 `chapterQuality`、`faithfulness`、`mindmapUsability` 打 1–5 分（锚点见 `benchmarks/golden/short-local/rubric.md` 与 `benchmarks/golden/rubric.template.json`）
5. 确认后写入 `benchmarks/golden/{profile}/scores/{date}_{jobId}.json`（目录默认 gitignore）
6. 合并进报告：

```bash
make core-benchmark-report JOB_ID=<uuid> PROJECT_ID=<uuid> MERGE_RUBRIC=1
```

7. 月跑对比：查看 `scores/` 历史 JSON 或 baseline 中 `humanRubric.meanScore` 趋势

建议流程：先 `--with-llm-judge`，人工 rubric 时对照 `highlightFaithfulness.samples` 加速抽检。

## 更新 baseline

1. 各 profile 跑 3 次
2. 取 `e2eMs`、`speedFactor`、`structureScore` 中位数
3. 写入 `benchmarks/results/baseline.json` 并记录硬件环境

## 本地评测

Benchmark 与性能回归均在本地执行（`make core-benchmark`、`run_benchmark.py`），不依赖 CI 定时任务。需配置 LLM 与 FFmpeg 环境，见上文「运行方式」。

见 `benchmarks/golden/manifest.json`。L3 需 `expected_chapters.json` 和/或人工 rubric。
