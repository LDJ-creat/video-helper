# Story 3.2: [BE/core] 创建 Job（上传文件的 multipart 形态）

Status: review

## Story

As a 用户,
I want 通过 Web 上传视频文件并创建分析任务,
so that 我不用依赖本地路径作为真相。

## Acceptance Criteria

1. Given 提交 `POST /api/v1/jobs`（multipart，含 `sourceType=upload` 与 `file`）When 合法 Then 文件落盘到 DATA_DIR 受控目录并创建 Project + Job；DB 只保存相对路径。
2. Given 上传文件类型不支持 When 校验 Then 返回统一错误 envelope 且 message 可理解。

## Tasks / Subtasks

- [x] multipart 接收与服务端落盘（DATA_DIR/{projectId}/...）(AC: 1)
- [x] 文件类型/大小校验与错误 envelope (AC: 2)
- [x] DB 只存相对路径；返回 DTO 不含本机路径 (AC: 1)

## Dev Notes

- 路径安全与相对路径：_bmad-output/implementation-artifacts/00-standards-and-parallel-plan.md

### References

- _bmad-output/planning-artifacts/epics.md

## Dev Agent Record

### Agent Model Used

GPT-5.2

### Completion Notes

- Implemented `POST /api/v1/jobs` multipart branch: `sourceType=upload` + `file`.
- Stored uploaded file under `DATA_DIR/{projectId}/uploads/{jobId}/...` and persisted ONLY relative path in DB.
- Validated file extension and enforced a max size via `MAX_UPLOAD_MB` (default 500MB).
- Tests: `python -m unittest discover -s services/core/tests -p "test*.py"`.

## File List

- services/core/src/core/app/api/jobs.py
- services/core/src/core/storage/layout.py
- services/core/src/core/db/models/project.py
- services/core/tests/test_jobs_create.py

## Change Log

- 2026-02-01: Add multipart upload job creation with safe DATA_DIR storage and tests.
