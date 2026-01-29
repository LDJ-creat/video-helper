# Story 9.6: [BE/core] 关键帧/图片关联更新 API（绑定/替换/排序）

Status: ready-for-dev

## Story

As a 用户,
I want 调整关键帧与章节/笔记模块的关联关系,
so that 我能把最有用的画面固定在对应章节。

## Acceptance Criteria

1. Given 提交关键帧绑定更新 When 请求合法 Then 服务更新关联关系并在下次读取 Result 时可见。
2. Then 不能把 asset 绑定到不属于该项目的章节。

## Tasks / Subtasks

- [ ] 定义 binding 更新 API：支持 chapterId 绑定、排序、可选替换/解绑 (AC: 1)
- [ ] 服务端校验：assetId 属于 project；chapterId 属于 project (AC: 2)
- [ ] 持久化：asset 表增加 chapterId/order；或单独 binding 表（选其一并写清）(AC: 1)

## Dev Notes

- 这条 story 直接影响结果页的“每章关键帧”展示顺序。

### References

- _bmad-output/planning-artifacts/epics.md

## Dev Agent Record

### Agent Model Used

GPT-5.2
