# Story 9.6: [BE/core] 关键帧/图片关联更新 API（绑定/替换/排序）

Status: review

## Story

As a 用户,
I want 调整关键帧与章节/笔记模块的关联关系,
so that 我能把最有用的画面固定在对应章节。

## Acceptance Criteria

1. Given 提交关键帧绑定更新 When 请求合法 Then 服务更新关联关系并在下次读取 Result 时可见。
2. Then 不能把 asset 绑定到不属于该项目的章节。

## Tasks / Subtasks

- [x] 定义 binding 更新 API：支持 chapterId 绑定、排序、可选替换/解绑 (AC: 1)
- [x] 服务端校验：assetId 属于 project；chapterId 属于 project (AC: 2)
- [x] 持久化：asset 表增加 chapterId/order；或单独 binding 表（选其一并写清）(AC: 1)

## Dev Notes

- 这条 story 直接影响结果页的“每章关键帧”展示顺序。

### References

- _bmad-output/planning-artifacts/epics.md

## Dev Agent Record

### Agent Model Used

GPT-5.2

### Completion Notes

- 新增 `PUT /api/v1/projects/{projectId}/results/latest/chapters/{chapterId}/keyframes`：以“替换语义”更新某章节的 keyframes 列表（绑定/排序/解绑）。
- 服务端校验：chapterId 必须存在于该 project 的 latest result；每个 assetId 必须存在且 `asset.projectId == projectId`（否则 `ASSET_NOT_IN_PROJECT`）。
- 持久化策略：
	- 章节内排序与绑定关系写入 `results.chapters[*].keyframes`（结果读取接口直接可见）；
	- 同步更新 `assets.chapter_id/time_ms` 作为资源侧 linkage hint（用于 metadata 与后续处理）。

### Tests

- `services/core/tests/test_editing_apis.py::TestEditingAPIs::test_update_keyframes_validates_project_scope_and_persists`

## File List

- services/core/src/core/app/api/editing.py
- services/core/src/core/schemas/editing.py
- services/core/src/core/contracts/error_codes.py
- services/core/src/core/db/models/result.py
- services/core/src/core/db/session.py
- services/core/src/core/pipeline/stages/assemble_result.py
- services/core/src/core/main.py
- services/core/tests/test_editing_apis.py
- _bmad-output/implementation-artifacts/9-6-be-core-asset-binding.md

## Change Log

- 2026-02-04：新增 keyframes 绑定更新 API（绑定/替换/排序/解绑）并补齐校验与测试。

