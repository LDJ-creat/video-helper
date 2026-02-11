# 暂定需要的接口

> 目标：把关键契约写成“可复制/可校验”的形态，避免多人/多代理实现时自行发挥。

## API Contract（强约束：Schema + 示例）

### Base

- Base URL: `/api/v1`
- Auth：本地默认关闭；远程模式启用 `Authorization: Bearer <token>`
	- 涉及“写入/删除密钥（secret）”的接口：无论本地/远程，均要求启用 Bearer（或明确的本地 loopback-only 保护开关），避免无意暴露写入口
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
	- `contentBlocks`：统一的“内容块 + highlights + keyframes + 时间锚点”渲染入口
	- 关键帧图片（keyframes）直接内联 `contentUrl`，前端无需二次请求拿路径

#### Results API

**GET /api/v1/projects/{projectId}/results/latest**

- Auth：同 Base（如启用 bearer，则该接口必须受保护）
- 若项目不存在：404（`PROJECT_NOT_FOUND`）
- 若项目存在但尚无结果：404（`RESULT_NOT_FOUND`）

响应（示例）：

说明（vNext，LLM-plan 统一产物）：

- `contentBlocks`：作为“内容重点 + 关键帧 + 时间锚点”的统一渲染入口（后端由同一次 plan 生成，保证一致性）。
- `mindmap.nodes[*].data.targetBlockId` / `targetHighlightId`：用于把思维导图节点与内容精确关联（联动锚点）。
- 不再单独返回顶层 `chapters` / `highlights` / `note`，避免重复与不必要的 payload。

```json
{
	"resultId": "6a5c...",
	"projectId": "2d2f...",
	"schemaVersion": "2026-02-06",
	"pipelineVersion": "0",
	"createdAtMs": 1738030000000,
	"contentBlocks": [
		{
			"blockId": "b01...",
			"idx": 0,
			"title": "Intro",
			"startMs": 0,
			"endMs": 60000,
			"highlights": [
				{
					"highlightId": "h01...",
					"idx": 0,
					"text": "...",
					"startMs": 12000,
					"endMs": 18000,
					"keyframe": {
						"assetId": "a01...",
						"contentUrl": "/api/v1/assets/a01.../content",
						"timeMs": 15000
					}
				}
			]
		}
	],
	"mindmap": {
		"nodes": [
			{
				"id": "n0",
				"type": "root",
				"label": "视频主题",
				"level": 0,
				"data": {}
			},
			{
				"id": "n1",
				"type": "topic",
				"label": "Intro",
				"level": 1,
				"data": {"targetBlockId": "b01..."}
			},
			{
				"id": "n2",
				"type": "detail",
				"label": "Key Point",
				"level": 2,
				"data": {"targetBlockId": "b01...", "targetHighlightId": "h01..."}
			}
		],
		"edges": [
			{"id": "e1", "source": "n0", "target": "n1", "label": null},
			{"id": "e2", "source": "n1", "target": "n2", "label": "..."}
		]
	},
	"assetRefs": [
		{
			"assetId": "v01...",
			"kind": "video",
			"contentUrl": "/api/v1/assets/v01.../content"
		}
	]
}
```

备注：结果中建议保留一个“轻量版本标识”（例如 result_schema_version 或 pipeline_version 的简化形式），用于区分结果结构/算法迭代；不要求前端 UI 使用。

### 4) 用户编辑（Note / Mindmap / Keyframes）

目标：冻结“写入类接口”路径/字段/错误码，避免 FE/其它代理自行发挥。

通用约定：

- 写入目标：只写 `GET /projects/{projectId}/results/latest` 所返回的 **latest result**（覆盖式更新，不做结果版本化）。
- 成功响应：统一返回 `{ "updatedAtMs": number }`，并返回响应头 `ETag: W/"{updatedAtMs}"`（best-effort 作为前端对账锚点）。

#### 保存笔记（TipTap JSON）

**PUT /api/v1/projects/{projectId}/results/latest/note**

请求（`application/json`）：支持两种形态（推荐 1）：

1) 包一层 `note`：

```json
{
	"note": {
		"type": "doc",
		"content": []
	}
}
```

2) 直接传 TipTap JSON 根对象：

```json
{
	"type": "doc",
	"content": []
}
```

最小校验：

- `note` 必须是 object
- `note.type` 必须是非空字符串
- `note.content` 缺省时会补 `[]`；若存在则必须是 array

响应（200）：

```json
{ "updatedAtMs": 1738030000456 }
```

错误：

- 404：`PROJECT_NOT_FOUND` | `RESULT_NOT_FOUND`
- 400：`VALIDATION_ERROR`
- 500：`INTERNAL_ERROR`

#### 保存思维导图（nodes/edges）

**PUT /api/v1/projects/{projectId}/results/latest/mindmap**

请求（`application/json`）：支持两种形态（推荐 1）：

1) 包一层 `mindmap`：

```json
{
	"mindmap": {
		"nodes": [{"id": "n1", "type": "topic", "label": "Intro", "level": 1, "data": {}}],
		"edges": [{"id": "e1", "source": "n1", "target": "n2"}]
	}
}
```

