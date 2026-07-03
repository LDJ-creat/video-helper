## Video Helper — Project Makefile (cross-platform)
##
## Notes:
## - Windows: uses cmd.exe for basic targets; PowerShell (pwsh/powershell) for .ps1 scripts.
## - macOS/Linux: uses /bin/sh; uses the provided .sh equivalents for script-based targets.
## - Requirements (by target): pnpm, uv, node, docker.

.DEFAULT_GOAL := help

ifeq ($(OS),Windows_NT)
SHELL := cmd.exe
.SHELLFLAGS := /c
PWSH ?= powershell
else
SHELL := /bin/sh
.SHELLFLAGS := -c
PWSH ?= pwsh
endif

# ─────────────────────────────────────────────────────────────────────────────
# Configurable variables
# ─────────────────────────────────────────────────────────────────────────────

WEB_API_BASE ?= http://127.0.0.1:8000

SMOKE_API_BASE ?= http://127.0.0.1:8000
SMOKE_TIMEOUT_SEC ?= 1200

# Optional: override to test a specific URL
# Example:
#   make core-smoke SMOKE_API_BASE=http://127.0.0.1:8000 SMOKE_URL=https://...
SMOKE_URL ?=
SMOKE_SOURCE_TYPE ?= bilibili
SMOKE_PROFILE ?= $(SMOKE_SOURCE_TYPE)

# Derived args for wrapper-based closed-loop smoke.
SMOKE_WRAPPER_ARGS_SH := --api-base-url "$(SMOKE_API_BASE)" --timeout-sec "$(SMOKE_TIMEOUT_SEC)" --profile "$(SMOKE_PROFILE)"
SMOKE_WRAPPER_ARGS_WIN := -ApiBaseUrl "$(SMOKE_API_BASE)" -TimeoutSec $(SMOKE_TIMEOUT_SEC) -Profile "$(SMOKE_PROFILE)"
ifneq ($(strip $(SMOKE_URL)),)
SMOKE_WRAPPER_ARGS_SH += --url "$(SMOKE_URL)"
SMOKE_WRAPPER_ARGS_WIN += -Url "$(SMOKE_URL)"
endif

BENCHMARK_API_BASE ?= http://127.0.0.1:8000
BENCHMARK_PROFILE ?= short-local
BENCHMARK_DATA_DIR ?=
JOB_ID ?=
PROJECT_ID ?=
BENCHMARK_SKIP_START_BACKEND ?= 0


# ─────────────────────────────────────────────────────────────────────────────
# Help
# ─────────────────────────────────────────────────────────────────────────────

