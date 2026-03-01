# Story 10.5: [BE/core] 方案A：服务端托管（加密）LLM 配置中心（Catalog + Secret + Active + Test）

Status: in-progress

## Story

As a Web/桌面端用户（高级配置）, I want 在 UI 中配置 LLM provider 参数与 API key，并让后端异步 Job 稳定读取到密钥,
so that 我不需要手工编辑环境变量且分析任务可跨重启持续运行。

## Scope

- 提供“主流模型提供商 + 模型列表”的后端 Catalog（前端无需手填 baseUrl 等）
- 支持用户对某个 provider 配置/修改/删除 apiKey，并在 provider 列表中区分已配置/未配置
- 支持选择当前使用的 provider + model（active selection），后续分析任务默认使用该选择
- 在创建分析 Job 前进行 LLM 连通性/鉴权测试，失败则立即返回可行动的错误

## Acceptance Criteria

1. Given 前端请求 Catalog When 调用 `GET /api/v1/settings/llm/catalog` Then 返回主流 provider 列表及其支持的模型（不包含任何用户 secret）。
2. Given 前端展示 provider 列表 When 调用 `GET /api/v1/settings/llm/catalog` Then 每个 provider 返回 `hasKey`（用于样式区分），且不得回显 key。
3. Given 用户配置或修改 apiKey When 调用 `PUT /api/v1/settings/llm/providers/{providerId}/secret` Then 后端加密持久化成功；任意响应与日志不包含 key 明文。
4. Given 用户删除 apiKey When 调用 `DELETE /api/v1/settings/llm/providers/{providerId}/secret` Then `hasKey=false` 且后端不再可用旧 key。
5. Given 用户选择当前使用的 provider+model When 调用 `PUT /api/v1/settings/llm/active` Then 后端持久化 active selection；后续 Job 默认使用该 selection。
	- 并且 `GET /api/v1/settings/llm/active` 返回 `hasKey` 以便前端渲染。
6. Given 用户保存选择或创建 Job 前检查 When 调用 `POST /api/v1/settings/llm/active/test` Then 后端用 active selection + 对应 secret 进行最小连通性测试（例如一次轻量 chat/completions），失败返回明确错误（例如 `INVALID_CREDENTIALS`/`PROVIDER_UNAVAILABLE`/`MODEL_NOT_FOUND`）。
7. Given 远程部署 When 调用任何写 secret/修改 active 的接口 Then 必须鉴权（Bearer 或明确 local-only 防护开关），未授权返回 `UNAUTHORIZED`。

## API Contract (must match api.md)

- `GET /api/v1/settings/llm/catalog`
- `PUT /api/v1/settings/llm/providers/{providerId}/secret`
- `DELETE /api/v1/settings/llm/providers/{providerId}/secret`
- `GET /api/v1/settings/llm/active`
- `PUT /api/v1/settings/llm/active`
- `POST /api/v1/settings/llm/active/test`

Reference: api.md（"LLM 配置中心（vNext，方案A）"）

## Data / Security Design (方案A)

- DB 为主存储：所有“用户配置/选择状态”存储在 SQLite。
- Catalog 为后端可信来源：provider/model 的 baseUrl 与支持模型列表由后端提供（可作为代码内静态数据或 seed 到 DB），前端只做展示与选择。
- 敏感密钥：加密存储（at-rest encryption），write-only。

推荐 SQLite 表（MVP，单用户）：

- `llm_profile_secrets`
	- `provider_id` TEXT PRIMARY KEY
	- `ciphertext` TEXT NOT NULL（base64）
	- `updated_at_ms` INTEGER NOT NULL

- `llm_active`
	- `id` INTEGER PRIMARY KEY CHECK(id = 1)
	- `provider_id` TEXT NOT NULL
	- `model_id` TEXT NOT NULL
	- `updated_at_ms` INTEGER NOT NULL

加密（MVP 推荐）：

- 使用对称加密（例如 Fernet / AES-GCM）对 `apiKey` 加密后持久化。
- 加密主密钥来源（二选一，需在 Dev Notes 中定最终方案）：
	- 方案 A1：环境变量 `SETTINGS_ENCRYPTION_KEY`（base64，部署侧管理）
	- 方案 A2：首次启动生成并写入 `DATA_DIR/secret.key`（需确保文件权限，Windows 可先做 best-effort）

硬约束：

- key 永不回显
- key 不进入日志
- error.details 不包含 key

关于是否保留 settings.json：

- 本 story 以 DB 为主存储，不再写入 settings.json。
- 可选兼容：启动时若检测到旧 settings.json，则一次性导入 DB 并记录迁移完成（导入成功后可删除或忽略文件）。

