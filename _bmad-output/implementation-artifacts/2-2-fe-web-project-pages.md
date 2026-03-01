# Story 2.2: [FE/web] 项目列表页与项目详情页（含分页/虚拟化）

Status: review

## Story

As a 用户,
I want 在 Web 端浏览项目列表并进入项目详情,
so that 我可以快速切换不同视频的复习资产。

## Acceptance Criteria

1. Given 项目数量较多 When 滚动项目列表 Then 使用虚拟化或分段加载，保持交互流畅；翻页使用 cursor。
2. Given 某项目存在 `latestResultId` When 点击“打开” Then 路由到该项目结果页入口（未就绪则显示状态页）。

## Tasks / Subtasks

- [x] Projects 列表页：React Query + cursor；必要时虚拟化/增量加载 (AC: 1)
- [x] 项目详情页：展示来源/更新时间/latestResultId 等 (AC: 2)
- [x] 打开按钮路由：latestResultId 有/无分支逻辑 (AC: 2)

## Dev Notes

- 可先按契约 mock；统一契约见：_bmad-output/implementation-artifacts/00-standards-and-parallel-plan.md

### References

- _bmad-output/planning-artifacts/epics.md
- _bmad-output/planning-artifacts/ux-design-specification.md

## Dev Agent Record

### Agent Model Used

Gemini 2.0 Flash Thinking (Experimental)

### Implementation Plan

实现了完整的 Projects 列表页与详情页，严格遵循 `api.md` 中的 API 契约规范。

**关键技术决策：**
1. **契约驱动开发**：所有类型定义严格对齐 api.md 中的 Projects API 规范
2. **React Query 分页**：使用 `useInfiniteQuery` 实现 cursor-based pagination
3. **TypeScript 类型安全**：完整的类型定义确保编译时类型检查
4. **Next.js App Router**：使用 Next.js 15+ 的 App Router 模式（use() hook for async params）

**组件结构：**
- `lib/contracts/projectTypes.ts`：Project 类型定义与 API 响应类型
- `lib/api/projectApi.ts`：API 客户端函数（fetchProjects, fetchProjectDetail）
- `lib/api/projectQueries.ts`：React Query hooks（useProjects, useProjectDetail）
- `app/(main)/projects/page.tsx`：Projects 列表页，支持无限滚动加载
- `app/(main)/projects/[projectId]/page.tsx`：Project 详情页，根据 latestResultId 显示不同 UI

### Completion Notes

✅ **AC1 完成**：Projects 列表页使用 React Query 的 `useInfiniteQuery` 实现 cursor 分页，支持"加载更多"按钮。

✅ **AC2 完成**：Project 详情页展示所有元信息（来源、更新时间、latestResultId），并根据 `latestResultId` 是否存在显示不同UI：
- 有 latestResultId：显示"打开结果"按钮，路由到 `/projects/{projectId}/results`
- 无 latestResultId：显示"结果未就绪"提示

**验证结果：**
- ✅ Next.js build 成功（8个静态页面生成）
- ✅ TypeScript 编译无错误（仅 IDE 依赖加载提示，运行时正常）
- ✅ 所有文件遵循项目代码规范

**后续集成建议：**
- 待后端 API 就绪后，移除 mock 数据即可直接对接
- 可考虑添加 loading skeleton 提升用户体验
- 可添加错误边界（Error Boundary）处理 API 错误

### File List

**新增文件：**
- `apps/web/src/lib/contracts/projectTypes.ts`
- `apps/web/src/lib/api/projectApi.ts`
- `apps/web/src/lib/api/projectQueries.ts`

**修改文件：**
- `apps/web/src/lib/api/endpoints.ts`
- `apps/web/src/lib/api/queryKeys.ts`
- `apps/web/src/app/(main)/projects/page.tsx`
- `apps/web/src/app/(main)/projects/[projectId]/page.tsx`
