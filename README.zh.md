# Video Analysis Assistant (Video Helper)

🌐 **语言 / Language**: 中文 | [English](README.md)

## 📖 项目简介

**Video Analysis Assistant** 是一个基于 AI 的智能视频学习助手，旨在显著提升视频学习与知识复习的效率。

本项目采用全栈 Monorepo 架构，集成了先进的 LLM 分析流水线。用户只需提供视频链接（如 Bilibili）或上传本地视频，系统即可自动提取核心内容，生成结构化的**思维导图**和**重点摘要**。

核心亮点在于其强大的**联动交互能力**：点击思维导图节点可精准跳转至视频对应片段，反之亦然。此外，内置的 AI 助手支持多轮问答，并能基于视频知识点生成练习题，帮助用户巩固所学。

## ✨ 核心功能

- **智能流水线分析**: 自动化处理视频下载、音频转录、内容提取与结构化分析。
- **动态思维导图**: 生成可视化的知识结构图，支持缩放、拖拽与节点折叠。
- **双向联动交互**:
    - **导图 -> 视频**: 点击导图节点，视频流自动跳转至对应时间戳。
    - **内容 -> 视频**: 点击摘要重点，精准定位视频讲解片段。
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

### 环境要求

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
npm install
# 或使用 pnpm (推荐)
pnpm install

# 启动开发服务器 (默认端口: 3000)
npm run dev
# 或
pnpm dev
```

打开浏览器访问 [http://localhost:3000](http://localhost:3000) 即可看到应用界面。

### 🐳 Docker 部署

如果您希望使用 Docker 快速部署，请执行以下命令：

1. **构建并启动服务**
    ```bash
    # 在项目根目录下运行
    docker-compose up -d --build
    ```

2. **访问服务**
    - 前端: [http://localhost:3000](http://localhost:3000)
    - 后端 API: [http://localhost:8000/docs](http://localhost:8000/docs)

3. **停止服务**
    ```bash
    docker-compose down
    ```

> **注意**:
> 1. 请确保根目录下存在 `data` 目录用于持久化数据。
> 2. 请确保 `services/core/.env` 文件已配置正确。

## 📂 目录结构

```graphql
video-helper/
├── apps/
│   └── web/                # Next.js Frontend App
├── services/
│   └── core/               # Python FastAPI Backend
├── scripts/                # Automation Scripts (e.g., Smoke Tests)
├── _bmad-output/           # Architecture & Planning Artifacts
├── docker-compose.yml      # (Optional) Docker setup
└── README.md               # Project Documentation
```

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！在提交代码前，请确保通过了项目的 Smoke Tests 并符合代码规范。

---
*Created with ❤️ by the Open Source Community*
