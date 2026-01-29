# Story 8.2: [BE/core] Assets API：metadata + content（安全路径 + 可选 Range）

Status: ready-for-dev

## Story

As a 用户,
I want 前端能通过受控接口获取关键帧图片内容,
so that 不暴露绝对路径且避免目录穿越。

## Acceptance Criteria

1. Given assetId 存在且属于 projectId When 请求 assets content endpoint Then 返回正确图片流；路径解析通过单一 safe-join 工具限制在 DATA_DIR 内。
2. Given assetId 不属于 project 或路径越界 When 请求 Then 返回统一错误 envelope（不泄露路径）。
3. （可选）支持 Range/断点读取，至少不破坏普通 GET。

## Tasks / Subtasks

- [ ] 实现 assets metadata endpoint（返回 mimeType/size/width/height/chapterId/timeMs 等）(AC: 1)
- [ ] 实现 content streaming endpoint：Content-Type 正确；禁止目录穿越 (AC: 1,2)
- [ ] safe-join/safe-open 工具集中封装，供删除/其它文件访问复用 (AC: 1,2)
- [ ] （可选）Range 支持：处理 `Range` 头并返回 206；否则忽略 Range 也要稳定 (AC: 3)

## Dev Notes

- DB 只存相对路径；任何错误响应不得包含绝对路径。
- 契约以 8.1 为准；统一标准见 00-standards。

### References

- _bmad-output/planning-artifacts/epics.md
- api.md

## Dev Agent Record

### Agent Model Used

GPT-5.2
