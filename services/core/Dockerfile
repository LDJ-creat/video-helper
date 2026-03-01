# 使用官方 Python 3.12 slim 镜像
FROM python:3.12-slim

# 设置工作目录
WORKDIR /app

# 安装 uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# 复制项目配置文件
COPY pyproject.toml uv.lock ./

# 安装依赖
# --frozen: 确保使用 lock 文件
# --no-cache: 不使用缓存以减小镜像体积
RUN uv sync --frozen --no-cache

# 复制源代码
COPY . .

# 暴露端口
EXPOSE 8000

# 设置环境变量，确保 Python 输出不缓冲
ENV PYTHONUNBUFFERED=1

# 启动命令
# 假设 main.py 是入口文件
CMD ["uv", "run", "python", "main.py"]
