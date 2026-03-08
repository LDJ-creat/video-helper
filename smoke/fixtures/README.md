# Smoke fixture

把 CI 冒烟测试用的本地视频放在同目录下：

- `smoke-fixture.mp4`

CI 工作流会在构建阶段将其复制到 `apps/desktop/release/smoke-fixture.mp4` 并随 artifact 上传，随后在 smoke 阶段以 `sourceType=upload` 的方式上传到后端执行闭环冒烟。

建议：
- 选择包含音频的人声/音乐片段（便于转写链路覆盖）
- 时长尽量短（PR 门禁 smoke 建议 20-60 秒），避免 CI 时间/体积膨胀
- 如果需要更长视频（例如 6 分钟）做更强覆盖，建议改为 `workflow_dispatch` 或定时任务使用，避免阻塞 PR
