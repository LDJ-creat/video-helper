FROM node:20-slim AS base

# 启用 pnpm
ENV PNPM_HOME="/pnpm"
ENV PATH="$PNPM_HOME:$PATH"
RUN corepack enable

# 1. 依赖安装阶段
FROM base AS deps
WORKDIR /app

# 复制根目录的 lock 文件和 workspace 配置 (如果有)
# 注意：需要在 docker-compose 中设置 context 为项目根目录
COPY pnpm-lock.yaml ./
COPY apps/web/package.json ./apps/web/

# 安装依赖 only for web app
# --filter: 只安装 web 应用的依赖
RUN pnpm install --frozen-lockfile --filter web...

# 2. 构建阶段
FROM base AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY --from=deps /app/apps/web/node_modules ./apps/web/node_modules
COPY . .

# 构建 Next.js 应用
WORKDIR /app/apps/web
# 禁用 Next.js 遥测
ENV NEXT_TELEMETRY_DISABLED=1
RUN pnpm build

# 3. 运行阶段
FROM base AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

# 复制构建产物
# Next.js standalone build (需要在 next.config.js 中开启 output: 'standalone')
# 如果没有开启 standalone，则需要复制 .next/static 和 public
# 这里假设可以开启 standalone 或者回退到标准运行方式
# 为了稳健性，我们将复制整个 .next 目录（非 standalone 模式）
# 如果追求极小体积，建议在 next.config.ts 中配置 output: 'standalone'

# 复制 public 目录
COPY --from=builder /app/apps/web/public ./apps/web/public

# 复制构建文件
# 自动创建的 standalone 文件夹（如果有）会更小，但为了通用性先复制 .next
# 为了权限正确，设置 owner
COPY --from=builder --chown=nextjs:nodejs /app/apps/web/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/apps/web/.next/static ./apps/web/.next/static
# 兼容非 standalone 模式的 fallback (如果上面两条失败)
# COPY --from=builder --chown=nextjs:nodejs /app/apps/web/.next ./apps/web/.next

USER nextjs

EXPOSE 3000

ENV PORT=3000
# 必须设置 hostname 为 0.0.0.0 才能在容器外部访问
ENV HOSTNAME="0.0.0.0"

# 启动命令
# 针对 standalone模式:
CMD ["node", "apps/web/server.js"]
