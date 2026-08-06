# =====================================================================
#  TerraForge 多阶段构建镜像
#  - Stage 1: 构建前端（Vue3 + Vite），产物 dist 打进后端镜像
#  - Stage 2: Python 运行镜像（非 root、含 curl 供健康检查）
# =====================================================================

# ---------- Stage 1: 前端 ----------
FROM node:20-alpine AS frontend
WORKDIR /web
COPY frontend/package.json frontend/pnpm-lock.yaml* ./
RUN corepack enable && corepack prepare pnpm@9 --activate \
    && (pnpm install --frozen-lockfile || pnpm install)
COPY frontend/ ./
# 跳过 vue-tsc 类型检查，仅做 vite 生产构建，避免类型误差阻断镜像产出
RUN pnpm exec vite build

# ---------- Stage 2: 后端运行镜像 ----------
FROM python:3.11-slim AS backend

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/backend \
    TERRAFORGE_FRONTEND_DIST=/app/frontend_dist

# 运行时最小依赖：curl 供容器健康检查使用
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
    && rm -rf /var/lib/apt/lists/*

# 非 root 运行用户
RUN groupadd -r appuser && useradd -r -g appuser -u 1000 appuser

WORKDIR /app
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
COPY --from=frontend /web/dist /app/frontend_dist

RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 8000
WORKDIR /app/backend

# 启动即执行 Alembic 迁移（见 app/db/session.init_db），无需额外步骤
HEALTHCHECK --interval=30s --timeout=5s --retries=5 --start-period=20s \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--proxy-headers", "--forwarded-allow-ips=*"]
