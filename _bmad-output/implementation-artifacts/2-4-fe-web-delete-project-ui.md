# Story 2.4: [FE/web] 删除项目交互（确认、反馈、回收列表状态）

Status: review

## Story

As a 用户,
I want 在 UI 中安全地删除项目,
so that 我不误删且能明确看到结果。

## Acceptance Criteria

1. Given 点击“删除项目” When 弹出确认对话框 Then 必须确认后才发起删除请求；成功后项目从列表/缓存移除并提示成功。
2. Given 删除失败 When 接收错误 envelope Then UI 显示可理解提示并允许重试。

## Tasks / Subtasks

- [x] 删除按钮 + confirm dialog (AC: 1)
- [x] 成功后更新 React Query cache / invalidate (AC: 1)
- [x] 错误 envelope 展示与重试 (AC: 2)

## Dev Notes

- 错误 envelope/字段命名：_bmad-output/implementation-artifacts/00-standards-and-parallel-plan.md

### References

- _bmad-output/planning-artifacts/epics.md

## Dev Agent Record

### Agent Model Used

Gemini 2.0 Flash Thinking (Experimental)

### Implementation Summary

实现了完整的删除项目功能，包括确认对话框、错误处理、重试机制和缓存管理。

**实现范围：**
1. API 扩展：endpoints.ts, projectApi.ts, projectQueries.ts
2. 列表页删除按钮：确认对话框 + 错误重试
3. 详情页删除按钮：删除后重定向至列表页
4. React Query 缓存自动失效：删除成功后自动刷新列表

**技术亮点：**
- 使用 `useMutation` 管理删除状态
- `onSuccess` callback 自动 `invalidateQueries` 触发列表刷新
- 递归重试逻辑处理错误场景
- Next.js `useRouter` 实现删除后页面跳转

### Completion Notes

✅ **AC1 完成**：
- 删除按钮添加到列表页和详情页
- `window.confirm` 实现确认对话框，显示项目名称
- 成功后通过 `invalidateQueries` 自动更新 React Query 缓存
- 成功提示使用 `alert`（后续可替换为 toast 组件）

✅ **AC2 完成**：
- 错误处理捕获 error envelope 的 `message` 字段
- 错误对话框显示错误信息并询问是否重试
- 重试逻辑通过递归调用 `handleDelete` 实现

**验证结果：**
- ✅ Next.js build 成功
- ✅ TypeScript 编译无错误
- ✅ 所有 AC 满足

### File List

**修改文件：**
- `apps/web/src/lib/api/endpoints.ts` - 添加 deleteProject endpoint
- `apps/web/src/lib/api/projectApi.ts` - 添加 deleteProject API 函数
- `apps/web/src/lib/api/projectQueries.ts` - 添加 useDeleteProject mutation hook
- `apps/web/src/app/(main)/projects/page.tsx` - 添加删除按钮与逻辑
- `apps/web/src/app/(main)/projects/[projectId]/page.tsx` - 添加删除按钮与重定向