## Tasks / Subtasks

- [x] Catalog：提供后端 provider/model 清单（代码静态数据或 seed），并实现 `GET /api/v1/settings/llm/catalog` (AC: 1)
- [x] DB：创建 `llm_profile_secrets` / `llm_active` 表与 repo（get/set）(AC: 2,3,4,5)
- [x] 加密模块：密钥加载（A1/A2 二选一落地）+ encrypt/decrypt（Fernet 或 AES-GCM）(AC: 3,4)
- [ ] API：
	- [x] `PUT /api/v1/settings/llm/providers/{providerId}/secret`（write-only）(AC: 3)
	- [x] `DELETE /api/v1/settings/llm/providers/{providerId}/secret` (AC: 4)
	- [x] `GET /api/v1/settings/llm/active` / `PUT /api/v1/settings/llm/active` (AC: 5)
	- [x] `POST /api/v1/settings/llm/active/test`（最小连通性测试）(AC: 6)
- [ ] 鉴权/保护：为所有写接口与 test 启用 Bearer（或本地 loopback-only + 显式开关），未授权返回 `UNAUTHORIZED` (AC: 7)
- [ ] Job 启动前校验：在创建 Job 或 analyze stage 开始前，若 LLM 不可用则立即失败并归因（不等到转写后）(AC: 6)
- [ ] 测试：
	- [ ] catalog 返回稳定、包含预期 provider/model
	- [ ] profiles hasKey 逻辑（PUT secret 后 true，DELETE 后 false）
	- [ ] active selection 持久化与读取
	- [ ] active/test：缺 key、无效 key、provider 不可用、model 不存在的错误归因

## Dev Notes

- 当前仓库 `services/core/src/core/app/middleware/auth.py` 是占位符；本 story 需要落地“至少对写接口有效”的保护。
- 对于 UI：以 `hasKey` 区分“已配置/未配置”；不得回显 key。
- baseUrl 由后端 catalog 决定，前端不暴露/不允许手填（可选保留 `custom` provider 作为高级入口，默认隐藏）。
- 规则引擎（rules）与 fallback：不再对外暴露配置；若仍需兜底策略，应改为后端内部策略开关，不作为用户设置项。

## Dev Agent Record

### Agent Model Used

GPT-5.2

### Implementation Notes

- Catalog 静态清单：`services/core/src/core/llm/catalog.py`
- 接口：`GET /api/v1/settings/llm/catalog`（`services/core/src/core/app/api/settings.py`，已接入 secrets meta 计算 `hasKey`/`secretUpdatedAtMs`）
- DB 表：`llm_profile_secrets` / `llm_active`（SQLAlchemy models）
- Repo：`core.db.repositories.llm_settings`（get/set secret & active）
- 加密方案：A2（首次启动生成并写入 `DATA_DIR/secret.key`），算法 Fernet（`core.llm.secrets_crypto`）

### Tests

- `services/core/tests/test_llm_settings_catalog_api.py`
- `services/core/tests/test_llm_settings_repo.py`
- `services/core/tests/test_llm_settings_crypto.py`
- `services/core/tests/test_llm_settings_secret_api.py`
- `services/core/tests/test_llm_settings_active_api.py`
- `services/core/tests/test_llm_settings_active_test_api.py`
- `services/core/tests/test_llm_active_test_helper.py`

### File List

- services/core/pyproject.toml
- services/core/src/core/llm/catalog.py
- services/core/src/core/llm/secrets_crypto.py
- services/core/src/core/llm/active_test.py
- services/core/src/core/app/api/settings.py
- services/core/src/core/db/models/llm_settings.py
- services/core/src/core/db/repositories/llm_settings.py
- services/core/src/core/db/session.py
- services/core/src/core/schemas/settings.py
- services/core/tests/test_llm_settings_catalog_api.py
- services/core/tests/test_llm_settings_repo.py
- services/core/tests/test_llm_settings_crypto.py
- services/core/tests/test_llm_settings_secret_api.py
- services/core/tests/test_llm_settings_active_api.py
- services/core/tests/test_llm_settings_active_test_api.py
- services/core/tests/test_llm_active_test_helper.py

### Change Log

- 2026-02-05：新增 LLM Catalog 接口（AC1）
- 2026-02-05：新增 LLM settings DB 表与 repo（AC2/AC5 基础）
- 2026-02-05：新增密钥加密模块（A2 + Fernet，AC3/AC4 基础）
- 2026-02-05：新增 provider secret 写接口（PUT/DELETE，AC3/AC4）
- 2026-02-05：新增 active selection 读写接口（GET/PUT，AC5）
- 2026-02-05：新增 active/test 最小连通性测试接口（AC6）
