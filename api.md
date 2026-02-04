# 暂定需要的接口

> 目标：把关键契约写成“可复制/可校验”的形态，避免多人/多代理实现时自行发挥。

## API Contract（强约束：Schema + 示例）

### Base

- Base URL: `/api/v1`
- Auth：本地默认关闭；远程模式启用 `Authorization: Bearer <token>`
- 所有时间戳：Unix epoch milliseconds（number）
- 所有 ID：UUID string

### Error Envelope（所有错误统一）

**JSON Schema（Draft 2020-12）：**

```json
{
	"$schema": "https://json-schema.org/draft/2020-12/schema",
	"$id": "https://video-helper.local/schemas/error-envelope.json",
	"type": "object",
	"required": ["error"],
	"properties": {
		"error": {
			"type": "object",
			"required": ["code", "message"],
			"properties": {
				"code": {"type": "string"},
				"message": {"type": "string"},
				"details": {"type": "object"},
				"requestId": {"type": "string"}
			},
			"additionalProperties": false
		}
	},
	"additionalProperties": false
}
```

**示例：**

```json
{
	"error": {
		"code": "JOB_NOT_FOUND",
		"message": "Job does not exist",
		"details": {"jobId": "b3b2..."},
		"requestId": "req_01J..."
	}
}
```

### Cursor Pagination（列表统一）

**响应形态（所有 list/search 一致）：**

```json
{
	"items": [],
	"nextCursor": null
}
```

**示例：GET /projects**

```json
{
	"items": [
		{
			"projectId": "2d2f...",
			"title": "Video A",
			"sourceType": "youtube",
			"updatedAtMs": 1738030000000,
			"latestResultId": "6a5c..."
		}
	],
	"nextCursor": "eyJ1cGRhdGVkQXRNcyI6MTczODAzMDAwMDAwMCwiaWQiOiIyZDJmLi4uIn0="
}
```

### SSE（Job 事件流统一）

统一标准（stage 集合、SSE event schema、字段命名）：见 `_bmad-output/implementation-artifacts/00-standards-and-parallel-plan.md`。

- Endpoint: `GET /api/v1/jobs/{jobId}/events` (`Content-Type: text/event-stream`)
- 事件类型（仅允许）：`heartbeat` | `progress` | `log` | `state`
- Payload 字段（camelCase，统一）：
	- `eventId` string（单调递增，用于 `Last-Event-ID`）
	- `tsMs` number
	- `jobId` string
	- `projectId` string
	- `stage` string（稳定 stage 名：`ingest`/`transcribe`/`segment`/`analyze`/`assemble_result`/`extract_keyframes`）
	- `progress` number（0..1，可选；可为 null；对同一 `stage` best-effort 单调不回退）
	- `message` string（可选）

**SSE 示例：**

```text
event: progress
id: 12
data: {"eventId":"12","tsMs":1738030000123,"jobId":"...","projectId":"...","stage":"transcribe","progress":0.42,"message":"Transcribing"}

event: log
id: 13
data: {"eventId":"13","tsMs":1738030000456,"jobId":"...","projectId":"...","stage":"transcribe","message":"ffmpeg: ..."}
```

## 项目级接口
 - 健康检查接口：用于前端判断服务可用性、依赖是否就绪（例如 ffmpeg/yt-dlp/模型可用性）。

## 业务逻辑接口

### 1) 项目（Project / Video Note）

- 创建项目接口：创建一个“视频笔记项目”，用于承载后续分析结果与用户编辑内容。
- 获取项目列表接口（分页查询）：用于展示“不同视频对应的笔记列表”。
- 获取项目详情接口：用于获取项目元信息（标题、来源、更新时间、latest_result 指针等）。
- 删除项目接口：删除单个视频笔记项目（包含其数据与资源）。

### 2) 分析任务（Job：长任务统一模型）

- 创建分析任务接口（创建 Job）：输入为视频来源（YouTube/B站 URL 或本地文件路径/上传资源引用等），后端异步执行分析。
- 查询分析任务状态接口（轮询 Job，降级方案）：返回任务状态（queued/running/succeeded/failed/canceled）、进度 progress、stage、错误信息等。
- 取消分析任务接口（可选）：用户取消正在运行的任务。
- 任务进度事件流接口（SSE，默认方案）：用于实时推送 stage/progress/log；前端默认使用 SSE 获取进度与阶段信息。

