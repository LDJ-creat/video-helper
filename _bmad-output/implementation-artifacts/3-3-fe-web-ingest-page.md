# Story 3.3: [FE/web] 导入页（URL/上传双入口）

Status: review

## Story

As a 用户,
I want 在一个页面里选择“粘贴链接”或“上传文件”创建分析,
so that 我能用最适合我的方式导入视频。

## Acceptance Criteria

1. Given 选择“粘贴链接” When 提交 Then UI 调用 `POST /api/v1/jobs` JSON 并跳转到 Job 详情/进度页。
2. Given 选择“上传文件” When 提交 Then UI 发起 multipart 请求并显示上传中状态与错误提示。

## Tasks / Subtasks

- [x] URL 表单：校验/提交/错误提示 (AC: 1)
- [x] 上传表单：loading/progress（可选）/error 状态 (AC: 2)
- [x] 成功后路由到 job 页面（与 4.5 对齐）(AC: 1,2)

## Dev Notes

- 允许先 mock；错误 envelope 解析必须统一。

### References

- _bmad-output/planning-artifacts/epics.md
- _bmad-output/planning-artifacts/ux-design-specification.md

## Dev Agent Record

### Agent Model Used

Gemini 2.0 Flash Thinking (2026-02-01)

### Implementation Plan

实现了导入页面，提供 URL 粘贴和文件上传两种创建任务方式：

1. **类型定义**: 创建 `jobCreation.ts`，定义 Job 创建的请求和响应类型
2. **API 层**: 实现 `jobCreationApi.ts`（URL 和文件上传）和 `jobCreationQueries.ts`（mutation hooks）
3. **UI 页面**: 实现 `/ingest/page.tsx`，包含 Tab 切换和两个表单

### Completion Notes

✅ 所有 AC 已满足：
- AC1: URL 表单提交时调用 `POST /api/v1/jobs`（JSON），成功后跳转到 `/jobs/{jobId}`
- AC2: 上传表单发起 multipart 请求，显示 loading 状态和错误提示

技术实现：
- 使用 React Query 的 `useMutation` hook 处理表单提交
- URL 表单实现客户端 URL 验证
- 文件上传表单限制只接受视频文件
- 统一错误处理，解析 Error Envelope
- 集成 HealthBanner 组件显示依赖状态
- 更新主页添加导航链接

## File List

- `apps/web/src/lib/contracts/jobCreation.ts` (新增)
- `apps/web/src/lib/api/endpoints.ts` (修改)
- `apps/web/src/lib/api/jobCreationApi.ts` (新增)
- `apps/web/src/lib/api/jobCreationQueries.ts` (新增)
- `apps/web/src/app/(main)/ingest/page.tsx` (新增)
- `apps/web/src/app/page.tsx` (修改)

## Change Log

- 2026-02-01: 实现 Ingest Page，支持 URL 和文件上传两种导入方式

