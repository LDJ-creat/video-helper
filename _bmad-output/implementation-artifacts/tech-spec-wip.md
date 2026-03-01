---
title: 'Video Helper 桌面端版本 (Electron vs Tauri 选型与实施规划)'
slug: 'video-helper-desktop'
created: '2026-02-21'
status: 'ready-for-development'
stepsCompleted: [1, 2, 3, 4]
tech_stack: ['Next.js 16', 'React 19', 'FastAPI', 'Python 3.12', 'Electron/Tauri', 'TypeScript']
files_to_modify:
  - 'apps/web/package.json'
  - 'apps/web/src/lib/api/apiClient.ts'
  - 'apps/web/src/lib/api/jobCreationApi.ts'
  - 'apps/web/src/lib/api/cookiesApi.ts'
  - 'apps/web/next.config.ts (or .js)'
code_patterns: ['FormData multipart upload', 'fetch() HTTP client', 'IPC bridge', 'Tauri commands', 'Electron preload']
test_patterns: []
---

# Tech-Spec: Video Helper 桌面端版本（Electron vs Tauri 选型与实施规划）

**创建时间：** 2026-02-21

---

## Overview

### Problem Statement

当前 Video Helper 是纯 Web 应用（Next.js 前端 + FastAPI 后端）。用户需要手动配置并启动后端服务，无法像原生桌面 App 那样一键打开即用。目标是：

1. 将应用打包为桌面端程序（Windows / macOS / Linux）
2. 复用现有 Next.js 前端代码，无需重写 UI
3. 在桌面端环境下调整部分功能实现（视频上传、Cookie 上传等）以充分利用系统文件访问能力

### Solution

在现有 Web 前端之上叠加一个桌面壳层（Electron 或 Tauri），将 FastAPI 后端作为子进程内嵌或单独捆绑运行。前端保持不变，仅针对桌面特有功能（文件读取、IPC 通信）做适配层。

### Scope

**In Scope：**
- Electron vs Tauri 选型深度对比
- 桌面壳层初始化方案（架构设计）
- 文件上传（视频、Cookie）在桌面端的实现差异与适配方案
- 后端（FastAPI）在桌面端的集成方案（子进程启动）
- 打包与分发方案概述

**Out of Scope：**
- 具体的 CI/CD 发布流水线搭建
- macOS 公证（Notarization）和代码签名细节
- 移动端（iOS/Android）
- 现有 Web 端功能变更（不变）

---

## 技术选型对比：Electron vs Tauri

### 关键维度对比表

| 维度 | Electron | Tauri |
|------|----------|-------|
| **渲染引擎** | 内置 Chromium（版本固定） | 系统 WebView（Edge/WebKit/GTK） |
| **安装包大小** | ~100-150 MB（含 Chromium + Node.js） | ~5-15 MB（复用系统 WebView） |
| **内存占用** | 较高（Chromium 进程开销） | 较低（系统 WebView 轻量） |
| **语言** | JS/TS（主/渲染进程）| Rust（后端命令）+ JS/TS（前端） |
| **与 Next.js 兼容性** | ✅ 极佳，可直接加载 Next.js 开发服务器或 export | ⚠️ 需要 Next.js `output: 'export'` 静态导出（无法使用 SSR/Server Actions） |
| **本地文件访问** | Node.js `fs` 模块（主进程）+ IPC | Tauri `dialog` & `fs` plugin（Rust 命令）+ invoke |
| **后端集成** | `child_process.spawn()` 启动 Python 进程 | `tauri-plugin-shell` sidecar 启动 Python 进程 |
| **原生 UI 能力** | 有限（主要依赖 web） | 系统原生弹窗、菜单、托盘等 |
| **安全模型** | 相对宽松（Node 集成可全局开启） | 默认最小权限，显式声明 IPC 权限 |
| **跨平台表现一致性** | ⭐⭐⭐⭐⭐（Chromium 保证） | ⭐⭐⭐（各平台 WebView 有差异） |
| **生态成熟度** | 非常成熟，大量案例（VSCode、Slack 等） | 较新但增长迅速（2.0 稳定版 2024 年） |
| **学习曲线** | 低（全 JS/TS） | 中（需了解 Rust 基础） |
| **热更新支持** | 简单（加载远端 URL 即可） | 需使用 `tauri-plugin-updater` |