说明：

- 默认策略：前端优先建立 SSE 连接；当 SSE 不可用或发生中断时，自动降级为轮询查询任务状态，并在需要时可尝试重连 SSE。
- 降级判定建议（契约层面的行为约定）：例如 SSE 连接报错/关闭，或超过一定时间未收到任何事件（可由后端定期发送心跳事件来避免误判）。
- 最终结果仍需通过结果接口可查询、可恢复（例如页面刷新/断线恢复场景）。

#### Jobs API（路径与请求体）

**POST /api/v1/jobs**

功能：创建 Job（同时自动创建 Project），支持两种输入形态：

1) `application/json`（URL 类来源）

```json
{
	"sourceType": "youtube",
	"sourceUrl": "https://www.youtube.com/watch?v=...",
	"title": "optional"
}
```

2) `multipart/form-data`（上传文件）

- `sourceType`: 固定为 `upload`
- `file`: 视频文件
- `title`: optional

响应（两种方式一致）：

```json
{
	"jobId": "...",
	"projectId": "...",
	"status": "queued",
	"createdAtMs": 1738030000000
}
```

**GET /api/v1/jobs/{jobId}**

```json
{
	"jobId": "...",
	"projectId": "...",
	"type": "analyze_video",
	"status": "running",
	"stage": "transcribe",
	"progress": 0.42,
	"error": null,
	"updatedAtMs": 1738030000456
}
```

**POST /api/v1/jobs/{jobId}/cancel**（可选）

```json
{ "ok": true }
```

**GET /api/v1/jobs/{jobId}/events**（SSE）

- 支持请求头 `Last-Event-ID`（best-effort 断线续传）

#### Job Logs API（MVP：全量按文件落盘，HTTP 提供 tail）

**GET /api/v1/jobs/{jobId}/logs?limit=200&cursor=...**

- `cursor`：服务端返回的 opaque cursor（推荐实现为“文件字节偏移量”或“行号游标”）
- 响应：

```json
{
	"items": [
		{"tsMs":1738030000456,"level":"INFO","message":"...","stage":"transcribe"}
	],
	"nextCursor": "..."
}
```

### 3) 分析结果（Result：可渲染产物）

- 获取最新分析结果接口：返回项目的最新结果，包含：
	- 视频内容对应的思维导图 graph（nodes/edges）
	- 视频内容对应的笔记 note（tiptap json）
	- 笔记模块/章节对应的关键帧截图信息（以 asset 引用为主）
	- 视频内容时段划分 chapters（用于前端点击跳转到对应时间播放）

#### Results API

**GET /api/v1/projects/{projectId}/results/latest**

- Auth：同 Base（如启用 bearer，则该接口必须受保护）
- 若项目不存在：404（`PROJECT_NOT_FOUND`）
- 若项目存在但尚无结果：404（`RESULT_NOT_FOUND`）

响应（示例）：

```json
{
	"resultId": "6a5c...",
	"projectId": "2d2f...",
	"schemaVersion": "2026-01-29",
	"createdAtMs": 1738030000000,
	"chapters": [
		{
			"chapterId": "c01...",
			"idx": 0,
			"title": "Intro",
			"summary": "...",
			"startMs": 0,
			"endMs": 60000,
			"keyframes": [
				{
					"assetId": "a01...",
					"idx": 0,
					"timeMs": 12000,
					"caption": "..."
				}
			]
		}
	],
	"highlights": [
		{
			"highlightId": "h01...",
			"chapterId": "c01...",
			"idx": 0,
			"text": "...",
			"timeMs": 15000
		}
	],
	"mindmap": {
		"nodes": [{"id": "n1", "label": "Intro"}],
		"edges": [{"id": "e1", "source": "n1", "target": "n2"}]
	},
	"note": {
		"type": "doc",
		"content": []
	},
	"assetRefs": [
		{
			"assetId": "a01...",
			"kind": "screenshot"
		}
	]
}
```

