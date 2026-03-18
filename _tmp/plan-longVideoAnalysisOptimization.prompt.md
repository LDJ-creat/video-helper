## Plan: 长视频分层分析 + 关键帧校验/回退优化

对“长视频（课程/播客）”启用 chunk 级→章节/全片级的分层分析，避免全量转写一次性输入 LLM 导致的慢与注意力发散；关键帧采用“方案1（文本推断 timeMs）为主 + 预算上限的方案2校验/回退闭环”为辅，在不强制多模态的前提下提升关键帧有效性与稳定性。

**Steps**

1.  确认现有流水线插入点（已摸清）
    - 当前顺序：transcribe → plan → keyframes → assemble_result
    - plan 入口与 schema：见 services/core/src/core/app/pipeline/llm_plan.py
    - 关键帧抽取与回填：见 services/core/src/core/app/pipeline/keyframes.py
    - 编排入口：见 services/core/src/core/app/worker/worker_loop.py

2.  增加“长视频判定 + 路由策略”（_阻塞后续_）
    - 判定输入：优先用 transcript meta 的时长；缺失时用 segments 最大 endMs 估算
    - 判定维度：duration（默认 20min）+ 输入规模（segments 数、字符数/估算 token）
    - 路由结果：
      - 短视频：保持现有 plan 路径（采样 excerpt → generate_plan）
      - 长视频：走分层路径（步骤 3-7）