---

### 针对本项目的具体分析

#### Next.js SSR 兼容性（关键制约因素）

当前项目 `apps/web` 使用 **Next.js 16 App Router**，包含：
- Server Components
- API Routes（`/api/*`）
- `next-intl` 中间件（i18n）

**Tauri 的限制**：Tauri 建议前端以静态文件方式提供（`next export`），而项目使用 App Router 的 Server Components 和 middleware，**无法直接 `output: 'export'`**。变通方案是在 Tauri 中仍将 Next.js 以 dev server / production server 形式运行，并通过 `customProtocol` 或 `localhost` 加载——这丧失了 Tauri 的主要优势之一，并引入了额外复杂度。

**Electron 的优势**：Electron 可以直接将 `BrowserWindow` 指向 `http://localhost:3000`（Next.js 开发/生产服务器），或对 Next.js 进行 standalone 导出后作为 Node.js 服务在主进程中启动。完全兼容现有路由和 Server Components。

#### 文件上传实现差异（核心关注点）

**Web 端现有实现（两个场景）：**

1. **视频上传** (`jobCreationApi.ts`)：
   - 用户通过 `<input type="file">` 选择本地视频
   - 前端构造 `FormData`，将 `File` 对象 `.append("file", file)`
   - 通过 `fetch()` POST 到 `http://localhost:8000/api/v1/jobs`（multipart/form-data）

2. **Cookie 上传** (`cookiesApi.ts`)：
   - 用户通过 `<input type="file" accept=".txt">` 选择 `.txt` 文件
   - 同 `FormData` + `fetch()` 方式上传到后端

**桌面端特有机会（但非必须）：**

在桌面端，可以用更高效的方式替代 multipart 上传——直接传递**本地文件路径**给后端，后端直接从文件系统读取，避免大文件的内存拷贝：

```
Web 端现有路径（保持可用）：
  选择文件 → 浏览器 File API → FormData → HTTP 上传 → 后端写入临时目录 → 处理

桌面端优化路径（可选）：
  系统文件选择器 → 获取本地绝对路径 → IPC 传递路径 → 后端直接读取
```

但这需要修改后端 API，增加复杂度。**推荐的实施策略是：** 优先保持现有 FormData 上传路径在桌面端继续可用（无需改动），将文件路径传递作为后续优化项。

#### 后端（FastAPI）集成方案

无论选 Electron 还是 Tauri，都需要将 FastAPI 进程打包并自动启动：

| 方案 | Electron | Tauri |
|------|----------|-------|
| 子进程启动 | `child_process.spawn('python', ['main.py'])` 或打包后的 exe | `tauri-plugin-shell` sidecar |
| Python 运行时 | 需捆绑 Python（PyInstaller 打包为单 exe）或要求用户安装 | 同左，PyInstaller sidecar |
| 端口管理 | 主进程负责动态分配端口，通过 IPC 告知渲染进程 | Rust 后端命令负责端口管理 |
| 健康检查 | 主进程轮询 `/api/v1/health` 确认后端就绪 | 同理 |

---

### 选型建议

> **推荐：Electron**

**核心理由：**

1. **Next.js SSR/App Router 零改造**：现有代码库无需任何修改，Electron 主进程直接启动 Next.js Production Server（`next start`）并加载 `http://localhost:3000`。
2. **团队上手成本低**：整个技术栈保持 TypeScript/JavaScript，无需引入 Rust。
3. **开发调试体验**：开发阶段可以直接把 `BrowserWindow` 指向运行中的 Next.js dev server，实现热重载。
4. **文件上传无需改造**：Electron 的 WebView 完整支持 `File` API 和 `FormData`，现有上传代码 100% 可用。

**Tauri 的适用场景（如未来切换）：**
- 如果决定将前端重构为纯 SPA（Vite + React，去掉 Next.js SSR）
- 对安装包体积有极高要求（目标 < 20MB）
- 团队有 Rust 能力