备注：结果中建议保留一个“轻量版本标识”（例如 result_schema_version 或 pipeline_version 的简化形式），用于区分结果结构/算法迭代；不要求前端 UI 使用。

### 4) 用户编辑（Note / Mindmap / Keyframes）

- 更新笔记标题/内容接口：用于用户编辑后保存。
- 更新思维导图接口：用于用户编辑节点/连线后保存。
- 更新关键帧/图片关联接口：用于把图片（截图/用户提供）与某个章节/笔记模块进行绑定或替换。

建议约定：

- 图片更新尽量以“导入为项目 Asset 后再引用”为主；用户提供本地路径或远程 URL 可作为导入来源，但不要把外部路径作为唯一存储真相。

### 5) 搜索

- 搜索接口：根据关键词搜索笔记（MVP 可先做标题/摘要；后续再扩展到 transcript/RAG）。

#### Search API

**GET /api/v1/search**

Query Parameters:

- `query` string（必填，非空；大小写不敏感）
- `limit` number（可选，默认 20；范围 1..200）
- `cursor` string（可选，opaque cursor）

响应：Cursor Pagination（统一）

```json
{
	"items": [
		{
			"projectId": "2d2f...",
			"chapterId": "c01..."
		}
	],
	"nextCursor": null
}
```

说明：

- `items[].projectId` 必填，用于跳转到 Project。
- `items[].chapterId` 可选：当 query 命中章节标题/摘要或 highlights 文本时，后端尽力返回可定位章节；否则为 `null`。
- 排序与分页：稳定排序（推荐按 `projects.updatedAtMs desc, projects.projectId desc`），cursor 编码最后一条的排序键。

错误：query 为空

```json
{
	"error": {
		"code": "VALIDATION_ERROR",
		"message": "Query must be non-empty",
		"details": {"reason": "invalid_query"},
		"requestId": "req_01J..."
	}
}
```

### 6) 模型与提供方配置

- 模型 API 设置接口：用于配置当前使用的模型提供方与参数（例如云端 API、或本地 Ollama）；需要明确是否持久化与适用范围（桌面端/本机）。

#### Analyze Settings API（非敏感读取）

**GET /api/v1/settings/analyze**

功能：返回当前生效的“分析/LLM 相关配置”的非敏感字段。

关键约束：

- **永不返回 API key**
- **永不落盘 API key**（Key 只允许从 env 或运行态注入获取，例如请求头）

响应（示例）：

```json
{
	"provider": "llm",
	"baseUrl": "https://integrate.api.nvidia.com/v1",
	"model": "minimax-2.1",
	"timeoutS": 60,
	"allowRulesFallback": true,
	"debug": false
}
```

字段说明：

- `provider`: string（`llm` | `rules`；MVP 可扩展）
- `baseUrl`: string | null（LLM provider base URL；不含 key）
- `model`: string | null
- `timeoutS`: number
- `allowRulesFallback`: boolean（当 LLM 不可用/配置缺失时是否允许 rules fallback）
- `debug`: boolean（仅允许输出安全元数据，不输出 prompt/response）

错误：settings 持久化文件存在但不可解析（示例）

```json
{
	"error": {
		"code": "VALIDATION_ERROR",
		"message": "Invalid settings file",
		"details": {"reason": "invalid_settings_file"},
		"requestId": "req_01J..."
	}
}
```

#### Settings 存储（非敏感落盘）

默认位置：`DATA_DIR/settings.json`

建议 JSON 形态（只允许非敏感字段）：

```json
{
	"analyze": {
		"provider": "llm",
		"baseUrl": "https://integrate.api.nvidia.com/v1",
		"model": "minimax-2.1",
		"timeoutS": 60,
		"allowRulesFallback": true,
		"debug": false
	}
}
```

运行态 Key 读取约束（不落盘）：

- 环境变量：`LLM_API_KEY`
- 可选：请求头注入（例如 `X-LLM-API-KEY`）

---

# SQLite 表结构（契约草案）

目标：支撑上述接口（Project / Job / Result / Assets / Chapters 等），并满足：