3.  新增 chunk-level summaries 生成阶段（_长视频专用，可并行_）
    - 切分（建议自适应，避免过碎）：
      - 目标：单 chunk 时长“默认约 5min”，但支持随视频总时长动态调整（在质量可控的前提下尽量减少 chunk 数量与 LLM 调用次数）
      - 约束：
        - 最小窗口：CHUNK_MIN_WINDOW_MS（建议 3–4min）
        - 最大窗口：CHUNK_MAX_WINDOW_MS（建议 6–8min）
        - 基准目标窗口：CHUNK_TARGET_WINDOW_MS（建议 5min）
      - 计算方式（推荐：按总时长自动选窗，真正“动态调整”）：
        - 先估算视频总时长：durationMs（优先 transcript_meta.durationMs；否则取 segments 最大 endMs）
        - 统一采用 auto（不再区分 fixed/auto 模式，减少配置复杂度）：
          - 目标：让 chunk 数量尽量落在一个“可并发消化”的区间，避免 2 小时视频切成 40+ 个 chunk 或 30 分钟视频切成 3 个超大 chunk
          - 默认常量（建议先写死在代码里；只有需要调参时再考虑暴露为 env）：
            - TARGET_COUNT = 24
            - MIN_COUNT = 12
            - MAX_COUNT = 60
          - 算法（示例）：
            - roughCount = ceil(durationMs / CHUNK_TARGET_WINDOW_MS)
            - targetCount = clamp(roughCount, MIN_COUNT, MAX_COUNT)
            - windowMs = clamp(ceil(durationMs / targetCount), CHUNK_MIN_WINDOW_MS, CHUNK_MAX_WINDOW_MS)
          - 解释：
            - CHUNK_TARGET_WINDOW_MS 仍有意义：它提供 roughCount 的“默认密度”；最终 windowMs 会被 durationMs 自动纠偏。
            - clamp 的意义也更清晰：它是护栏（guardrail），防止异常输入把 windowMs 推到过小（调用爆炸）或过大（单次摘要过重）。
          - fallback（无需额外配置）：若 durationMs 缺失/不可信，则回退到
            - windowMs = clamp(CHUNK_TARGET_WINDOW_MS, CHUNK_MIN_WINDOW_MS, CHUNK_MAX_WINDOW_MS)
        - 备选（更直观但更“写死”）：按总时长分桶选择 targetWindow，然后再 clamp。
          - 例如：<45min 用 4min；45–120min 用 5min；2–4h 用 6min；>4h 用 7–8min。
      - 对齐：切分边界要落在 transcript segment 边界上；每个 chunk 必须带 chunkId + startMs/endMs

    - 并发执行（必须明确）：
      - chunk-level summaries 是典型 map 阶段：对每个 chunk 的 LLM 调用可以并发进行
      - 为避免触发 provider 限流：设定最大并发上限 CHUNK_LLM_MAX_CONCURRENCY（建议默认 5）
      - 调度：使用有界并发队列（worker pool / semaphore），并对 429/5xx 做退避重试（仍受总超时约束）

    - 产出数据结构（必须固定格式，供 Step4 reduce 消费；示例 JSON Schema 级别定义）：
      - ChunkSummary
        - chunkId: string
        - startMs: int
        - endMs: int
        - summary: string（<= CHUNK_SUMMARY_MAX_CHARS；本段一句话/一小段概括）
        - points: Array<{ text: string, importance: 1|2|3 }>
        - terms: Array<{ term: string, definition?: string }>（可选；数量要很少）
        - keyMoments: Array<{ timeMs: int, label: string }>（可选；timeMs 必须落在 [startMs,endMs) 内）
      - 输出集合：chunkSummaries: ChunkSummary[]（按 startMs 升序；chunkId 唯一）
      - 约束：严格限制每个 chunk 的条目数与字符预算（CHUNK_MAX_POINTS、CHUNK_SUMMARY_MAX_CHARS、CHUNK_MAX_CHARS），避免“chunk summary 变成 chunk transcript”。

      - 字段含义与作用（这段可直接作为提示词规范提供给 LLM）：
        - chunkId
          - 含义：chunk 的稳定标识符（例如 c0001/c0002…）；用于排序、去重、debug 与缓存。
          - 作用：Step4 reduce 依赖它把多个 chunk summary 按时间聚合为章节。
        - startMs / endMs
          - 含义：该 chunk 覆盖的时间范围（毫秒）。必须满足 endMs > startMs。
          - 作用：Step4 用时间范围对齐章节边界，保证最终 contentBlocks 不重叠。
        - summary
          - 含义：对该 chunk 的“整体一句话概括”（不是逐句转写）。
          - 作用：Step4 用它快速理解本段主题与上下文，决定本段归属哪个章节。
          - 约束：长度 <= CHUNK_SUMMARY_MAX_CHARS；避免包含过多细节。
        - points[]
          - 含义：本 chunk 中“可直接变成学习笔记/高亮点”的要点陈述（完整句子/可读笔记）。
          - 作用：Step4 主要从 points 里选取、合并、改写，生成最终 highlights.text。
          - 约束：
            - points 的 text 应该是“陈述句/知识点”，而不是名词列表。
            - importance: 1=一般，2=重要，3=关键；用于 Step4 在预算内优先保留关键点。
        - terms[]（可选）
          - 含义：本 chunk 出现的重要术语/概念的“词条”（term 是名词短语；definition 是简短定义）。
          - 作用：Step4 用它做跨 chunk 的概念一致性（同一概念统一命名/定义），并辅助生成更准确的 points/highlights。
          - 与 points 的区别：
            - points 是“发生了什么/讲了什么”的笔记要点；terms 是“概念词典条目”。
            - 若某项内容可以写成一句话知识点，优先放 points；只有稳定术语才放 terms。
          - 约束：数量要很少（只保留最关键概念）；definition 可省略。
        - keyMoments[]（可选）
          - 含义：本 chunk 内值得标记的小节点（例如“开始讲定义/给出公式/切到代码演示”）。
          - 作用：Step4 可用它更稳地切章节/放置 highlight 的时间范围；不是必须字段。
          - 约束：timeMs 必须落在 [startMs, endMs)；label 要短。

      - 生成风格约束（同样可作为提示词的一部分）：
        - 不要复述原始转写；不要逐句 paraphrase。
        - points 以“学习笔记”口吻写清楚结论/方法/步骤；避免口语填充词。
        - terms 只收录本段最关键的概念，不要把所有名词都列进去。

    - 多语言输出（与现有 plan 阶段一致）：
      - pipeline 接收客户端选择的 outputLanguage（参考 llm_plan.py 的 build_plan_request 逻辑）
      - chunk summaries 阶段与 Step4 reduce 阶段的提示词都必须带同样的 language hint：
        - 要求所有用户可见文本（summary/points/term definition/章节标题/highlight/mindmap label 等）使用 outputLanguage
      - 这保证长视频路径与短视频路径对“语言模式”的支持一致。

    - 持久化：
      - 存储位置（默认不新增 SQLite 表）：
        - 复用你们现有 artifacts 目录结构（参考 transcript_store.py）：DATA_DIR/<projectId>/artifacts/<jobId>/
      - 存储形态（固定为“多文件 + manifest”，避免并发写单文件的问题）：
        - 清单：chunk_summaries/manifest.json
          - 记录：windowMs（最终值）、outputLanguage、promptsVersion、chunkingVersion（例如 1）、以及 chunk 列表（chunkId/startMs/endMs）
        - 单 chunk 结果：chunk*summaries/chunk*<chunkId>.json
          - 记录：对应 ChunkSummary
        - （可选）汇总索引：chunk_summaries/index.json
          - 记录：已完成 chunkId 列表 + 总数，用于快速判断是否可进入 Step4
      - 断点续跑 / 继续分析复用（必须支持）：
        - chunk 切分必须是确定性的（同一 transcript + 配置 => 相同 chunkId/startMs/endMs 列表），这样才能可靠复用。
        - 执行每个 chunk 前先检查该 chunk 的结果文件是否已存在且可解析：
          - 存在 => 直接跳过该 chunk 的 LLM 调用
          - 不存在/损坏 => 仅重跑该 chunk
        - 写入必须原子化：先写临时文件（.tmp），校验 JSON 后再 rename 覆盖，避免断电/崩溃留下半文件。
        - 进度汇报：job.progress 可按 completedChunks/totalChunks 更新；job.stage 可设置为 chunk_summaries。
      - “是否已完成所有 chunk summaries”的判定：
        - 以 manifest.json 的 chunk 总数为准；当存在并可解析的 chunk\_<chunkId>.json 数量达到总数，即可进入 Step4 reduce。
      - 缓存键（用于跨次运行复用，避免无效重算）：
        - 至少包含：transcript sha256（已在 transcript_store 返回）、windowMs（最终值）、chunkingVersion、promptsVersion、outputLanguage
        - 若你们的“继续分析”会复用同一个 jobId：仅依赖 artifacts/jobId 即可。
        - 若“继续分析”会新建 jobId：引入 project 级缓存目录来跨 job 复用（推荐）。

               - project 级缓存（跨 job 复用，推荐启用）：
                   - 目录结构建议：
                      - DATA_DIR/<projectId>/cache/long_video/<cacheKey>/
                         - transcript.json（可选：若你们愿意把最终 transcript 也缓存到这里，便于跨 job 直接复用）
                         - transcript_chunks/manifest.json + chunk_<chunkId>.json（可选：若启用 chunked transcribe）
                         - chunk_summaries/manifest.json + chunk_<chunkId>.json
                         - plan.json（可选：若 Step4 reduce 产物也希望跨 job 复用）
                   - cacheKey 组成（示例，确保“同输入 + 同配置 => 同 key”）：
                      - transcriptSha256（来自 transcript_store 的 sha256）
                      - outputLanguage
                     - windowMs（最终值）+ chunkingVersion
                      - promptsVersion（chunk summaries 提示词版本 + reduce 提示词版本）
                      - （若启用 chunked transcribe）TRANSCRIBE_MODEL_SIZE/DEVICE/COMPUTE_TYPE/VAD 等关键 ASR 配置
                   - 复用逻辑：
                      - 新 job 开始时，若已存在 transcript.json 且能得到 transcriptSha256，则优先查 project cache 命中：
                         - 命中 => 直接复用 chunk_summaries（甚至 plan.json），跳过对应阶段
                         - 未命中 => 走本 job 生成，并写入 project cache
                      - 若 transcript 尚未生成（例如转写尚在进行），仍按 artifacts/jobId 落盘做断点续跑；待 transcript 完成后再将结果“归档”到 project cache（写入同一 cacheKey 目录）。

               - 重要现状与补齐（解决“转写中断无法复用”的问题）：
                   - 现状：当前转写阶段是“一次性落盘”，ASR 完成后才写入 transcript.json（参考 transcribe_real.py -> store_transcript_json）。
                      - 这意味着：转写中断（断网/限额/误关）时无法复用已转写部分。
                   - 补齐方案（建议仅对长音频启用，可选）：chunked transcribe（分段转写落盘）
                      - 思路：先用 ffmpeg 把音频切成与 chunk 类似的时间窗（例如 5min，或沿静音/VAD 边界），逐段 ASR。
                      - 并发与流水线（回答“能否并发、能否一段完成就立刻分析”）：
                         - ffmpeg 分段音频提取：
                            - 不采用并发，建议用“单次 ffmpeg 分段输出”（segment muxer）生成所有片段，避免多进程争抢磁盘。
                         - faster-whisper 分段转写：
                            - 可以并发，但强烈建议有界并发；GPU 场景通常并发=1 更稳（避免显存/吞吐抖动）。
                            - CPU 场景可尝试并发 2–3（取决于核心数/内存）。用配置 TRANSCRIBE_CHUNK_MAX_CONCURRENCY 控制。
                         - “一段转写完成就立刻调用 LLM 分析”：
                            - 推荐（流水线化降低端到端延迟）。实现上把流程做成 producer/consumer：
                               - ASR worker 产出 transcript_chunk_<chunkId>.json 后，立即投递到 LLM map 队列
                               - LLM worker（并发受 CHUNK_LLM_MAX_CONCURRENCY 限制）生成 chunk_<chunkId>.json（ChunkSummary）
                            - reduce（Step4）只在“所有 chunkSummaries 都落盘完成”后开始，保证最终 plan 一致性。
                      - 存储：DATA_DIR/<projectId>/artifacts/<jobId>/transcript_chunks/
                         - manifest.json（记录 chunkId/startMs/endMs/audioChunkRef）
                         - chunk_<chunkId>.json（该段的 transcript segments）
                      - 断点续跑：同样以“文件存在且可解析”判定，跳过已完成的转写 chunk。
                      - 汇总：当全部 transcript_chunks 完成后，合并生成最终 transcript.json（保持后续 pipeline 接口不变）。

