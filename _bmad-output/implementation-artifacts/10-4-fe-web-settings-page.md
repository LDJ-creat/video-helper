# Story 10.4: [FE/web] 设置页（provider/model 参数 + 可理解提示）

Status: ready-for-dev

## Story

As a 运维/高级用户,
I want 在 Web 端配置模型提供方与参数,
so that 我能在不同环境下跑通分析。

## Acceptance Criteria

1. Given 填写 provider/baseUrl/model 等参数 When 保存成功 Then 提示立即生效，并可通过健康检查或下一次 job 失败信息验证。

## Tasks / Subtasks

- [ ] 设置页表单：provider/baseUrl/model（不包含 Key 明文持久化）(AC: 1)
- [ ] 保存/读取 API 对接，错误提示可理解（解析 error envelope）(AC: 1)
- [ ] 增加快速入口：跳转 health 或显示当前健康检查结果（可选）(AC: 1)

## Dev Notes

- 若需要用户输入 Key：建议仅作为本次会话 header 使用，不写入本地存储（按架构约束）。

### References

- _bmad-output/planning-artifacts/epics.md

## Dev Agent Record

### Agent Model Used

GPT-5.2
