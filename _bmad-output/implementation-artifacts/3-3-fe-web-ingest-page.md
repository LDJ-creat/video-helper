# Story 3.3: [FE/web] 导入页（URL/上传双入口）

Status: ready-for-dev

## Story

As a 用户,
I want 在一个页面里选择“粘贴链接”或“上传文件”创建分析,
so that 我能用最适合我的方式导入视频。

## Acceptance Criteria

1. Given 选择“粘贴链接” When 提交 Then UI 调用 `POST /api/v1/jobs` JSON 并跳转到 Job 详情/进度页。
2. Given 选择“上传文件” When 提交 Then UI 发起 multipart 请求并显示上传中状态与错误提示。

## Tasks / Subtasks

- [ ] URL 表单：校验/提交/错误提示 (AC: 1)
- [ ] 上传表单：loading/progress（可选）/error 状态 (AC: 2)
- [ ] 成功后路由到 job 页面（与 4.5 对齐）(AC: 1,2)

## Dev Notes

- 允许先 mock；错误 envelope 解析必须统一。

### References

- _bmad-output/planning-artifacts/epics.md
- _bmad-output/planning-artifacts/ux-design-specification.md

## Dev Agent Record

### Agent Model Used

GPT-5.2
