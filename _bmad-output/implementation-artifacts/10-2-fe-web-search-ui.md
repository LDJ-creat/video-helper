# Story 10.2: [FE/web] 搜索 UI（输入、结果列表、定位跳转）

Status: ready-for-dev

## Story

As a 用户,
I want 在 UI 中搜索并跳转到对应项目/章节,
so that 我能用“检索”替代翻找。

## Acceptance Criteria

1. Given 输入关键词并提交 When 返回结果 Then 可点击打开对应项目（或定位到章节）。

## Tasks / Subtasks

- [x] 搜索输入框 + debounce（可选）+ 提交 (AC: 1)
- [x] 结果列表：分页/加载更多（cursor）(AC: 1)
- [x] 点击结果：跳转到 project 或带 chapter 定位参数 (AC: 1)

## Dev Notes

- 搜索结果 DTO 与分页形态必须与统一标准一致。

### References

- _bmad-output/planning-artifacts/epics.md

## Dev Agent Record

### Agent Model Used

GPT-5.2 (Gemini 2.0 Flash Experimental)

### Implementation Summary

**完成时间**: 2026-02-04

**实现文件**:
- `apps/web/src/lib/contracts/searchTypes.ts` - 搜索类型定义
- `apps/web/src/lib/api/searchApi.ts` - 搜索 API 客户端
- `apps/web/src/lib/api/searchQueries.ts` - React Query hooks
- `apps/web/src/lib/api/endpoints.ts` - 添加搜索端点
- `apps/web/src/lib/api/queryKeys.ts` - 添加搜索查询键
- `apps/web/src/components/features/SearchInput.tsx` - 搜索输入组件（300ms debounce）
- `apps/web/src/components/features/SearchResults.tsx` - 搜索结果列表（无限滚动）
- `apps/web/src/components/features/SearchResultItem.tsx` - 单个结果项（支持项目/章节跳转）
- `apps/web/src/app/(main)/search/page.tsx` - 搜索页面

**技术实现**:
1. 使用 React Query 的 `useInfiniteQuery` 实现无限滚动分页
2. 搜索输入框使用 `useEffect` + `setTimeout` 实现 300ms debounce
3. 搜索结果支持跳转到项目详情或结果页面（带章节定位参数）
4. 遵循项目现有的 API 客户端模式和错误处理规范

**测试方法**: 手动验证（npm run dev 启动开发服务器，访问 /search 路径）

