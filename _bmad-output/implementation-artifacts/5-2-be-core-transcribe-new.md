# Story 5.2 (New): [BE/core] 真实转写闭环（yt-dlp → ffmpeg → ASR → transcript 落盘 → SSE 可观测）

Status: ready-for-dev

## Story

As a 用户,
I want 系统对视频执行“真实可用”的转写（外部视频可自动下载）并产出带 ms 时间戳的 transcript,
so that Phase 5 的 chapters/highlights/mindmap/keyframes 可以基于同一时间轴对齐，最终形成完整闭环。

## Scope / Non-Goals

- **In scope**：
  - 外部视频（URL source）：使用 yt-dlp 下载媒体文件到项目存储
  - 上传视频（upload source）：使用已上传的媒体文件
  - 使用 ffmpeg 抽取/解码/重采样音频（建议 16kHz mono PCM wav）
  - 使用本地 ASR（faster-whisper）生成 transcript（分段+ms 时间戳）
  - transcript **落盘**（文件）并在 DB 中保存引用/元数据
  - SSE / job state 可观察 stage=transcribe + progress 单调推进 + 关键日志

- **Out of scope（本 story 不要求）**：
  - 摘要/重点/highlights/mindmap/keyframes 的生成（Phase 5/WT-BE-07）
  - 多语言自动检测/翻译质量优化（允许后续迭代）
  - GPU 加速与大规模并发优化（只要求功能闭环与可观测性）

## Acceptance Criteria

1. **外部视频闭环（URL → transcript）**
   - Given 通过 `POST /api/v1/jobs` 创建一个外部视频 Job（如 YouTube/Bilibili URL）
   - When worker 执行到 transcribe stage
   - Then 系统必须：
     - 使用 **yt-dlp 下载**媒体文件到 `DATA_DIR/<projectId>/...`（保存相对路径到 DB）
     - 使用 **ffmpeg 提取/重采样**音频（保存音频文件到项目存储，保存相对路径到 DB 或 transcript 元信息中）
     - 使用 **faster-whisper** 对音频转写并生成 transcript（分段，包含 `startMs/endMs`，单位 ms）
     - transcript **落盘**为文件（例如 JSON），并在 DB 中保存引用（例如 `jobs.transcript_ref` / `assets` 绑定 / 结果表引用，按现有数据模型选一种）

2. **上传视频闭环（upload → transcript）**
   - Given 通过 multipart upload 创建的 Job 且已保存媒体文件
   - When worker 执行到 transcribe stage
   - Then 系统必须对该媒体文件执行 **ffmpeg → faster-whisper → transcript 落盘**（同 AC1 的格式与持久化要求）

3. **可观测性（SSE + state）**
   - Given Job 进入 transcribe stage
   - Then：
     - `GET /api/v1/jobs/{jobId}`（或等价状态接口）对外 stage 映射为 `transcribe`
     - SSE 必须持续输出：stage/progress 单调推进（0→100 或等价进度语义）
     - 日志中必须包含：是否走 URL 下载、ffmpeg 音频输出位置、ASR provider=faster-whisper、transcript 落盘位置/引用 ID

4. **失败归因（错误码与建议动作）**
   - Given 转写失败
   - Then Job 必须进入 failed，并且 error code / reason 可区分以下至少几类：
     - 依赖缺失：yt-dlp 不可用、ffmpeg 不可用
     - 模型缺失/加载失败：faster-whisper 模型不可用
     - 资源不足：磁盘空间不足/内存不足/超时
     - 内容异常：媒体不可解码/无音轨
   - 且错误信息不泄露敏感信息（遵循既有 health/settings 错误规范）

5. **为 Phase 5 对齐的时间轴保证**
   - transcript 的 `startMs/endMs` 必须源自音频时间轴（ffmpeg 重采样后）
   - 后续章节/重点/导图/关键帧将以该 transcript 时间轴作为唯一基准，不允许混用其它时间单位

## Tasks / Subtasks

