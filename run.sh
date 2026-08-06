#!/usr/bin/env bash
# =====================================================================
#  TerraForge 启动脚本（开发模式 / 直接运行）
#  - 自动创建虚拟环境
#  - 安装后端 + 前端依赖
#  - 启动 FastAPI（端口 8000）和可选的 Vite（端口 5173）
# =====================================================================
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN=${PYTHON_BIN:-python3.11}

echo "==> 1. 创建/激活后端虚拟环境 ..."
cd backend
if [ ! -d ".venv" ]; then
  $PYTHON_BIN -m venv .venv
fi
source .venv/bin/activate
pip install -U pip >/dev/null
pip install -r requirements.txt

echo "==> 2. 初始化数据库（SQLite，自动建表） ..."
python -m app.db.session >/dev/null 2>&1 || true

if [ "${SEED:-0}" = "1" ]; then
  echo "==> 3. 灌入演示数据 ..."
  python scripts/seed_data.py --reset
fi

cd ..

if [ "${SKIP_FRONTEND:-0}" != "1" ]; then
  echo "==> 4. 构建前端静态资源 ..."
  cd frontend
  if [ ! -d "node_modules" ]; then
    corepack enable 2>/dev/null || true
    pnpm install
  fi
  pnpm run build
  cd ..
fi

echo "==> 5. 启动 TerraForge 后端（8000） ..."
echo "    访问 http://localhost:8000/"
echo "    API 文档 http://localhost:8000/docs"
cd backend
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}