2) 直接传 mindmap 根对象：

```json
{
	"nodes": [{"id": "n1", "type": "topic", "label": "Intro", "level": 1, "data": {}}],
	"edges": [{"id": "e1", "source": "n1", "target": "n2"}]
}
```

最小校验（MVP，但要可控）：

- `nodes`/`edges` 必须是 array
- `nodes[*].id` 必须是非空字符串，且全局唯一
- `nodes[*].type` 必须是 `root` | `topic` | `detail`
- `nodes[*].level` 必须是 0、1 或 2
- `edges[*]` 必须包含 `id/source/target`，并且 `source/target` 必须引用已存在的 node id
- 字段白名单（出现额外字段会 400）：
	- node：`id` `type` `label` `level` `position` `data`
	- edge：`id` `source` `target` `label`

响应（200）：

```json
{ "updatedAtMs": 1738030000456 }
```

错误：

- 404：`PROJECT_NOT_FOUND` | `RESULT_NOT_FOUND`
- 400：`VALIDATION_ERROR`
- 500：`INTERNAL_ERROR`

#### 编辑章节（标题/顺序/可选时间范围）

#### 编辑内容块（标题/顺序/可选时间范围）

**PATCH /api/v1/projects/{projectId}/results/latest/blocks/{blockId}**

请求（`application/json`）：以下字段均可选（至少提供 1 个）。

```json
{
	"title": "New Title",
	"idx": 1,
	"startMs": 0,
	"endMs": 60000
}
```

语义：

- `title`：修改内容块标题（必须是非空字符串）
- `idx`：修改内容块排序；服务端会按 `idx` 重新排序并归一化为 `0..n-1`
- `startMs/endMs`：默认禁用；仅当环境变量 `ALLOW_CHAPTER_TIME_EDIT=1` 时允许修改，并校验：
	- `startMs/endMs` 必须是整数，且 `0 <= startMs < endMs`
	- MVP：仅校验本 block 的范围合法性（不做全局 overlap 校验）

响应（200）：

```json
{ "updatedAtMs": 1738030000456 }
```

错误：

- 404：`PROJECT_NOT_FOUND` | `RESULT_NOT_FOUND` | `CHAPTER_NOT_FOUND`
- 400：`VALIDATION_ERROR` | `CHAPTER_TIME_EDIT_DISABLED`
- 500：`INTERNAL_ERROR`

#### 绑定/解绑 Highlight Keyframe（精确到 highlight）

**PUT /api/v1/projects/{projectId}/results/latest/highlights/{highlightId}/keyframe**

请求（`application/json`）：绑定时必须给 `assetId`；解绑时 `assetId=null`。

```json
{
	"assetId": "a01...",
	"timeMs": 12000,
	"caption": "..."
}
```

解绑：

```json
{ "assetId": null }
```

语义：

- 该接口是“覆盖语义”：每个 highlight 最多绑定 1 个 `keyframe`。
- 资产必须属于同一 project；否则返回 `ASSET_NOT_IN_PROJECT`。
- 后端会把 `contentUrl` 写入 `highlight.keyframe.contentUrl`（形如 `/api/v1/assets/{assetId}/content`）。

响应（200）：

```json
{ "updatedAtMs": 1738030000456 }
```

错误：

- 404：`PROJECT_NOT_FOUND` | `RESULT_NOT_FOUND` | `CHAPTER_NOT_FOUND` | `ASSET_NOT_FOUND`
- 400：`VALIDATION_ERROR` | `ASSET_NOT_IN_PROJECT`
- 500：`INTERNAL_ERROR`

建议约定：

- 图片更新尽量以“导入为项目 Asset 后再引用”为主；用户提供本地路径或远程 URL 可作为导入来源，但不要把外部路径作为唯一存储真相。

### 5) 搜索

- 搜索接口：根据关键词搜索笔记（MVP 可先做标题/摘要；后续再扩展到 transcript/RAG）。

返回锚点（vNext）：