4.  章节级/全片级聚合（reduce）（_依赖 3_）
    - 目标：从 chunk summaries 推导稳定章节结构，并直接生成长视频的最终 PlanOutput（contentBlocks/highlights/mindmap 的完整 JSON）
    - 约束：章节时间不重叠（可有空隙），标题面向学习复盘；输出必须通过现有 validate_plan（保持对外契约一致）
    - 关键点：为避免后续“再把 Step4 产物喂给 Step5 重新生成”造成 token 浪费，长视频路径建议在这里一次性完成最终结构化输出。

5.  关键帧主策略（方案1）：仍由 LLM 产出 timeMs（_依赖 4_）
    - 仍按现有 schema：highlights[].keyframes[].timeMs（或兼容 keyframe）
    - 控制策略（可配置）：
      - 播客默认少/无关键帧
      - 课程允许关键帧，但每个 highlight 默认最多 0–1 张

6.  关键帧校验/回退闭环（方案2，严格预算上限）（_依赖 5；在抽帧后执行最合适_）
    - 开关（默认关闭）：
      - KEYFRAME_VERIFY_MODE=off|ocr|multimodal（默认 off）
      - off：完全跳过“校验/回退”阶段，不做 OCR、不做二次抽帧、不做多模态
      - 触发条件（在开关开启时才生效；由 LLM 决定，配合硬预算裁决）：
        - 在 Step4（长视频 reduce 生成）或短视频 plan 生成时，让 LLM 为每个 highlight 输出：
          - needsKeyframeVerify=true/false（是否建议校验/回退）
          - keyframeConfidence（例如 0–1）或低/中/高
        - 校验阶段只在以下条件同时满足时执行：
          - needsKeyframeVerify=true（或 keyframeConfidence 低于阈值）
          - 且未超过硬预算（每 highlight / 每 job 的上限）
        - 备注：不再依赖“关键词规则触发”，因为 chunk 抽取阶段可能会清理掉“如图/这一页”等口语提示词，导致规则失效。
    - 校验模式（两档，默认先做 OCR-only）：
      - OCR-only：对已抽帧图片做 OCR，LLM 基于 OCR文本 + highlight文本 + 时间范围 做保留/丢弃判断
      - multimodal（可选开关）：provider 支持时，发起多模态校验并生成/修订 caption
    - 回退策略（锁死成本与时延）：
      - 每个 highlight 最多 1 次校验 + 1 次重选（共最多 2 张帧/OCR）
      - 重选仅在原 timeMs 附近局部搜索（例如 ±10s 取 3 个候选点）
      - 若仍不通过：清空该 highlight 的 keyframe/keyframes，不再重试

