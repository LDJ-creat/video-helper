# Story 10.4: [FE/web] 设置页（provider/model 参数 + 可理解提示）

Status: ready-for-dev

## Story

As a 运维/高级用户,
I want 在 Web 端配置模型提供方与参数,
so that 我能在不同环境下跑通分析。

## Acceptance Criteria

1. Given 填写 provider/baseUrl/model 等参数 When 保存成功 Then 提示立即生效，并可通过健康检查或下一次 job 失败信息验证。

## Tasks / Subtasks

- [x] 设置页表单：provider/baseUrl/model（不包含 Key 明文持久化）(AC: 1)
- [x] 保存/读取 API 对接，错误提示可理解（解析 error envelope）(AC: 1)
- [x] 增加快速入口：跳转 health 或显示当前健康检查结果（可选）(AC: 1)

## Dev Notes

- 若需要用户输入 Key：建议仅作为本次会话 header 使用，不写入本地存储（按架构约束）。

### References

- _bmad-output/planning-artifacts/epics.md

## Dev Agent Record

### Agent Model Used

GPT-5.2 (Gemini 2.0 Flash Experimental)

### Implementation Summary

**完成时间**: 2026-02-04

**实现文件**:
- `apps/web/src/lib/contracts/settingsTypes.ts` - 设置类型定义
- `apps/web/src/lib/api/settingsApi.ts` - 设置 API 客户端（读取/更新）
- `apps/web/src/lib/api/settingsQueries.ts` - React Query hooks
- `apps/web/src/lib/api/endpoints.ts` - 添加设置端点
- `apps/web/src/lib/api/queryKeys.ts` - 添加设置查询键
- `apps/web/src/components/features/SettingsForm.tsx` - 设置表单组件
- `apps/web/src/app/(main)/settings/page.tsx` - 设置页面

**技术实现**:
1. 表单支持配置 provider (openai/ollama/anthropic/custom)、baseUrl、model
2. 使用 React Query 的 `useQuery` 和 `useMutation` 管理设置的读取和更新
3. 实现表单验证（必填字段、URL 格式）
4. 显示保存成功/失败提示，并自动刷新缓存
5. 按架构约束不保存 API Key 到本地存储，页面提示用户通过环境变量提供

**测试方法**: 手动验证（npm run dev 启动开发服务器，访问 /settings 路径）

