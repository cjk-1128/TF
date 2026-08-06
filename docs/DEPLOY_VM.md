# TerraForge 虚拟机部署指南（192.168.88.100）

适用于在一台 Linux 虚拟机（如 `192.168.88.100`）上用 Docker Compose 一键部署。
部署后前端通过 **80 端口**（nginx 反代）访问，后端 API 在 8000 端口。

## 1. 前置条件（在目标虚拟机上）

```bash
# 确认已安装
docker --version
docker compose version        # 或 docker-compose --version
git --version
```

> 若使用 SQLite（默认零依赖模式），无需额外的 MySQL/Milvus，开箱即用。

## 2. 拉取代码

```bash
git clone <你的 GitHub 仓库地址> terraforge
cd terraforge
```

## 3. 启动服务

```bash
# 在仓库根目录执行（compose 文件位于 deploy/）
docker compose -f deploy/docker-compose.yml up -d --build
```

- 首次构建会安装 Python 依赖并编译前端，耗时几分钟。
- `terraforge` 容器：FastAPI + 本地向量库，监听 8000，数据持久化到卷 `terraforge_data`（含 `terraforge.db` / `vectorstore` / `uploads`）。
- `terraforge-nginx` 容器：80 端口反代到后端 8000。

## 4. 初始化知识库（首次必做）

容器启动后数据库为空，需灌入示例知识（规范/案例/企业文档）并重建向量索引：

```bash
docker compose -f deploy/docker-compose.yml exec terraforge \
  python backend/scripts/seed_data.py
```

完成后可校验：

```bash
curl http://localhost/health      # 应返回 vector_count > 0, bm25_count > 0
curl http://localhost/api/v1/knowledge/kb   # 应返回 3 个知识库
```

## 5. 访问

- **前端页面**：http://192.168.88.100/ （nginx 80 → 8000）
- **API 文档（Swagger）**：http://192.168.88.100/docs
- **健康检查**：http://192.168.88.100/health

## 6. 常用运维

```bash
# 查看日志
docker compose -f deploy/docker-compose.yml logs -f terraforge

# 停止 / 重启
docker compose -f deploy/docker-compose.yml down
docker compose -f deploy/docker-compose.yml up -d

# 更新代码后重建
git pull
docker compose -f deploy/docker-compose.yml up -d --build
```

## 7. 切换到真实大模型（可选）

默认是零依赖演示模式（`MockLLM` + `HashEmbedding` + 本地向量库）。
要接入真实能力，在 `deploy/.env`（或 `docker compose` 环境变量）中设置：

```dotenv
LLM_PROVIDER=openai_compatible
EMBEDDING_PROVIDER=openai
RERANK_PROVIDER=cross_encoder_api
OPENAI_API_KEY=sk-xxx
OPENAI_BASE_URL=https://your-endpoint/v1
OPENAI_MODEL=gpt-4o-mini
VECTOR_BACKEND=milvus      # 需要额外起 Milvus（compose 中已注释，按需启用）
```

## 8. 持久化说明

为兼容容器重启，已在 `docker-compose.yml` 中将以下路径统一指向持久卷 `/data`：

| 用途 | 容器内路径 |
|---|---|
| SQLite 数据库 | `/data/terraforge.db` |
| 向量/BM25 索引 | `/data/vectorstore` |
| 上传文件 | `/data/uploads` |

请勿把索引写到镜像内目录，否则容器重建后会丢失、问答变空。