- 核心实体（projects/jobs/results/assets/chapters）主键统一使用 UUID（`TEXT`）。
- 顺序/排序使用 `INTEGER`（例如 `idx`）。
- 复杂结构（mindmap、tiptap json、transcript）先用 `TEXT` 存 JSON，后续需要再拆表。

时间字段建议统一用 Unix 毫秒：`INTEGER`（例如 `created_at`）。

## 1) projects（项目）

用途：项目列表/详情、承载视频来源信息、指向最新结果。

字段：

- `id` TEXT PRIMARY KEY
- `title` TEXT NOT NULL
- `source_type` TEXT NOT NULL  -- youtube | bilibili | local_file | upload_asset
- `source_url` TEXT           -- 平台类来源
- `source_file_path` TEXT     -- 仅桌面端允许（引用外部路径）
- `source_asset_id` TEXT      -- 如果是 upload_asset，则引用 assets.id
- `duration_ms` INTEGER
- `latest_result_id` TEXT     -- 指向 results.id
- `created_at` INTEGER NOT NULL
- `updated_at` INTEGER NOT NULL
- `deleted_at` INTEGER

索引建议：

- `projects(updated_at)`
- `projects(source_type)`

## 2) jobs（长任务）

用途：创建分析任务、SSE 推进度、轮询状态、关联产出 result。

字段：

- `id` TEXT PRIMARY KEY
- `project_id` TEXT NOT NULL
- `type` TEXT NOT NULL        -- analyze_video（MVP）/ export / index_for_rag ...
- `status` TEXT NOT NULL      -- queued | running | succeeded | failed | canceled
- `progress` REAL             -- 0~1
- `stage` TEXT                -- downloading/transcribing/segmenting/...
- `result_id` TEXT            -- succeeded 后关联 results.id
- `idempotency_key` TEXT      -- 可空，避免重复提交
- `error_code` TEXT
- `error_message` TEXT
- `error_details_json` TEXT
- `created_at` INTEGER NOT NULL
- `updated_at` INTEGER NOT NULL
- `started_at` INTEGER
- `finished_at` INTEGER
- `canceled_at` INTEGER

约束/索引建议：

- 外键：`jobs.project_id -> projects.id`
- 索引：`jobs(project_id, created_at DESC)`
- 可选唯一：`UNIQUE(project_id, type, idempotency_key)`（当 idempotency_key 非空时）

## 3) results（分析结果）

用途：获取最新分析结果（可渲染产物）。

字段：

- `id` TEXT PRIMARY KEY
- `project_id` TEXT NOT NULL
- `schema_version` TEXT       -- 轻量版本标识（可选但建议保留）
- `created_at` INTEGER NOT NULL

-- 结构化 JSON（先存 TEXT）
- `mindmap_json` TEXT NOT NULL           -- graph: nodes/edges
- `note_tiptap_json` TEXT NOT NULL       -- tiptap/prosemirror doc
- `transcript_json` TEXT                 -- 可选：segments（带时间戳）

-- 为搜索/列表优化的派生字段（可选）
- `summary` TEXT
- `note_plaintext` TEXT
- `transcript_text` TEXT

约束/索引建议：

- 外键：`results.project_id -> projects.id`
- 索引：`results(project_id, created_at DESC)`

## 4) chapters（内容分段/时段划分）

用途：章节列表与时间跳转（start_ms/end_ms）。

字段：

- `id` TEXT PRIMARY KEY         -- chapter_id
- `result_id` TEXT NOT NULL
- `idx` INTEGER NOT NULL        -- 章节顺序
- `title` TEXT NOT NULL
- `summary` TEXT
- `start_ms` INTEGER NOT NULL
- `end_ms` INTEGER NOT NULL
- `extra_json` TEXT

约束/索引建议：

- 外键：`chapters.result_id -> results.id`
- 索引：`chapters(result_id, idx)`

## 5) chapter_keyframes（章节多图关联，推荐新增）

用途：每章关联多张图（关键帧/用户图），支持排序与可选时间点。

字段：

- `id` TEXT PRIMARY KEY
- `chapter_id` TEXT NOT NULL
- `asset_id` TEXT NOT NULL
- `idx` INTEGER NOT NULL        -- 在该章节内的顺序
- `time_ms` INTEGER             -- 可选：更精确的跳转点
- `caption` TEXT

