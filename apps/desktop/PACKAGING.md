# Video Helper Desktop — 打包与发布指南

## ⚡ 一键打包（推荐）

```powershell
# 从项目根目录运行（需要 PowerShell）
powershell -ExecutionPolicy Bypass -File apps\desktop\scripts\build-all.ps1
```

打包完成后，安装包位于：`apps/desktop/release/Video Helper Setup *.exe`

---

## 📋 前置条件

| 工具 | 版本要求 | 检查命令 |
|------|---------|---------|
| Node.js | ≥ 18 | `node -v` |
| pnpm | ≥ 8 | `pnpm -v` |
| Python | ≥ 3.12 | `python --version` |
| uv | 最新 | `uv --version` |

> [!IMPORTANT]
> **仅支持 Windows x64 构建。** macOS / Linux 包需要在对应平台的 CI 环境中构建。

---

## 📦 分步骤手动打包

如果一键脚本失败，可逐步执行：

### Step 1：编译 Electron 主进程（TypeScript）

```powershell
cd apps\desktop
pnpm compile
```

产物：`apps/desktop/dist/main.js`、`apps/desktop/dist/preload.js`

---

### Step 2：打包 Next.js 前端（Standalone 模式）

```powershell
cd apps\web
$env:BUILD_STANDALONE="1"
pnpm build
```

产物（三个目录，缺一不可）：
- `apps/web/.next/standalone/` — 独立 Node.js 服务器
- `apps/web/.next/static/`    — 静态资源
- `apps/web/public/`          — 公共文件

> [!NOTE]
> `BUILD_STANDALONE=1` 环境变量会触发 `next.config.ts` 中的 `output: 'standalone'`，
> 不设置时正常开发流程不受影响。

---

### Step 3：打包 FastAPI 后端（PyInstaller）

```powershell
cd services\core
uv run python scripts\build_backend.py
```

脚本会自动：
1. 安装 PyInstaller（进入 uv 虚拟环境）
2. 以 `backend.spec` 为配置运行 PyInstaller
3. 将产物复制到 `apps/desktop/resources/backend/`

产物：`apps/desktop/resources/backend/backend.exe`（及所有依赖文件）

**测试后端 exe 是否正常：**

```powershell
apps\desktop\resources\backend\backend.exe
# 应输出:
# INFO:     Started server process [...]
# INFO:     Uvicorn running on http://0.0.0.0:8000
```

> [!TIP]
> **首次打包可能遇到缺失模块**（Python 的隐式导入问题）。如果运行 exe 时看到 `ModuleNotFoundError`，
> 在 `services/core/backend.spec` 的 `hiddenimports` 列表中添加对应模块名，然后重新打包。

---

### Step 4：生成 Windows 安装包（electron-builder）

```powershell
cd apps\desktop
pnpm build
```

产物：`apps/desktop/release/Video Helper Setup <version>.exe`（NSIS 安装包）

---

## 🖥️ 用户安装与使用

### 安装步骤

1. 双击 `Video Helper Setup <version>.exe`
2. 按照安装向导完成安装（可自定义安装目录）
3. 安装完成后桌面会出现 `Video Helper` 快捷方式

### 首次使用配置

安装后需在 `resources/backend/` 目录下创建 `.env` 文件，配置 LLM 服务密钥等必要参数：

```env
# LLM 提供商配置（至少配置一个）
OPENAI_API_KEY=sk-...
# ANTHROPIC_API_KEY=...
# GOOGLE_API_KEY=...

# （可选）自定义数据存储目录，默认在用户主目录下
# DATA_DIR=C:\Users\YourName\VideoHelperData
```

> [!NOTE]
> 安装后的 `.env` 文件路径：`<安装目录>\resources\backend\.env`

### 数据目录

应用数据（数据库、下载缓存、Cookie 文件）默认存储在：
```
C:\Users\<用户名>\video-helper\
```

---

## 🔧 打包问题排查

### PyInstaller：运行时缺失模块

```
ModuleNotFoundError: No module named 'xxx'
```

在 `services/core/backend.spec` 的 `hiddenimports` 列表中添加 `'xxx'`，重新执行 Step 3。

### electron-builder：找不到 Next.js 产物

```
Cannot find source directory "../web/.next/standalone"
```

确保已按 Step 2 完成前端构建，且 `BUILD_STANDALONE=1` 已设置。

### Electron 启动后白屏

1. 打开开发者工具查看控制台错误（开发模式下按 `Ctrl+Shift+I`）
2. 检查后端健康端点：访问 `http://localhost:8000/api/v1/health`
3. 查看后端日志：`%APPDATA%\Video Helper\logs\backend.log`
