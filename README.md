# Video Helper (Video Analysis Assistant)

🌐 **语言 / Language**: [中文](README.zh.md) | English

## 📖 Introduction

**Video Helper** is an AI-powered smart video learning assistant designed to significantly improve the efficiency of video learning and knowledge review.

This project adopts a full-stack Monorepo architecture and integrates advanced LLM analysis pipelines. Users simply provide a video link (e.g., Bilibili, YouTube) or upload a local video, and the system automatically extracts core content, generating structured **Mind Maps** and **Key Summaries**.

The core highlight lies in its outstanding **interactive linkage**: clicking on a mind map node precisely navigates to the corresponding key content module, and clicking on a content module can jump to the corresponding video segment. Additionally, the built-in AI assistant supports multi-turn Q&A and can generate practice questions based on video knowledge points to help users consolidate what they have learned.

## ✨ Key Features

- **Smart Pipeline Analysis**: Automated handling of video downloading, audio transcription, content extraction, and structured analysis.
- **Dynamic Mind Map**: Generates visual knowledge structure maps supporting zooming, dragging, and adding/deleting/editing nodes.
- **Bi-directional Interaction**:
    - **Mind Map -> Content**: Click a map node to automatically locate the corresponding key content module.
    - **Content -> Video**: Click summary highlights to jump the video stream to the corresponding timestamp.
- **AI Q&A**: Supports multi-turn dialogue with the user based on video context, explaining difficult points in depth.
- **Quiz Canvas**: AI automatically generates questions based on video knowledge points, providing targeted practice and feedback to form a learning loop.
- **Flexible Editing**: Supports manual adjustment of mind map logic and summary content to customize personalized learning notes.


## 🏗️ Architecture

This project uses Monorepo architecture to manage frontend and backend, ensuring efficient code maintenance and scalability.

- **Frontend**: `apps/web`
    - **Framework**: [Next.js 16](https://nextjs.org/) (App Router)
    - **Language**: TypeScript, React 19
    - **Styling**: Tailwind CSS v4
    - **Visualization**: ReactFlow (Mind Map), Tiptap (Rich Text Notes)
- **Backend**: `services/core`
    - **Framework**: [FastAPI](https://fastapi.tiangolo.com/)
    - **Language**: Python 3.12+
    - **Database**: SQLite + SQLAlchemy (ORM) + Alembic (Migrations)
    - **Package Management**: [uv](https://github.com/astral-sh/uv)
    - **AI Pipeline**: Integrates whisper (transcription), LLM (analysis/summarization)

## 🚀 Getting Started

## ⬇️ Download Client

If you want to use the application directly without setting up a development environment, you can download the latest pre-built client for your OS:

| Windows | MacOS | Linux |
| :---: | :---: | :---: |
| <img src="https://simpleicons.org/icons/windows11.svg" width="36" height="36" alt="Windows" /> | <img src="https://simpleicons.org/icons/apple.svg" width="36" height="36" alt="macOS" /> | <img src="https://simpleicons.org/icons/linux.svg" width="36" height="36" alt="Linux" /> |
| [Setup.exe](https://github.com/LDJ-creat/video-helper/releases/latest) | [dmg/zip](https://github.com/LDJ-creat/video-helper/releases/latest) | [AppImage](https://github.com/LDJ-creat/video-helper/releases/latest) |

### Prerequisites (For Source Code Compilation)

Please ensure your development environment has the following tools installed:

- **Node.js**: >= 20.x
- **Python**: >= 3.12
- **uv**: Python package and project manager (Recommended install: `curl -LsSf https://astral.sh/uv/install.sh | sh` or `pip install uv`)
- **FFmpeg**: For audio/video processing (Must be configured in system PATH)

### 🛠️ Installation & Running

#### 1. Clone Project
```bash
git clone https://github.com/LDJ-creat/video-helper.git
cd video-helper
```

#### 2. Backend Startup

The backend service is located in the `services/core` directory.

```bash
# Enter backend directory
cd services/core

# First run will automatically create virtual environment and install dependencies
# Start API service (Default port: 8000)
uv run python main.py
```

> **Note**: Please ensure the `.env` file is configured in the `services/core` directory (refer to `.env.example`).

Common commands:
- Run tests: `uv run pytest -q`
- Activate environment (Manual): Windows: `.venv\Scripts\activate` | Linux/Mac: `.venv/bin/activate`

#### 3. Frontend Startup

The frontend application is located in the `apps/web` directory.

```bash
# Enter frontend directory
cd apps/web

# Install dependencies (from the root or in web)
pnpm install

# Setup environment variables using the provided example:
cp .env.example .env.local

# Start development server (Default port: 3000)
pnpm run dev
```

Open your browser and visit [http://localhost:3000](http://localhost:3000) to see the web interface.

#### 4. Desktop App (Electron) Startup & Build

If you want to run the Desktop version locally instead of the Web version, we provide convenient scripts:

**Run in Development Mode**:
```bash
# In the project root, this script automatically starts the Python backend, Next.js frontend, and Electron container
node apps/desktop/scripts/dev.js
```

**Test Desktop Packaging**:
```bash
cd apps/desktop
# Compile the TypeScript and package the app into a local folder (without building installers)
pnpm run pack
```

**Build Complete Release Installers (Windows)**:
```powershell
# In PowerShell, from the project root. This fully compiles the Web, packages the Backend via PyInstaller, and builds the Electron installer.
powershell -ExecutionPolicy Bypass -File apps\desktop\scripts\build-all.ps1
```

#### 5. Using as an AI Skill

You can also use the backend service of this project as a skill within AI editors like **Claude Code**, **Antigravity**, or **GitHub Copilot**. In this mode, you don't need to configure LLMs in the backend project itself; instead, the AI editor's LLM handles the analysis.

To use it:
1. Download the source code and start the backend service.
2. Download and install the dedicated skill from: [video-helper-skill](https://github.com/LDJ-creat/video-helper-skill).
3. Follow the usage guide in the skill repository to perform video analysis using your AI editor, and view the structured results in the web or desktop app.


## 📂 Directory Structure

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

## License

This project is licensed under the MIT License – see the [LICENSE](LICENSE) file for details.

## 🤝 Contribution

Issues and Pull Requests are welcome! Before submitting code, please ensure it passes the project's Smoke Tests and adheres to code standards.

---
*Created with ❤️ by the Open Source Community*
