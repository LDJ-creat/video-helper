# Video Analysis Assistant (Video Helper)

🌐 **语言 / Language**: [中文](README.zh.md) | English

## 📖 Introduction

**Video Analysis Assistant** is an AI-powered smart video learning assistant designed to significantly improve the efficiency of video learning and knowledge review.

This project adopts a full-stack Monorepo architecture and integrates advanced LLM analysis pipelines. Users simply provide a video link (e.g., Bilibili) or upload a local video, and the system automatically extracts core content, generating structured **Mind Maps** and **Key Summaries**.

The core highlight lies in its powerful **interactive linkage**: clicking on a mind map node precisely jumps to the corresponding video segment, and vice versa. Additionally, the built-in AI assistant supports multi-turn Q&A and can generate practice questions based on video knowledge points to help users consolidate what they have learned.

## ✨ Key Features

- **Smart Pipeline Analysis**: Automated handling of video downloading, audio transcription, content extraction, and structured analysis.
- **Dynamic Mind Map**: Generates visual knowledge structure maps supporting zooming, dragging, and node folding.
- **Bi-directional Interaction**:
    - **Mind Map -> Video**: Click a map node to jump the video stream to the corresponding timestamp.
    - **Content -> Video**: Click summary highlights to precisely locate the video explanation segment.
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

### Prerequisites

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

# Install dependencies
npm install
# Or use pnpm (Recommended)
pnpm install

# Start development server (Default port: 3000)
npm run dev
# Or
pnpm dev
```

Open your browser and visit [http://localhost:3000](http://localhost:3000) to see the application interface.

### 🐳 Docker Deployment

If you prefer to deploy using Docker, run the following commands:

1. **Build and Start Services**
    ```bash
    # Run in the project root directory
    docker-compose up -d --build
    ```

2. **Access Services**
    - Frontend: [http://localhost:3000](http://localhost:3000)
    - Backend API: [http://localhost:8000/docs](http://localhost:8000/docs)

3. **Stop Services**
    ```bash
    docker-compose down
    ```

> **Note**:
> 1. Ensure the `data` directory exists in the root for data persistence.
> 2. Ensure `services/core/.env` is correctly configured.

## 📂 Directory Structure

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

## License

This project is licensed under the MIT License – see the [LICENSE](LICENSE) file for details.

## 🤝 Contribution

Issues and Pull Requests are welcome! Before submitting code, please ensure it passes the project's Smoke Tests and adheres to code standards.

---
*Created with ❤️ by the Open Source Community*
