# TerraForge 后端镜像
# 多阶段构建：先编译前端，再把 dist 打进后端镜像
FROM node:20-alpine AS frontend
WORKDIR /web
COPY frontend/package.json frontend/pnpm-lock.yaml* ./
RUN corepack enable && corepack prepare pnpm@9 --activate \
    && (pnpm install --frozen-lockfile || pnpm install)
COPY frontend/ ./
RUN pnpm run build

FROM python:3.11-slim AS backend

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    TERRAFORGE_FRONTEND_DIST=/app/frontend_dist

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential default-jre-headless libgl1 libglib2.0-0 curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt ./
RUN pip install -r requirements.txt

COPY backend/ ./backend/
COPY --from=frontend /web/dist /app/frontend_dist

ENV PYTHONPATH=/app/backend

EXPOSE 8000
WORKDIR /app/backend
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]