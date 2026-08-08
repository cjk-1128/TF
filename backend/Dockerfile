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
    PYTHONPATH=/app/backend:/app/backend/site-packages

WORKDIR /app/backend

# 复用宿主 venv 的 site-packages（由部署脚本从 /root/terraforge/backend/.venv/lib/python3.9/site-packages
# 预置到 backend/site-packages）。包含全部依赖（fastapi/sqlalchemy/alembic/langgraph/pymilvus 等）。
COPY backend/site-packages/ /app/backend/site-packages/

# Phase 1 新增 MySQL 驱动（小体积纯 Python 包，即便宿主 venv 缺也从此补齐；cryptography 用于 MySQL 8 caching_sha2 公钥交换）。
# 关键：必须装进 PYTHONPATH 优先的 /app/backend/site-packages 并先删除宿主拷贝的旧版 pymysql ——
# 否则宿主 venv 里过旧的 pymysql（不认 allow_public_key_retrieval 参数）会被优先导入，
# 导致 SQLAlchemy 连 MySQL 时抛 TypeError 而崩溃（init_db 即便走了 create_all 兜底也会炸）。
RUN rm -rf /app/backend/site-packages/pymysql /app/backend/site-packages/cryptography && \
    pip install --no-cache-dir --target=/app/backend/site-packages pymysql cryptography redis

# 复制应用代码（不含 data/logs/vectorstore，运行时用卷挂载）
COPY backend/app /app/backend/app
COPY backend/migrations /app/backend/migrations
COPY backend/alembic.ini /app/backend/alembic.ini

# 健康检查：slim 镜像不含 curl，用 python 探测 /health（用 127.0.0.1 避免 localhost 解析 IPv6 挂起）
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8001/health',timeout=5).status==200 else 1)"

EXPOSE 8001

# 用 `python -m uvicorn` 而非 venv bin 入口，规避 venv 路径问题（site-packages 直接挂 PYTHONPATH）
# Phase 6：--proxy-headers + --forwarded-allow-ips=* 使 uvicorn 信任 nginx 转发的
# X-Forwarded-For/Proto，从而正确识别真实客户端 IP 与 HTTPS 协议（自签名下 scheme=https）。
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001", \
     "--proxy-headers", "--forwarded-allow-ips=*"]