---

## Context for Development

### Codebase Patterns

- **API 调用**：所有前端 HTTP 请求通过 `apps/web/src/lib/api/apiClient.ts` 的 `apiFetch()` 发起，Base URL 由 `apps/web/src/lib/config.ts` 提供（推测为环境变量 `NEXT_PUBLIC_API_BASE_URL`）
- **文件上传**：使用浏览器原生 `FormData` + `File` 对象，通过 `fetch()` POST（multipart/form-data）
- **Cookie 上传**：`cookiesApi.ts` → `uploadCookiesFile(file: File)`，接口 `POST /api/v1/ytdlp/cookies`
- **视频上传**：`jobCreationApi.ts` → `createJobFromUpload(file, title, outputLanguage)`，接口 `POST /api/v1/jobs`

### Files to Reference

| File | Purpose |
| ---- | ------- |
| `apps/web/src/lib/api/apiClient.ts` | 核心 HTTP 客户端，Electron 适配需在此处修改 Base URL 注入方式 |
| `apps/web/src/lib/api/jobCreationApi.ts` | 视频上传实现，桌面端复用此逻辑无需改动 |
| `apps/web/src/lib/api/cookiesApi.ts` | Cookie 上传实现，桌面端复用此逻辑无需改动 |
| `apps/web/next.config.ts` | Next.js 配置，需添加 standalone 输出模式 |
| `services/core/src/core/app/main.py` | FastAPI 入口，子进程启动的目标 |

### Technical Decisions

1. **选型决定**：使用 **Electron**，保持 Next.js App Router 不变
2. **架构模式**：Electron 主进程负责启动 Next.js Production Server 和 FastAPI 子进程；`BrowserWindow` 加载 `http://localhost:3000`
3. **文件上传策略**：桌面端继续使用现有 `FormData + fetch()` 路径，无需改动。桌面端特有的"路径传递"优化作为 Future Work
4. **Python 运行时打包**：使用 PyInstaller 将 FastAPI 应用打包为独立可执行文件，捆绑到 Electron 的 `resources/` 目录

---

## Implementation Plan

### Phase 1：项目结构搭建

- [ ] **Task 1.1**：新建 `apps/desktop/` 目录，初始化 Electron 项目
  - 文件：`apps/desktop/package.json`, `apps/desktop/src/main.ts`, `apps/desktop/src/preload.ts`
  - 操作：`npm init`，安装 `electron`, `electron-builder`, `typescript`
  
- [ ] **Task 1.2**：配置 `apps/web/next.config.ts` 开启 standalone 输出
  - 文件：`apps/web/next.config.ts`
  - 操作：添加 `output: 'standalone'`，使 Next.js 可作为独立 Node.js 服务运行

### Phase 2：Electron 主进程开发

- [ ] **Task 2.1**：主进程启动 Next.js Production Server
  - 文件：`apps/desktop/src/main.ts`
  - 操作：使用 `child_process.fork()` 或 `spawn()` 运行 `node .next/standalone/server.js`；监听端口就绪后再打开窗口

- [ ] **Task 2.2**：主进程启动 FastAPI 子进程
  - 文件：`apps/desktop/src/main.ts`
  - 操作：`spawn()` 运行内嵌的 `backend.exe`（PyInstaller 构建产物）；健康检查轮询 `GET http://localhost:8000/api/v1/health`；将动态端口通过环境变量注入 Next.js 进程

- [ ] **Task 2.3**：实现优雅退出
  - 文件：`apps/desktop/src/main.ts`
  - 操作：监听 `app.on('before-quit')`，`SIGTERM` 子进程，等待退出后关闭

- [ ] **Task 2.4**：Preload 脚本（安全桥接）
  - 文件：`apps/desktop/src/preload.ts`
  - 操作：暴露最小化 IPC API：`window.electronAPI.getBackendUrl()` 供渲染进程获取实际后端端口

### Phase 3：前端适配（最小化改动）

