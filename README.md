# video-helper

本仓库采用 monorepo 结构：

- 前端：`apps/web`（Next.js App Router + TS + Tailwind）
- 后端：`services/core`（FastAPI + SQLite + SQLAlchemy + Alembic，使用 uv 管理）

规划与实现上下文：

- `_bmad-output/planning-artifacts/architecture.md`
- `_bmad-output/implementation-artifacts/00-standards-and-parallel-plan.md`
- `_bmad-output/implementation-artifacts/01-worktree-branch-assignment.md`
- `_bmad-output/implementation-artifacts/02-agent-claim-board.md`

## Python/后端环境约定

- 本仓库唯一的 Python 项目在 `services/core`（使用 `uv` 管理依赖）。
- 后端运行/测试的标准环境为 `services/core/.venv`（也即 `uv run ...` 实际使用的虚拟环境）。
- 仓库根目录下若存在 `.venv`，通常是误创建/历史遗留，不作为标准；建议删除以避免 VS Code/命令行选错解释器。

常用命令（在 `services/core` 目录执行）：

- 运行后端：`uv run python main.py`
- 运行单测：`uv run pytest -q`