7.  预算与开关治理（_与实现并行推进_）
    - 配置策略（桌面端优先，回答“写 env 还是写代码常量”）：
      - 桌面端（你们主要分发形态）：
        - 原则：对普通用户不暴露环境变量；全部使用代码内安全默认值（常量）。
        - 可选“高级覆盖”（仅用于排障/灰度，不面向普通用户）：沿用现有 dotenv 约定，读取一个本地 `.env` 文件并注入缺失的环境变量（默认不需要、不提示用户配置）。
          - 现状：后端入口已会读取 `services/core/.env`（开发用；见 services/core/main.py 的最简 dotenv loader）。
      - 自托管/开发（可选支持）：
        - 允许通过环境变量覆盖同一组参数，方便 CI/smoke/压力测试与快速调参。
      - 分层建议：
        - Tier A（即使将来要做“高级覆盖”，也只建议开放这一层）：
          - 长视频判定阈值：LONG_VIDEO_MIN_MS、LONG_VIDEO_MIN_SEGMENTS、LONG_VIDEO_MIN_CHARS
          - 并发上限：CHUNK_LLM_MAX_CONCURRENCY
          - 关键帧校验总开关：KEYFRAME_VERIFY_MODE
        - Tier B（强烈建议永远写死在代码里；需要调参时走发版，而不是让用户配置）：
          - chunk 窗口上下界与基准：CHUNK_TARGET_WINDOW_MS、CHUNK_MIN_WINDOW_MS、CHUNK_MAX_WINDOW_MS
          - auto 计算用的 TARGET_COUNT/MIN_COUNT/MAX_COUNT
          - 各类预算（points/summary chars/timeout 等）：CHUNK_MAX_CHARS、CHUNK_MAX_POINTS、CHUNK_SUMMARY_MAX_CHARS、CHUNK_LLM_TIMEOUT_S
          - 关键帧校验细分参数：KEYFRAME_VERIFY_MAX_PER_HIGHLIGHT、KEYFRAME_VERIFY_MAX_PER_JOB、KEYFRAME_RETRY_MAX、KEYFRAME_LOCAL_SEARCH_WINDOW_MS、KEYFRAME_VERIFY_CONFIDENCE_THRESHOLD
    - 长视频判定：LONG_VIDEO_MIN_MS、LONG_VIDEO_MIN_SEGMENTS、LONG_VIDEO_MIN_CHARS（或 token 估算）
    - chunk：
      - CHUNK_TARGET_WINDOW_MS、CHUNK_MIN_WINDOW_MS、CHUNK_MAX_WINDOW_MS
      - （窗口 auto 计算默认常量，建议先不暴露 env）：TARGET_COUNT=24、MIN_COUNT=12、MAX_COUNT=60
      - CHUNK_MAX_CHARS、CHUNK_MAX_POINTS、CHUNK_SUMMARY_MAX_CHARS、CHUNK_LLM_TIMEOUT_S
      - CHUNK_LLM_MAX_CONCURRENCY（默认 5）
    - 关键帧校验：
      - KEYFRAME_VERIFY_MODE=off|ocr|multimodal（默认 off）
      - KEYFRAME_VERIFY_MAX_PER_HIGHLIGHT（例如 1）
      - KEYFRAME_VERIFY_MAX_PER_JOB（例如 5）
      - KEYFRAME_RETRY_MAX（例如 1）
      - KEYFRAME_LOCAL_SEARCH_WINDOW_MS（例如 10s）
      - KEYFRAME_VERIFY_CONFIDENCE_THRESHOLD（可选，用于 keyframeConfidence）
    - 目标：端到端耗时、LLM 调用次数、图片/OCR次数都有硬上限