- [ ] **Task 3.1**：API Base URL 动态注入
  - 文件：`apps/web/src/lib/config.ts`（或等效配置文件）
  - 操作：检测 `window.electronAPI` 是否存在，若是桌面端则从 IPC 获取 `backendUrl`，否则使用 `NEXT_PUBLIC_API_BASE_URL` 环境变量
  - 代码示意：
    ```ts
    export const config = {
      apiBaseUrl: (typeof window !== 'undefined' && (window as any).electronAPI)
        ? await (window as any).electronAPI.getBackendUrl()
        : process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8000'
    }
    ```

- [ ] **Task 3.2**：文件上传验证（无需改动）
  - Electron 内嵌 Chromium，完整支持 `File` API、`FormData`、`input[type=file]`
  - **结论**：`jobCreationApi.ts` 和 `cookiesApi.ts` 无需任何修改

### Phase 4：后端打包

- [ ] **Task 4.1**：创建 PyInstaller 构建脚本
  - 文件：`services/core/build-desktop.spec`
  - 操作：配置 PyInstaller，将 `main.py` 及所有依赖（包括 FFmpeg 二进制、whisper 模型）打包为单目录 exe
  
- [ ] **Task 4.2**：集成到 Electron Builder
  - 文件：`apps/desktop/electron-builder.yml`
  - 操作：配置 `files` 包含 `resources/backend/` 目录；配置 `extraResources` 将后端 exe 复制到应用包中

### Phase 5：打包与分发

- [ ] **Task 5.1**：配置 electron-builder 多平台打包
  - 文件：`apps/desktop/electron-builder.yml`
  - 操作：配置 Windows（NSIS installer）、macOS（dmg）、Linux（AppImage）打包目标

---

## Acceptance Criteria

### 基础功能
- [ ] **Given** 用户双击桌面快捷方式，**When** 应用启动，**Then** 10 秒内自动打开应用窗口，无需手动配置任何端口或运行命令
- [ ] **Given** 后端服务已内嵌，**When** 前端发起 API 请求，**Then** 请求成功路由到内嵌的 FastAPI 进程（健康检查通过）

### 文件上传（关键验证点）
- [ ] **Given** 用户在桌面端点击「上传视频」选择本地视频文件，**When** 点击提交，**Then** 文件成功通过 multipart 上传到后端，分析任务正常启动
- [ ] **Given** 用户在桌面端上传 Cookie 文件，**When** 上传完成，**Then** 后端状态接口返回 `hasFile: true` 且正确显示文件名

### 用户体验
- [ ] **Given** 应用正在运行，**When** 用户点击关闭按钮，**Then** Next.js 进程和 FastAPI 子进程均被正确终止，无僵尸进程

---

## Additional Context

### Dependencies

**新增前端依赖（`apps/desktop/`）：**
- `electron` ^29+
- `electron-builder` ^24+
- `typescript` (dev)
- `ts-node` (dev)

**后端打包工具：**
- `PyInstaller` （Python）
- FFmpeg 静态二进制需包含在后端打包产物中

### Testing Strategy

- **手动验证**：
  1. `cd apps/desktop && npm run dev` — 验证 Electron 窗口正常加载 Next.js
  2. 在 Electron 窗口中完成视频上传流程
  3. 在 Electron 窗口中完成 Cookie 上传流程
  4. 关闭窗口后检查任务管理器无残余进程
- **打包验证**：`npm run build` → 安装生成的 installer → 运行并重复上述手动步骤

### Notes

- **Tauri 回退路径**：若未来需要切换到 Tauri，前提是将 `apps/web` 重构为 Vite + React SPA，去除所有 Next.js SSR 依赖。代价较大，建议在项目稳定后再评估。
- **文件上传无需额外处理**：经确认，Electron 内嵌的 Chromium 完整实现了 Web File API，桌面端与 Web 端的上传代码完全共用，无差异。
- **大文件上传性能**：当视频文件较大（>500MB）时，multipart 上传涉及内存拷贝可能较慢。桌面端"路径传递"优化（绕过 HTTP 上传，后端直接读路径）可作为后续性能优化项，但需新增后端 API 端点。
