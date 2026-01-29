# Story 4.6: [BE/core] 取消与重试（可选取消 + 失败重试）

Status: ready-for-dev

## Story

As a 用户,
I want 取消正在运行的任务并对失败任务发起重试,
so that 我能在资源不足或配置修复后继续完成闭环。

## Acceptance Criteria

1. Given Job 为 running When `POST /api/v1/jobs/{jobId}/cancel` Then 返回 `{ ok: true }`，Job 最终进入 `canceled`，并停止调度后续 stage，尽力终止 subprocess。
2. Given Job 为 failed When 请求重试接口 Then 在同一 Project 下创建新 Job（新 jobId）并返回 queued；契约与普通 Job 一致。

## Tasks / Subtasks

- [ ] 设计 cancel endpoint：cooperative cancellation（DB 标记 + worker 轮询检查）(AC: 1)
- [ ] subprocess 终止 best-effort（ffmpeg/yt-dlp 等）并避免僵尸进程 (AC: 1)
- [ ] 设计 retry endpoint：仅允许 failed/canceled（按产品选择）→ 创建新 Job 并记录 parentJobId（可选）(AC: 2)
- [ ] 错误码：不可取消/状态不允许/不存在/并发限制等 (AC: 1,2)

## Dev Notes

- 取消语义是 cooperative：不能承诺立即终止，但必须尽快停止后续 stage。
- 并发上限（MAX_CONCURRENT_JOBS）与队列/claim 在 5.1 实现。

### References

- _bmad-output/planning-artifacts/epics.md

## Dev Agent Record

### Agent Model Used

GPT-5.2
