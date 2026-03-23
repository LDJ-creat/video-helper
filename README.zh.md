<h1 align="center">Video Helper</h1>

<p align="center">
  <strong>基于 AI 的智能视频分析助手，让视频学习更高效</strong>
</p>

<p align="center">
  <a href="README.md">English</a> | 中文
</p>

<p align="center">
  <a href="#features">核心功能</a> •
  <a href="#architecture">技术架构</a> •
  <a href="#getting-started">快速开始</a> •
  <a href="#contribution">贡献指南</a>
</p>

<p align="center">
  如果您喜欢这个项目，请给一个 Star ⭐ 吧！
</p>

---

## 📖 项目简介

**Video Helper** 是一款基于 AI 的**智能视频学习助手**，旨在显著提升**视频分析**、**知识复习**与**内容总结**的效率。它是您不可或缺的 **AI 学习助手**。

本项目采用全栈 Monorepo 架构，集成了先进的 **LLM 分析流水线**。用户只需提供视频链接（如 Bilibili, YouTube, TikTok）或上传本地视频，系统即可自动提取核心内容，生成结构化的**思维导图**和**重点摘要**。

核心亮点在于其出色的**联动交互能力**：点击思维导图节点可精准跳转至对应的重点内容，点击某模块的内容可以跳转至对应的视频片段。此外，内置的 AI 助手支持多轮问答，并能基于视频知识点生成练习题，形成完整的学习闭环。

### 🎥 演示视频

<div align="center">
  <video src="docs/assets/video-zh.mp4" width="100%" controls autoplay muted loop></video>
</div>

## <a id="features"></a>✨ 核心功能

- **智能流水线分析**: 自动化处理视频下载、音频转录、内容提取与结构化分析。系统支持由 LLM 智能决策并利用 FFmpeg 截取关联关键帧，与重点摘要同步展示，使用户能够更直观地理解知识点。
- **动态思维导图**: 生成可视化的知识结构图，支持缩放、拖拽与增删改。
- **双向联动交互**:
    - **导图 -> 内容**: 点击导图节点，自动定位到对应的重点内容模块。
    - **内容 -> 视频**: 点击摘要重点，视频流自动跳转至对应时间戳。
- **AI 智能问答**: 基于视频内容的上下文，支持用户与 AI 进行多轮对话，深入解析疑难点。
- **练习画布 (Quiz Canvas)**: AI 根据视频知识点自动出题，提供针对性练习与反馈。
- **灵活编辑**: 支持用户手动调整思维导图结构与摘要内容，定制个性化学习笔记。

### 🚀 为什么选择 Video Helper？

| 功能特性 | 传统视频学习 | Video Helper |
| :--- | :--- | :--- |
| **内容结构化** | 手写笔记，耗时费力 | **自动生成思维导图和重点笔记** |
| **查找知识点** | 反复拖动进度条 | **点击节点精准跳转** |
| **复习巩固** | 遗忘曲线不可控 | **AI 自动出题测试** |
| **深度理解** | 无法即时追问 | **AI 24/7 实时问答** |


## <a id="architecture"></a>🏗️ 技术架构

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

### 架构图

![项目整体架构](docs/assets/overview.png)

*图：项目整体架构。*

![核心视频分析流](docs/assets/core-flow.png)

*图：项目核心视频分析流程。*

## <a id="getting-started"></a>🚀 快速开始

根据您的使用场景，选择以下**三种方式**之一：

---

### 🖥️ 方式一：下载客户端

无需任何环境配置，直接下载对应平台的安装包，开箱即用：

