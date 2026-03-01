# Video Helper Desktop

Electron 桌面客户端，将 Next.js 前端与 FastAPI 后端封装为原生桌面应用。

## 开发启动

### 方式一：一键启动（推荐）

```bash
# 在项目根目录
node apps/desktop/scripts/dev.js
```

### 方式二：手动启动各服务

```bash
# 终端 1：启动后端
cd services/core
uv run python main.py

# 终端 2：启动前端
cd apps/web
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000 pnpm dev

# 终端 3：启动 Electron（等前两个就绪后）
cd apps/desktop
pnpm dev
```

## 生产打包

### 1. 打包后端（PyInstaller）

```bash
cd services/core
pip install pyinstaller
pyinstaller --onedir --name backend main.py
# 产物在 dist/backend/，复制到 apps/desktop/resources/backend/
```

### 2. 打包前端（Next.js Standalone）

```bash
cd apps/web
BUILD_STANDALONE=1 pnpm build
# 产物在 apps/web/.next/standalone/，复制到 apps/desktop/resources/web/
```

### 3. 打包 Electron

```bash
cd apps/desktop
pnpm build
# 产物在 apps/desktop/release/
```

## 目录结构

```
apps/desktop/
├── src/
│   ├── main.ts          # Electron 主进程
│   └── preload.ts       # 渲染进程桥接（contextBridge）
├── dist/                # TypeScript 编译输出（git ignored）
├── resources/
│   ├── backend/         # PyInstaller 打包的 FastAPI 后端（生产）
│   └── web/             # Next.js standalone 输出（生产）
├── release/             # electron-builder 打包产物（git ignored）
├── scripts/
│   └── dev.js           # 开发环境一键启动脚本
├── package.json
└── tsconfig.json
```

## 关键设计决策

| 决策 | 说明 |
|------|------|
| **文件上传无需改动** | Electron 内嵌 Chromium，`FormData + File API + fetch()` 完整支持 |
| **后端 URL 注入** | 主进程通过 IPC (`get-backend-url`) 告知渲染进程后端地址；同时 `NEXT_PUBLIC_API_BASE_URL` 作为备选 |
| **standalone 按需激活** | `BUILD_STANDALONE=1 pnpm build` 时才启用，不影响正常 web 开发 |
| **优雅退出** | `before-quit` 事件监听，Windows 使用 `taskkill /f /t` 确保子树进程全部终止 |