- 优先返回 `highlightId`（更精确），同时返回所属 `blockId`。
- 若只命中内容块标题，则仅返回 `blockId`。

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
			"blockId": "b01...",
			"highlightId": "h01..."
		}
	],
	"nextCursor": null
}
```

说明：

- `items[].projectId` 必填，用于跳转到 Project。
- `items[].blockId` 可选：命中内容块标题或其 highlights 时，后端尽力返回定位 block；否则为 `null`。
- `items[].highlightId` 可选：当 query 命中某条 highlight 文本时，后端尽力返回更精确的定位锚点；否则为 `null`。
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

（已移除）原 `GET/PUT /api/v1/settings/analyze`：其能力由 vNext 的 `GET /api/v1/settings/llm/catalog` + `GET/PUT /api/v1/settings/llm/active` + secret 接口覆盖。

（已移除）原 `/api/v1/settings/analyze/secret*`：由于方案A需要“按 provider 维度”管理多个 apiKey，该接口无法表达 `providerId`，统一由 vNext 的 provider secret 接口替代。

#### LLM 配置中心（vNext，方案A）

目标：

- 前端无需手填 baseUrl；后端提供主流 provider 与模型清单（Catalog）
- 用户可对 provider 配置/修改/删除 apiKey（write-only），并能在列表中看到 hasKey 状态
- 用户可选择当前使用的 provider + model；后续分析任务默认使用该选择
- 在创建分析任务前可进行最小连通性测试，失败立即返回可行动错误

安全约束：

- 任意 secret 写接口与 active 修改接口必须受保护（Bearer 或明确 local-only 防护开关）
- apiKey 永不回显、不得进入日志与错误 details

##### Catalog

**GET /api/v1/settings/llm/catalog**

功能：返回后端内置的 provider 与模型列表（非用户配置）。

响应（示例）：

```json
{
	"providers": [
		{
			"providerId": "openrouter",
			"displayName": "OpenRouter",
			"hasKey": true,
			"secretUpdatedAtMs": 1738030000000,
			"models": [
				{"modelId": "openrouter:anthropic/claude-3.5-sonnet", "displayName": "Claude 3.5 Sonnet"},
				{"modelId": "openrouter:openai/gpt-4o-mini", "displayName": "GPT-4o mini"}
			]
		}
	],
	"updatedAtMs": 1738030000000
}
```

字段说明：

- `providers[].hasKey`：表示该 provider 是否已配置 apiKey（不会回显 key）。
- `providers[].secretUpdatedAtMs`：当已配置 key 时返回。

##### Secret（write-only）

**PUT /api/v1/settings/llm/providers/{providerId}/secret**

Request Body（示例）：

```json
{
	"apiKey": "..."
}
```

Response：`{"ok": true}`

**DELETE /api/v1/settings/llm/providers/{providerId}/secret**

Response：`{"ok": true}`

##### Active（当前使用的 provider + model）

**GET /api/v1/settings/llm/active**

Response（示例）：

```json
{
	"providerId": "openrouter",
	"modelId": "openrouter:anthropic/claude-3.5-sonnet",
	"hasKey": true,
	"updatedAtMs": 1738030000000
}
```

字段说明：

- `hasKey`：表示当前 provider 是否已配置 apiKey（不会回显 key）。

**PUT /api/v1/settings/llm/active**

Request Body（示例）：

```json
{
	"providerId": "openrouter",
	"modelId": "openrouter:anthropic/claude-3.5-sonnet"
}
```

Response：`{"ok": true}`

##### Test（连通性/鉴权/模型可用性）

**POST /api/v1/settings/llm/active/test**

功能：对当前 active selection 做最小连通性测试（例如一次轻量 chat/completions）。

Response（示例）：

```json
{
	"ok": true,
	"latencyMs": 234
}
```

错误：缺 key（示例）

```json
{
	"error": {
		"code": "VALIDATION_ERROR",
		"message": "Missing credentials",
		"details": {"reason": "missing_credentials"},
		"requestId": "req_01J..."
	}
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

#### Settings 存储（vNext）

Deprecated：不再写入 `DATA_DIR/settings.json`。

vNext 使用 SQLite：

- 当前选择：`llm_active`
- 每个 provider 的加密密钥：`llm_profile_secrets`

可选运维兜底：仍允许通过环境变量 `LLM_API_KEY` 注入（不落盘），但 UI 场景以 Secret Store 为准。

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
- `schema_version` TEXT       -- 轻量版本标识（建议保留）
- `pipeline_version` TEXT     -- 流水线/算法版本（建议保留）
- `created_at_ms` INTEGER NOT NULL
- `updated_at_ms` INTEGER NOT NULL

-- 结构化 JSON（先存 TEXT）
- `content_blocks_json` TEXT NOT NULL    -- vNext 主渲染入口：blocks(highlights+time+highlight.keyframe)
- `mindmap_json` TEXT NOT NULL           -- graph: nodes/edges（node 可 targetBlockId/targetHighlightId）
- `note_json` TEXT NOT NULL              -- 导出/同步用结构化 note（暂不在 results/latest 返回）
- `asset_refs_json` TEXT NOT NULL        -- 仅需保留 video 类资源引用（截图已内联在 highlight.keyframe.contentUrl）

-- 可选：为搜索/回溯保留的派生字段
- `transcript_json` TEXT                 -- segments（带时间戳）

-- 为搜索/列表优化的派生字段（可选）
- `summary` TEXT
- `note_plaintext` TEXT
- `transcript_text` TEXT

约束/索引建议：

- 外键：`results.project_id -> projects.id`
- 索引：`results(project_id, created_at DESC)`

## 4) assets（资源/图片/上传文件）

用途：管理截图、用户图片、上传文件等；避免把外部路径作为唯一真相。

字段：

- `id` TEXT PRIMARY KEY         -- asset_id
- `project_id` TEXT NOT NULL
- `kind` TEXT NOT NULL          -- video | screenshot | upload | user_image | cover
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

