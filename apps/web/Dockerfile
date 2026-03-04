FROM node:20-slim AS base

# 启用 pnpm
ENV PNPM_HOME="/pnpm"
ENV PATH="$PNPM_HOME:$PATH"
RUN corepack enable

# 1) 依赖安装阶段（仅 web + workspace 解析所需 manifests）
FROM base AS deps
WORKDIR /app

COPY pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web/package.json ./apps/web/package.json
# pnpm -r / workspace 需要能解析到其它 workspace 包的 manifest（本仓库目前只有 desktop/web）
COPY apps/desktop/package.json ./apps/desktop/package.json

RUN pnpm -r install --frozen-lockfile --filter web...

# 2) 构建阶段
FROM base AS builder
WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY --from=deps /app/apps/web/node_modules ./apps/web/node_modules
COPY . .

# 构建 Next.js 应用（standalone）
ENV NEXT_TELEMETRY_DISABLED=1 \
    BUILD_STANDALONE=1

WORKDIR /app/apps/web
RUN pnpm build

# 3) 运行阶段
FROM node:20-slim AS runner
WORKDIR /app

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME="0.0.0.0"

RUN addgroup --system --gid 1001 nodejs \
    && adduser --system --uid 1001 nextjs

# Next standalone 产物结构会包含 apps/web/server.js
COPY --from=builder --chown=nextjs:nodejs /app/apps/web/public ./apps/web/public
COPY --from=builder --chown=nextjs:nodejs /app/apps/web/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/apps/web/.next/static ./apps/web/.next/static

USER nextjs

EXPOSE 3000

CMD ["node", "apps/web/server.js"]