.PHONY: help
help:
	@echo Video Helper - Make targets
	@echo.
	@echo Frontend (apps/web):
	@echo   make web-dev           Start Next.js dev server
	@echo   make web-build-check   Check if web can build (next build)
	@echo.
	@echo Desktop (apps/desktop):
	@echo   make desktop-dev       Start desktop dev helper (starts core+web+electron)
	@echo   make desktop-compile   Compile Electron main process (TypeScript)
	@echo   make desktop-build-all Full desktop release build ^(Windows: build-all.ps1; macOS/Linux: build-all.sh^)
	@echo.
	@echo Backend (services/core):
	@echo   make core-dev          Start backend dev server (uv run python main.py)
	@echo   make core-build        Package backend via PyInstaller (build_backend.py)
	@echo   make core-test         Run all backend tests (pytest services/core/tests)
	@echo   make core-smoke        Closed-loop smoke (starts backend by default)
	@echo   make core-benchmark    Run evaluation benchmark (PROFILE=short-local)
	@echo   make core-benchmark-report  Report for existing JOB_ID
	@echo   make core-benchmark-rubric  Interactive human rubric scoring
	@echo   make core-metrics      Aggregate succeeded job metrics from DATA_DIR
	@echo.
	@echo Docker:
	@echo   make docker-up         Pull latest images and start (docker-compose.yml)
	@echo   make docker-up-dev     Build local core/web images and start (override dev)
	@echo.
	@echo Variables (override like: make core-smoke SMOKE_API_BASE=http://127.0.0.1:8000):
	@echo   WEB_API_BASE=$(WEB_API_BASE)
	@echo   SMOKE_API_BASE=$(SMOKE_API_BASE)
	@echo   SMOKE_TIMEOUT_SEC=$(SMOKE_TIMEOUT_SEC)
	@echo   SMOKE_URL=$(SMOKE_URL)
	@echo   SMOKE_PROFILE=$(SMOKE_PROFILE) (legacy alias: SMOKE_SOURCE_TYPE)


# ─────────────────────────────────────────────────────────────────────────────
# Backend (services/core)
# ─────────────────────────────────────────────────────────────────────────────

.PHONY: core-dev
core-dev:

ifeq ($(OS),Windows_NT)
	$(PWSH) -NoProfile -ExecutionPolicy Bypass -File scripts\core-dev.ps1
else
	./scripts/core-dev.sh
endif


# ─────────────────────────────────────────────────────────────────────────────
# Frontend (apps/web)
# ─────────────────────────────────────────────────────────────────────────────

.PHONY: web-dev
web-dev:

ifeq ($(OS),Windows_NT)
	cd apps\web && pnpm dev
else
	cd apps/web && pnpm dev
endif

.PHONY: web-build-check
web-build-check:

ifeq ($(OS),Windows_NT)
	set "API_BASE_URL=$(WEB_API_BASE)" && set "NEXT_PUBLIC_API_BASE_URL=$(WEB_API_BASE)" && cd apps\web && pnpm build
else
	cd apps/web && API_BASE_URL="$(WEB_API_BASE)" NEXT_PUBLIC_API_BASE_URL="$(WEB_API_BASE)" pnpm build
endif


# ─────────────────────────────────────────────────────────────────────────────
# Desktop (apps/desktop)
# ─────────────────────────────────────────────────────────────────────────────

.PHONY: desktop-dev
desktop-dev:

ifeq ($(OS),Windows_NT)
	node apps\desktop\scripts\dev.js
else
	node apps/desktop/scripts/dev.js
endif

.PHONY: desktop-compile
desktop-compile:

ifeq ($(OS),Windows_NT)
	cd apps\desktop && pnpm compile
else
	cd apps/desktop && pnpm compile
endif

.PHONY: desktop-build-all
desktop-build-all:

ifeq ($(OS),Windows_NT)
	$(PWSH) -NoProfile -ExecutionPolicy Bypass -File apps\desktop\scripts\build-all.ps1
else
	bash apps/desktop/scripts/build-all.sh
endif


# ─────────────────────────────────────────────────────────────────────────────
# Backend (services/core)
# ─────────────────────────────────────────────────────────────────────────────

.PHONY: core-build
core-build:

ifeq ($(OS),Windows_NT)
	cd services\core && uv run python scripts\build_backend.py
else
	cd services/core && uv run python scripts/build_backend.py
endif

.PHONY: core-test
core-test:

ifeq ($(OS),Windows_NT)
	cd services\core && uv run pytest -q tests
else
	cd services/core && uv run pytest -q tests
endif

.PHONY: core-smoke
core-smoke:

ifeq ($(OS),Windows_NT)
	$(PWSH) -NoProfile -ExecutionPolicy Bypass -File scripts\smoke-closed-loop.ps1 $(SMOKE_WRAPPER_ARGS_WIN)
else
	bash scripts/smoke-closed-loop.sh $(SMOKE_WRAPPER_ARGS_SH)
endif

.PHONY: core-benchmark
core-benchmark:

ifeq ($(OS),Windows_NT)
	$(PWSH) -NoProfile -ExecutionPolicy Bypass -File scripts\benchmark-closed-loop.ps1 -ApiBaseUrl "$(BENCHMARK_API_BASE)" -Profile "$(BENCHMARK_PROFILE)" $(if $(filter 1,$(BENCHMARK_SKIP_START_BACKEND)),-SkipStartBackend,)
else
	bash scripts/benchmark-closed-loop.sh --api-base-url "$(BENCHMARK_API_BASE)" --profile "$(BENCHMARK_PROFILE)" $(if $(filter 1,$(BENCHMARK_SKIP_START_BACKEND)),--skip-start-backend,)
endif

.PHONY: core-benchmark-report
core-benchmark-report:
ifeq ($(strip $(JOB_ID)),)
	$(error JOB_ID is required for core-benchmark-report)
endif
ifeq ($(OS),Windows_NT)
	cd services\core && uv run python scripts\run_benchmark.py --mode report --job-id "$(JOB_ID)" --project-id "$(PROJECT_ID)" --api-base "$(BENCHMARK_API_BASE)" $(if $(BENCHMARK_DATA_DIR),--data-dir "$(BENCHMARK_DATA_DIR)",) $(if $(MERGE_RUBRIC),--merge-rubric,) $(if $(RUBRIC_SCORES),--rubric-scores "$(RUBRIC_SCORES)",)
else
	cd services/core && uv run python scripts/run_benchmark.py --mode report --job-id "$(JOB_ID)" --project-id "$(PROJECT_ID)" --api-base "$(BENCHMARK_API_BASE)" $(if $(BENCHMARK_DATA_DIR),--data-dir "$(BENCHMARK_DATA_DIR)",) $(if $(MERGE_RUBRIC),--merge-rubric,) $(if $(RUBRIC_SCORES),--rubric-scores "$(RUBRIC_SCORES)",)
endif

.PHONY: core-benchmark-rubric
core-benchmark-rubric:
ifeq ($(strip $(JOB_ID)),)
	$(error JOB_ID is required for core-benchmark-rubric)
endif
ifeq ($(strip $(PROJECT_ID)),)
	$(error PROJECT_ID is required for core-benchmark-rubric)
endif
ifeq ($(OS),Windows_NT)
	cd services\core && uv run python scripts\score_human_rubric.py --profile "$(BENCHMARK_PROFILE)" --job-id "$(JOB_ID)" --project-id "$(PROJECT_ID)" --api-base "$(BENCHMARK_API_BASE)"
else
	cd services/core && uv run python scripts/score_human_rubric.py --profile "$(BENCHMARK_PROFILE)" --job-id "$(JOB_ID)" --project-id "$(PROJECT_ID)" --api-base "$(BENCHMARK_API_BASE)"
endif

.PHONY: core-metrics
core-metrics:
ifeq ($(OS),Windows_NT)
	cd services\core && uv run python scripts\collect_all_job_metrics.py $(if $(BENCHMARK_DATA_DIR),--data-dir "$(BENCHMARK_DATA_DIR)",)
else
	cd services/core && uv run python scripts/collect_all_job_metrics.py $(if $(BENCHMARK_DATA_DIR),--data-dir "$(BENCHMARK_DATA_DIR)",)
endif


# Create / ensure a Python virtual environment for services/core and run main.py
.PHONY: core-venv
core-venv:
	@echo Ensuring virtualenv at services/core/.venv
ifeq ($(OS),Windows_NT)
	@if not exist services\core\.venv\Scripts\python.exe (
		cd services\core && python -m venv .venv && echo Created virtualenv at services\core\.venv
	) else (
		echo Virtualenv already exists at services\core\.venv
	)
else
	@bash -c "[ -x services/core/.venv/bin/python ] || (cd services/core && python3 -m venv .venv && echo Created virtualenv at services/core/.venv)"
endif

.PHONY: core-run
# Starts the backend `main.py` using the virtualenv Python. Will create venv if missing.
core-run:
	@echo Starting backend (will create venv if missing)...
ifeq ($(OS),Windows_NT)
	@if not exist services\core\.venv\Scripts\python.exe (
		$(MAKE) core-venv
	)
	@services\core\.venv\Scripts\python.exe services\core\main.py
else
	@bash -c "[ -x services/core/.venv/bin/python ] || $(MAKE) core-venv"
	@services/core/.venv/bin/python services/core/main.py
endif



# ─────────────────────────────────────────────────────────────────────────────
# Docker
# ─────────────────────────────────────────────────────────────────────────────

.PHONY: docker-up
docker-up:
	docker compose pull
	docker compose up -d

.PHONY: docker-up-dev
docker-up-dev:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build
