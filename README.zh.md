# Video Helper（Video Analysis Assistant）

🌐 **语言 / Language**: 中文 | [English](README.md)

## 📖 项目简介

**Video Helper** 是一个基于 AI 的智能视频学习助手，旨在显著提升视频学习与知识复习的效率。

本项目采用全栈 Monorepo 架构，集成了先进的 LLM 分析流水线。用户只需提供视频链接（如 Bilibili,Youtube）或上传本地视频，系统即可自动提取核心内容，生成结构化的**思维导图**和**重点摘要**。

核心亮点在于其出色的**联动交互能力**：点击思维导图节点可精准跳转至对应的重点内容，点击某模块的内容可以跳转至对应的视频片段。此外，内置的 AI 助手支持多轮问答，并能基于视频知识点生成练习题，帮助用户巩固所学。

## ✨ 核心功能

- **智能流水线分析**: 自动化处理视频下载、音频转录、内容提取与结构化分析。系统支持由 LLM 智能决策并利用 FFmpeg 截取关联关键帧，与重点摘要同步展示，使用户能够更直观地理解知识点。
- **动态思维导图**: 生成可视化的知识结构图，支持缩放、拖拽与增删改。
- **双向联动交互**:
    - **导图 -> 内容**: 点击导图节点，自动定位到对应的重点内容模块。
    - **内容 -> 视频**: 点击摘要重点，视频流自动跳转至对应时间戳。
- **AI 智能问答**: 基于视频内容的上下文，支持用户与 AI 进行多轮对话，深入解析疑难点。
- **练习画布 (Quiz Canvas)**: AI 根据视频知识点自动出题，提供针对性练习与反馈，形成学习闭环。
- **灵活编辑**: 支持用户手动调整思维导图结构与摘要内容，定制个性化学习笔记。


## 🏗️ 技术架构

本项目采用 Monorepo 架构管理，前后端分离，确保代码的高效维护与扩展。

- **前端 (Frontend)**: `apps/web`
    - **框架**: [Next.js 16](https://nextjs.org/) (App Router)
    - **语言**: TypeScript, React 19
    - **样式**: Tailwind CSS v4
    - **可视化**: ReactFlow (思维导图), Tiptap (富文本笔记)
- **后端 (Backend)**: `services/core`
    - **框架**: [FastAPI](https://fastapi.tiangolo.com/)
    - **语言**: Python 3.12+
    - **数据库**: SQLite + SQLAlchemy (ORM) + Alembic (迁移)
    - **包管理**: [uv](https://github.com/astral-sh/uv)
    - **AI 流水线**: 集成 whisper (转录)、LLM (分析/总结)

## 🚀 快速开始

## ⬇️ 下载客户端 (Download Client)

如果您不想配置本地开发环境，可以直接下载打包好的最新版本客户端开箱即用：

| Windows | MacOS | Linux |
| :---: | :---: | :---: |
| <img src="https://simpleicons.org/icons/windows11.svg" width="36" height="36" alt="Windows" /> | <img src="https://simpleicons.org/icons/apple.svg" width="36" height="36" alt="macOS" /> | <img src="https://simpleicons.org/icons/linux.svg" width="36" height="36" alt="Linux" /> |
| [Setup.exe](https://github.com/LDJ-creat/video-helper/releases/latest) | [dmg/zip](https://github.com/LDJ-creat/video-helper/releases/latest) | [AppImage](https://github.com/LDJ-creat/video-helper/releases/latest) |

### 环境要求 (针对源码运行)

在此之前，请确保您的开发环境已安装以下工具：

- **Node.js**: >= 20.x
- **Python**: >= 3.12
- **uv**: Python 包与项目管理器 (推荐安装: `curl -LsSf https://astral.sh/uv/install.sh | sh` 或 `pip install uv`)
- **FFmpeg**: 用于音视频处理 (需配置到系统 PATH 环境变量中)

### 🛠️ 安装与运行

#### 1. 克隆项目
```bash
git clone https://github.com/LDJ-creat/video-helper.git
cd video-helper
```

#### 2. 后端启动

后端服务位于 `services/core` 目录。

```bash
# 进入后端目录
cd services/core

# 首次运行将自动创建虚拟环境并安装依赖
# 启动 API 服务 (默认端口: 8000)
uv run python main.py
```

> **注意**: 请确保在 `services/core` 目录下配置好 `.env` 文件（参考 `.env.example`）。

常见命令：
- 运行测试: `uv run pytest -q`
- 激活环境(手动): Windows: `.venv\Scripts\activate` | Linux/Mac: `.venv/bin/activate`

#### 3. 前端启动

前端应用位于 `apps/web` 目录。

```bash
# 进入前端目录
cd apps/web

# 安装依赖
pnpm install

# 根据模板创建本地环境变量文件
cp .env.example .env.local

# 启动开发服务器 (默认端口: 3000)
pnpm run dev
```

打开浏览器访问 [http://localhost:3000](http://localhost:3000) 即可看到 Web 端应用界面。

#### 4. 桌面端 (Electron) 启动与打包

除了 Web 版之外，我们还可以直接编译运行具有原生能力的桌面端：

**开发模式启动**:
```bash
# 在项目根目录下运行，此脚本会自动串联并拉起 Python 后端、Next.js 前端和 Electron 容器
node apps/desktop/scripts/dev.js
```

**测试桌面端打包**:
```bash
cd apps/desktop
# 编译 TypeScript 并在本地目录生成解包文件 (不生成安装包)
pnpm run pack
```

**完整客户端离线安装包构建 (Windows)**:
```powershell
# 在 PowerShell 中于项目根目录运行。此脚本将完成 Web 编译、后端 PyInstaller 打包、Electron NSIS 安装包的完整流程。
powershell -ExecutionPolicy Bypass -File apps\desktop\scripts\build-all.ps1
```

#### 5. 作为 AI 编辑器 Skill 使用

除了常规独立部署，您还可以将本项目的后端服务作为 Skill 集成到 **Claude Code**, **Antigravity**, **GitHub Copilot** 等 AI 编辑器中使用。采用此模式，您**无需**在后端项目中配置 LLM（大模型选项），视频的 AI 分析推理将完全依靠您的 AI 编辑器所搭载的能力完成。

使用指南：
1. 下载本项目源码并启动后端服务（`services/core`）。
2. 下载并安装配套的独立 Skill 项目：[video-helper-skill](https://github.com/LDJ-creat/video-helper-skill)。
3. 参考该 skill 项目中的文档使用方式，即可在您的 AI 编辑器中对视频进行分析，最后仍可通过本项目的 Web 端或桌面端访问并查看生成的精美知识点和思维导图。



## 📂 目录结构

```graphql
video-helper/
├── apps/
│   ├── web/                # Next.js Frontend App
│   └── desktop/            # Electron Desktop App
├── services/
│   └── core/               # Python FastAPI Backend
├── docs/                   # Documentation
├── scripts/                # Automation Scripts (e.g., Smoke Tests)
├── _bmad-output/           # Architecture & Planning Artifacts
├── docker-compose.yml      # (Optional) Docker setup
└── README.md               # Project Documentation
```

## 许可证

本项目使用 MIT 许可证，详情请参阅 [LICENSE](LICENSE) 文件。

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！在提交代码前，请确保通过了项目的 Smoke Tests 并符合代码规范。

---
*Created with ❤️ by the Open Source Community*