8.  测试、smoke 与灰度（_阻塞上线_）
    - 单测覆盖：长视频路由、summaries 驱动 plan、关键帧校验/回退的预算上限路径
    - smoke：固定 1 条长课程 + 1 条长播客
      - 校验：contentBlocks 覆盖且不重叠；mindmap 锚点可解析；播客关键帧少/为空；课程关键帧更有画面价值
    - 指标：端到端耗时、LLM 调用次数/估算 token、plan 校验失败率、关键帧保留率（课程/播客分桶）

**Relevant files**

- services/core/src/core/app/pipeline/llm_plan.py — 长视频路径的请求拼装与提示词约束；已支持 summaries
- services/core/src/core/app/worker/worker_loop.py — 新增阶段（chunk summaries / reduce / keyframe verify）编排插入点
- services/core/src/core/app/pipeline/keyframes.py — 抽帧与回填 assetId/contentUrl；校验/回退环适合围绕这里做
- services/core/src/core/app/pipeline/transcript_store.py — 转写工件与引用存储；长视频判定/缓存复用
- services/core/src/core/external/asr_faster_whisper.py — segments 粒度与字段来源（startMs/endMs/text）

**Verification**

1. 运行核心单测 + 新增用例：路由、summaries 输入、校验/回退预算上限
2. 本地 smoke：长课程/长播客各 1 条，核对 blocks/mindmap 锚点/关键帧数量与质量、以及耗时是否在预算内
3. 回归短视频：确认原 plan 与 keyframes 逻辑不被影响

**Decisions**

- 主路径选方案1；仅对“视觉强需求”的课程 highlight 启用方案2校验/回退闭环
- 长视频才启用分层 chunk→chapter→plan；短视频保持现状
- 多模态非硬依赖：优先 OCR-only，multimodal 做可选开关
- 关键帧校验/回退默认关闭（KEYFRAME_VERIFY_MODE=off）；开启后可支持“由 LLM 建议触发”，但始终受硬预算约束