- [x] 定义并实现“媒体来源解析”策略（URL vs upload）(AC: 1,2)
- [x] URL 下载：封装 yt-dlp 下载器（存储路径、失败归因、可重试）(AC: 1,4)
- [x] 音频前处理：封装 ffmpeg 抽取/重采样（16kHz mono PCM），并落盘音频文件 (AC: 1,2,4)
- [x] ASR：接入 faster-whisper（本地），输出分段 transcript（ms）(AC: 1,2,5)
- [x] transcript 持久化：落盘文件 + DB 引用/元数据（路径、hash、provider、language 等）(AC: 1,2)
- [x] SSE/状态可观测：stage/progress/log 事件补齐，记录关键路径与落盘引用 (AC: 3)
- [x] 错误码归因：与现有错误码体系对齐，确保 job failed 可定位原因 (AC: 4)
- [x] 测试：
  - [x] 单元测试：yt-dlp/ffmpeg/faster-whisper wrapper 的命令构造与错误映射 (AC: 1,2,4)
  - [x] 集成/烟测：提供一个最小可复现脚本或说明，能在本机跑通 URL→transcript 与 upload→transcript (AC: 1,2,3)

## Dev Notes

- 依赖约束：
  - 外部工具：`yt-dlp`、`ffmpeg` 必须可在运行环境找到（PATH 或配置项）
  - Python：`faster-whisper`（本地 ASR）
- 输出建议：
  - 音频输出建议：WAV PCM S16LE，16kHz，mono
  - transcript 文件建议：JSON（segments 数组，字段含 text/startMs/endMs，可扩展 confidence/language）
- 可观测性：
  - SSE 中应区分 download/extract/transcribe 子进度，避免长时间无事件导致前端误判卡死
- 与 Phase 5 衔接：
  - Phase 5 产物（chapters/highlights/mindmap/keyframes）必须能消费本 story 的 transcript 时间轴；因此 schema 变更需走 WT-00 契约冻结流程

## Dev Agent Record

### Agent Model Used

GPT-5.2

### Implementation Plan

- 在 core 层新增可选依赖的 ASR wrapper（lazy import），输出统一 transcript schema（ms segments）。
- 新增 transcript 落盘 helper：写入 `DATA_DIR/<projectId>/artifacts/<jobId>/transcript.json` 并返回相对路径 + sha256。
- 在 worker 的 transcribe 阶段替换 placeholder：
  - URL source：`yt-dlp` 下载到 `DATA_DIR/<projectId>/downloads/<jobId>/...`，并写回 `projects.source_path`
  - upload source：直接使用 `projects.source_path`
  - `ffmpeg` 抽取 `audio.wav` 到 artifacts 目录
  - `faster-whisper` 转写并写入 DB + 文件引用
  - 通过 SSE 以 stage=transcribe 单调推进输出子进度与关键日志
- 对齐失败归因：缺依赖/模型缺失/资源不足/内容异常/超时。

### Completion Notes

- 已实现真实闭环：URL（yt-dlp）/upload → ffmpeg(16k mono wav) → faster-whisper → transcript.json 落盘 → DB 写入 transcript + refs。
- `jobs.transcript` 仍保留原 schema（`segments[]` + `startMs/endMs` + `durationMs` + `unit=ms`），确保可无缝衔接现有 `segment` 逻辑。
- 通过 `GLOBAL_JOB_EVENT_BUS` 在 transcribe 阶段输出子进度与关键日志（是否下载、音频/转写文件相对路径、provider）。
- 默认不做“自动回退 placeholder”（确保缺依赖/模型缺失会明确 failed）；可通过 `TRANSCRIBE_PROVIDER=placeholder` 或 `TRANSCRIBE_ALLOW_PLACEHOLDER_FALLBACK=1` 手动启用。

### Tests

- `uv run pytest -q`（services/core）：新增与既有测试全绿。
- 手工烟测（Windows PowerShell）：见 `scripts/smoke-phase5-transcribe.ps1`。

## File List

- services/core/src/core/app/pipeline/media_source.py
- services/core/src/core/external/ytdlp.py
- services/core/src/core/external/ffmpeg.py
- services/core/src/core/external/asr_faster_whisper.py
- services/core/src/core/app/pipeline/transcript_store.py
- services/core/src/core/app/pipeline/transcribe_real.py
- services/core/src/core/app/worker/worker_loop.py
- services/core/src/core/db/models/job.py
- services/core/src/core/db/session.py
- services/core/tests/test_pipeline_media_source.py
- services/core/tests/test_external_ytdlp.py
- services/core/tests/test_external_ffmpeg.py
- services/core/tests/test_external_asr_faster_whisper.py
- services/core/tests/test_pipeline_transcript_store.py
- scripts/smoke-phase5-transcribe.ps1

## Change Log

- 2026-02-02: 新增“真实转写闭环”story（不修改原 5-2），明确 yt-dlp + ffmpeg + faster-whisper + transcript 落盘 + SSE 可观测为硬性验收
