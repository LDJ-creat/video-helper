# 使用官方 Python 3.12 slim 镜像
FROM python:3.12-slim

WORKDIR /app

# 基础运行环境配置
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUTF8=1 \
    # IMPORTANT: 代码里的默认 DATA_DIR 会在容器路径结构下解析到 /data。
    # 显式设置为 /app/data 以配合 docker-compose 的卷挂载。
    DATA_DIR=/app/data

# 系统依赖：
# - ffmpeg: 音频提取/关键帧
# - yt-dlp: URL 下载
# - nodejs: 可选，用于 yt-dlp --js-runtimes (某些站点更稳)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    ffmpeg \
    imagemagick \
    libgomp1 \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

# 下载 yt-dlp（Linux，多架构）
RUN set -e; \
    arch="$(uname -m)"; \
    case "$arch" in \
    x86_64|amd64) asset="yt-dlp_linux" ;; \
    aarch64|arm64) asset="yt-dlp_linux_aarch64" ;; \
    armv7l|armv7) asset="yt-dlp_linux_armv7l" ;; \
    *) echo "Unsupported arch for yt-dlp: $arch" >&2; exit 1 ;; \
    esac; \
    url="https://github.com/yt-dlp/yt-dlp/releases/latest/download/${asset}"; \
    echo "Downloading yt-dlp: arch=$arch asset=$asset"; \
    curl -fsSL -o /usr/local/bin/yt-dlp "$url"; \
    chmod +x /usr/local/bin/yt-dlp; \
    yt-dlp --version

# 安装 uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# 先复制依赖清单以便缓存依赖层
COPY pyproject.toml uv.lock ./

# 安装 Python 依赖
RUN uv sync --frozen --no-cache

# 复制源代码
COPY . .

# 非 root 运行（更安全）
RUN addgroup --system --gid 10001 app \
    && adduser --system --uid 10001 --ingroup app --home /home/app app \
    && mkdir -p /app/data /home/app /tmp/uv-cache \
    && chown -R app:app /app /home/app /tmp/uv-cache

# uv 运行时会写缓存；system user 的默认 HOME 可能是 /nonexistent，导致权限错误。
ENV HOME=/home/app \
    UV_CACHE_DIR=/tmp/uv-cache

USER app

EXPOSE 8000

CMD ["uv", "run", "python", "main.py"]
