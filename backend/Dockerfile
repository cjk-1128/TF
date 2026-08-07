# TerraForge 后端容器镜像（Phase 0）
#
# 关键决策：基础镜像用 python:3.9-slim，与 VM 宿主运行环境（Python 3.9.19，
# systemd 服务使用的 venv）完全一致；并直接复制宿主已装好的 site-packages 进镜像，
# 彻底绕开从 PyPI 慢速下载（实测 langgraph/pymilvus 等在该 VM 上 pip 极慢）。
# 零网络安装依赖，构建从数十分钟降到分钟级。
#
# 目录层级保持 backend/app/core/config.py → parents[2]=/app/backend=BASE_DIR，PROJECT_ROOT=/app

FROM python:3.9-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/backend/site-packages

WORKDIR /app/backend

# 复用宿主 venv 的 site-packages（由部署脚本从 /root/terraforge/backend/.venv/lib/python3.9/site-packages
# 预置到 backend/site-packages）。包含全部依赖（fastapi/sqlalchemy/alembic/langgraph/pymilvus 等）。
COPY backend/site-packages/ /app/backend/site-packages/

# 复制应用代码（不含 data/logs/vectorstore，运行时用卷挂载）
COPY backend/app /app/backend/app
COPY backend/migrations /app/backend/migrations
COPY backend/alembic.ini /app/backend/alembic.ini

# 健康检查：slim 镜像不含 curl，用 python 探测 /health
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8001/health',timeout=3).status==200 else 1)"

EXPOSE 8001

# 用 `python -m uvicorn` 而非 venv bin 入口，规避 venv 路径问题（site-packages 直接挂 PYTHONPATH）
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
