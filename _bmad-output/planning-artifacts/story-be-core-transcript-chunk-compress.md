# Story: BE-Core 长视频转写压缩（Chunk Summarization）

## 背景 / 问题
长视频在 fast-whisper 产生的 `transcript.segments` 规模很大（token/字符数随时长线性增长），直接将全量转写交给 LLM 会出现：
- 超上下文窗口 / 成本高 / 延迟大
- 输出不稳定（截断、丢时间锚点）
- 难以在后续阶段保持“时间对齐 + 语义一致性”

本 story 的目标是：在不破坏时间对齐的前提下，将转写压缩为可控大小的“可追溯摘要材料”，供后续 LLM-plan 阶段使用。

## 目标
- 将 `transcript.segments` 规范化、分块（chunk）并生成“可追溯压缩”摘要。
- 压缩产物必须保留时间锚点：每条要点/候选重点都能映射到 `startMs/endMs`（或 segId 范围）。
- 支持并发：chunk 压缩可以并发执行以缩短总耗时。
- 不改变对外 API 契约（Results/Jobs 接口不必暴露中间产物）；中间产物可落盘并在 job 元数据中引用。

## 非目标
- 不实现前端联动逻辑。
- 不引入新的数据库表（MVP 可先落盘 JSON 文件 + job.transcript_meta 引用）。
- 不实现 RAG / 向量索引。

## 设计概述
### 1) 预处理（非 LLM）
输入：`transcript: dict`（fast-whisper 的 `segments`）
输出：`chunks: list[dict]`

建议实现：
- **normalize**：为每个 segment 补齐/校验字段（`startMs/endMs/text`），过滤空文本。
- **merge**：按时间窗口聚合（例如 30s–60s）形成 chunk：
  - `chunkId`（稳定且可复现，例如 `ch_{idx}` 或 hash）
  - `startMs/endMs`
  - `text`（拼接后做长度上限裁剪）
  - `segIds`（可选）

配置建议：
- `TRANSCRIPT_CHUNK_TARGET_SECONDS`（默认 45）
- `TRANSCRIPT_CHUNK_MAX_CHARS`（默认 4000~8000，按模型上下文调）

### 2) Chunk 压缩（LLM，可并发）
对每个 chunk 调用 `llm_provider_for_jobs()`，让 LLM 输出严格 JSON：

**ChunkSummary JSON schema（建议）**
```json
{
  "chunkId": "c_001",
  "startMs": 0,
  "endMs": 45000,
  "bulletSummary": ["..."],
  "entities": ["..."],
  "topics": ["..."],
  "highlightCandidates": [
    {
      "candidateId": "hc_001_0",
      "text": "...",
      "startMs": 12000,
      "endMs": 18000,
      "evidence": "(optional) 近原话片段"
    }
  ]
}
```

**强约束（必须在 prompt 里写清）**
- 只输出 JSON object（`response_format: json_object` 已支持）。
- 所有时间字段单位 ms。
- `highlightCandidates[*].startMs/endMs` 必须落在 chunk 的范围内。
- 限制长度：bullet 每条 <= N 字；候选条目数量 <= K。

并发策略：
- 并发度用现有 worker 配置约束：`MAX_CONCURRENT_JOBS` 之外，再加 `LLM_CHUNK_CONCURRENCY`（默认 3~6）。

### 3) 落盘与引用
- 将 chunks 与 summaries 落盘到 `DATA_DIR/{projectId}/artifacts/{jobId}/`：
  - `transcript_chunks.json`
  - `transcript_chunk_summaries.json`
- 在 `jobs.transcript_meta` 写入引用（避免改表）：
  - `transcript_meta.chunking = {chunkSeconds, chunkCount, chunksRef, summariesRef, summariesSha256, modelInfo...}`

### 4) 错误处理
复用现有错误码：
- LLM 不可用/鉴权失败/输出非法：抛 `AnalyzeError(code=JOB_STAGE_FAILED, details={reason: ...})`
- 若环境变量 `ANALYZE_ALLOW_RULES_FALLBACK=1`：允许降级为“无 LLM 压缩”（直接使用 chunks 文本作为摘要材料或仅保留 chunk 元数据）。

## 代码改动点（建议文件）
- 新增：`services/core/src/core/app/pipeline/transcript_chunking.py`
  - `normalize_segments()`
  - `chunk_transcript()`
- 新增：`services/core/src/core/app/pipeline/transcript_compress.py`
  - `compress_chunks_llm()`（并发/重试/校验）
  - `build_chunk_summary_prompt()`
- 复用：`services/core/src/core/app/pipeline/analyze_provider.py`（`llm_provider_for_jobs`）
- 可能修改：`services/core/src/core/app/pipeline/transcribe_real.py`
  - 在转写落盘后（或 worker 中 transcribe 之后）触发 chunking+compress
- 可能修改：`services/core/src/core/app/worker/worker_loop.py`
  - 将压缩作为可选步骤插入 transcribe 后、plan 前

## 验收标准（Acceptance Criteria）
- 对一个较长 transcript（模拟 > 1h，segments 数千条），可以在合理时间内生成 `transcript_chunk_summaries.json`。
- 任意 summary 条目都带 `startMs/endMs`，且落在 chunk 范围内（服务端校验）。
- LLM 关闭或缺 key 时：
  - 默认行为：跳过压缩并继续流水线（不阻塞 job），或按配置 fail-fast。
- 产物路径只写入 DATA_DIR 下，相对路径通过 `safe_paths` 约束。

## 测试建议
- 单元测试：chunk 边界、长度裁剪、时间范围校验。
- 单元测试：LLM 输出校验（缺字段/时间越界/类型错误 -> 触发 AnalyzeError）。
- 端到端 smoke：跑完整 job，确认 artifacts 文件落盘、SSE/日志不泄漏敏感信息。