| Windows | MacOS | Linux |
| :---: | :---: | :---: |
| <img src="https://cdn.jsdelivr.net/npm/simple-icons@latest/icons/windows.svg" width="36" height="36" alt="Windows" /> | <img src="https://simpleicons.org/icons/apple.svg" width="36" height="36" alt="macOS" /> | <img src="https://simpleicons.org/icons/linux.svg" width="36" height="36" alt="Linux" /> |
| [Setup.exe](https://github.com/LDJ-creat/video-helper/releases/latest) | [dmg/zip](https://github.com/LDJ-creat/video-helper/releases/latest) | [AppImage](https://github.com/LDJ-creat/video-helper/releases/latest) |

---

### 🐳 方式二：Docker 部署

适合希望快速在服务器上部署、无需本地开发环境的用户。

**1. 克隆项目**

```bash
git clone https://github.com/LDJ-creat/video-helper.git
cd video-helper
```

**2. 启动服务**

```bash
docker compose up -d
```

**3. 访问**

- Web 前端：http://localhost:3000
- 后端 API：http://localhost:8000



> 数据默认持久化到项目根目录的 `./data` 文件夹。


**端口冲突（宿主机的 8000 或 3000 已被占用时）**

如果遇到端口冲突问题，切换端口设置
```bash
# Linux / macOS
CORE_HOST_PORT=8001 WEB_HOST_PORT=3001 docker compose up -d
```

```powershell
# Windows (PowerShell)
$env:CORE_HOST_PORT="8001"; $env:WEB_HOST_PORT="3001"; docker compose up -d
```


---

### 🛠️ 方式三：源码构建（面向开发者）

适合希望二次开发、修改源码或参与项目贡献的用户。

**环境要求**

- **Node.js** >= 20.x
- **Python** >= 3.12
- **uv**（Python 包管理器，安装：`pip install uv`）
- **FFmpeg**（需配置到系统 PATH）

#### 1. 克隆项目

```bash
git clone https://github.com/LDJ-creat/video-helper.git
cd video-helper
```

#### 2. 启动后端

```bash
cd services/core

# 参考 .env.example 创建配置文件
cp .env.example .env          # Linux/macOS
Copy-Item .env.example .env   # Windows (PowerShell)

# 首次运行自动创建虚拟环境并安装依赖，启动 API 服务（端口 8000）
uv run python main.py
```

常用命令：`uv run pytest -q`（运行测试）

#### 3. 启动前端

```bash
cd apps/web
pnpm install

cp .env.example .env.local          # Linux/macOS
Copy-Item .env.example .env.local   # Windows (PowerShell)

pnpm run dev
```

打开浏览器访问 [http://localhost:3000](http://localhost:3000)。

#### 4. 桌面端（Electron）启动与打包

**开发模式**（在项目根目录运行，自动拉起后端 + 前端 + Electron）：

```bash
node apps/desktop/scripts/dev.js
```

**本地打包测试**：

```bash
cd apps/desktop
pnpm run pack
```

**构建完整安装包（仅 Windows）**：

```powershell
# 在项目根目录的 PowerShell 中运行
powershell -ExecutionPolicy Bypass -File apps\desktop\scripts\build-all.ps1
```

> 若需自行构建 Docker 镜像：
> ```bash
> docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build
> ```


## ⚡作为 AI 编辑器 Skill 使用

除了常规独立部署，您还可以将本项目的后端服务作为 Skill 集成到 **Claude Code**, **Antigravity**, **GitHub Copilot** 等 AI 编辑器中使用。采用此模式，您**无需**在后端项目中配置 LLM（大模型选项），视频的 AI 分析推理将完全依靠您的 AI 编辑器所搭载的能力完成。

使用指南：
1. 下载本项目源码或者客户端。
2. 下载并安装配套的独立 Skill 项目：[video-helper-skill](https://github.com/LDJ-creat/video-helper-skill)。
3. 参考该 skill 项目中的文档使用方式，即可在您的 AI 编辑器中对视频进行分析，最后仍可通过本项目的 Web 端或桌面端访问并查看生成的知识点汇总和思维导图等内容。



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

## <a id="contribution"></a>🤝 贡献

欢迎提交 Issue 和 Pull Request！在提交代码前，请确保通过了项目的 Smoke Tests 并符合代码规范。

## ❓ 常见问题 (FAQ)

**Q: Video Helper 支持哪些视频平台？**
A: 我们通过 `yt-dlp` 实现视频下载，支持 Bilibili, YouTube 等多个主流视频平台；同时也支持上传本地 MP4/MKV 格式视频进行分析。

**Q: 我需要付费使用大模型吗？**
A: 本项目支持集成各种 LLM API（如 OpenAI, Claude, DeepSeek）。此外，通过配套的 AI 编辑器 Skill，您甚至可以使用编辑器自带的模型能力。

**Q: 处理长视频的效果如何，会不会很慢？**
A: 对于长视频，我们采用 MapReduce 策略：先将视频内容进行拆分，然后并发地调用 LLM 进行分析，最后通过主 LLM 对信息进行对齐、聚合并产出最终结果，以最大程度提高分析效率。处理一个小时的视频，耗时大约在 15 到 20 分钟。


---
*Created with ❤️ by the Open Source Community*