约束/索引建议：

- 外键：`chapter_keyframes.chapter_id -> chapters.id`
- 外键：`chapter_keyframes.asset_id -> assets.id`
- 索引：`chapter_keyframes(chapter_id, idx)`
- 可选唯一：`UNIQUE(chapter_id, asset_id)`（避免重复绑定）

## 6) highlights（章节重点）

用途：每章的重点列表；前端点击可按 `time_ms` 跳转。

字段：

- `id` TEXT PRIMARY KEY
- `chapter_id` TEXT NOT NULL
- `idx` INTEGER NOT NULL
- `text` TEXT NOT NULL
- `time_ms` INTEGER             -- 可选：更精确跳转点
- `extra_json` TEXT

约束/索引建议：

- 外键：`highlights.chapter_id -> chapters.id`
- 索引：`highlights(chapter_id, idx)`

说明：highlights 默认不强制绑定图片；如需显示配图，可用 `time_ms` 在 chapter_keyframes 中选择最接近的一张，或未来扩展 `highlights.asset_id`（可空）。

## 7) assets（资源/图片/上传文件）

用途：管理截图、用户图片、上传文件等；避免把外部路径作为唯一真相。

字段：

- `id` TEXT PRIMARY KEY         -- asset_id
- `project_id` TEXT NOT NULL
- `kind` TEXT NOT NULL          -- screenshot | upload | user_image | cover
- `origin` TEXT NOT NULL        -- generated | uploaded | remote
- `mime` TEXT
- `width` INTEGER
- `height` INTEGER
- `file_path` TEXT              -- 建议存相对 DATA_DIR 的相对路径
- `remote_url` TEXT
- `sha256` TEXT
- `created_at` INTEGER NOT NULL

约束/索引建议：

- 外键：`assets.project_id -> projects.id`
- 索引：`assets(project_id, kind, created_at DESC)`
- 可选索引：`assets(sha256)`（用于去重）

---

# 资源访问（Assets Serving）

## 1) 资源元信息

**GET /api/v1/assets/{assetId}**

- Auth：同 Base（如启用 bearer，则该接口必须受保护）
- Project scope：后端必须校验该 asset 属于当前用户可访问的 project（即使路径中没有 projectId）
- Path safety：后端仅可从 `DATA_DIR` 下的相对路径读取（safe-join / 防目录穿越）

```json
{
	"assetId": "...",
	"projectId": "...",
	"kind": "screenshot",
	"origin": "generated",
	"mime": "image/jpeg",
	"width": 1280,
	"height": 720,
	"createdAtMs": 1738030000000,
	"contentUrl": "/api/v1/assets/.../content"
}
```

## 2) 资源内容（支持 Range）

**GET /api/v1/assets/{assetId}/content**

- 支持 `Range: bytes=start-end`（播放器/大文件常用）
- 若带 Range：返回 `206 Partial Content`，并包含 `Content-Range`；否则返回 `200`
- 建议响应头：`Accept-Ranges: bytes`

示例（Range 请求）：

```http
GET /api/v1/assets/..../content
Range: bytes=0-1048575
```

响应：

```http
HTTP/1.1 206 Partial Content
Accept-Ranges: bytes
Content-Range: bytes 0-1048575/9999999
Content-Type: video/mp4
```

## 8) model_settings（模型与提供方配置）

用途：实现“模型 API 设置接口”（桌面端/本机）。

字段：

- `id` INTEGER PRIMARY KEY      -- 可固定为 1（单配置）
- `provider` TEXT NOT NULL      -- openai | ollama | ...
- `base_url` TEXT
- `model` TEXT
- `api_key_ref` TEXT            -- 建议存 Keychain 引用，不存明文
- `options_json` TEXT
- `updated_at` INTEGER NOT NULL

## 9) 搜索（可选：FTS5）

若要实现关键词搜索，建议增加 FTS5 虚拟表（索引 title/summary/plaintext）：

- `notes_fts(project_id, result_id, title, content)`

其中 content 可用 `results.note_plaintext`（由 tiptap json 派生生成），避免直接对大 JSON 做 LIKE。

