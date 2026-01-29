# Story 9.1: [BE/core] 笔记保存 API（覆盖式更新 + updatedAtMs）

Status: ready-for-dev

## Story

As a 用户,
I want 编辑笔记后可以保存并在下次打开时恢复,
so that 我的复习提纲不会丢。

## Acceptance Criteria

1. Given 提交笔记保存请求（TipTap JSON）When 保存成功 Then 覆盖更新当前 Result 的 note 字段并返回 `updatedAtMs`（或等价）。
2. Then 请求/响应不包含敏感信息或绝对路径；失败返回统一错误 envelope。

## Tasks / Subtasks

- [ ] 定义 note schema（存 JSON）与 API 路径（以 8.1 契约/约定为准）(AC: 1)
- [ ] 覆盖式更新语义：以 projectId/latestResultId 定位写入 (AC: 1)
- [ ] updatedAtMs/ETag（可选）用于前端对账与最小冲突处理 (AC: 1)
- [ ] 错误处理：result 不存在/项目不存在/校验失败 (AC: 2)

## Dev Notes

- MVP 不做结果版本化：保存覆盖当前 result。

### References

- _bmad-output/planning-artifacts/epics.md

## Dev Agent Record

### Agent Model Used

GPT-5.2
