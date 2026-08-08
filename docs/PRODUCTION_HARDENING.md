# TerraForge 生产加固（Phase 6）

> 最后更新：2026-08-08 ｜ 范围：Nginx 反代 + TLS / CI 门禁 / 备份与恢复
> 适用部署：仓库根 `docker-compose.yml` + `nginx/terraforge.conf`（生产采用，非 `deploy/` 备选方案）

本阶段把"能跑起来"的演示部署提升为具备基本生产姿态的服务：

- **入口收敛**：应用容器 `web` 不再直连宿主端口，统一经 `nginx` 反代（80→HTTPS 跳转 + 443 TLS 终止）。
- **传输安全**：自签名 TLS（可一键替换为 CA 签发证书），默认 HSTS + 安全响应头 + 限速 + 请求体/超时限制。
- **流水线门禁**：GitHub Actions 增加 lint / 全量离线测试 / compose 校验 / 前端构建，保留评测回归。
- **可恢复性**：每日自动备份 MySQL `terraforge` 库 + 本地向量/数据 + Redis `tf:` 前缀隔离导出，支持到点恢复。

---

## 1. 网络与 TLS 架构

```
浏览器/客户端
   │  :80 (301 → https)   :443 (TLS 终止)
   ▼
nginx (容器 terraforge-nginx)  ← 宿主 80/443
   │  proxy_pass http://web:8001  （仅 compose 内网，宿主不再暴露 8001）
   ▼
web (容器 terraforge, FastAPI :8001)
   └─ 经 host.docker.internal 复用同机 KnowForge 的 MySQL/Milvus/Redis
```

- `web` 不再 `ports: "8002:8001"`，宿主侧只能经 nginx 的 80/443 访问。
- nginx 通过 compose 服务名 `web` 访问应用（默认网络），无需额外网络配置。
- 证书位于 `nginx/ssl/terraforge.crt` + `.key`（**已被 `.gitignore` 忽略，禁止提交**）。

### 1.1 切换入口（如从旧 8002 直连切到 nginx）

旧直连：`http://192.168.88.100:8002`。新入口：`http://192.168.88.100/`（自动跳 HTTPS）。

应用层已为反代就绪：`backend/Dockerfile` 的 uvicorn 启用 `--proxy-headers --forwarded-allow-ips=*`，
信任 nginx 转发的 `X-Forwarded-For/Proto`，使应用正确识别客户端 IP 与 HTTPS 协议。

### 1.2 生成自签名证书（部署前置步骤）

```bash
cd /root/terraforge
bash tools/gen_ssl.sh      # 生成 nginx/ssl/terraforge.{crt,key}（SAN=IP:192.168.88.100,DNS:localhost）
```

> 替换真实证书：把 CA 签发的 `fullchain.pem` / `privkey.pem` 放到 `nginx/ssl/`，
> 并改 `nginx/terraforge.conf` 的 `ssl_certificate` / `ssl_certificate_key` 指向它们即可，无需改容器。

### 1.3 启动 / 重建

```bash
cd /root/terraforge
docker compose build web      # 应用 CMD 变更（proxy-headers）需重建
docker compose up -d
docker compose ps            # terraforge 与 terraforge-nginx 均 healthy
```

### 1.4 验证

```bash
curl -k -sS https://192.168.88.100/health      # HTTPS 健康检查
curl    -sS http://192.168.88.100/health        # HTTP 应 301 跳 HTTPS
curl -k -sS https://192.168.88.100/docs         # Swagger（不受 CSP 限制）
```

### 1.5 回滚（nginx 异常时）

紧急恢复直连：在 `docker-compose.yml` 的 `web` 下取消 `ports: "8002:8001"` 注释并移除 `nginx` 的 `depends_on`，
然后 `docker compose up -d`。应用即恢复宿主 8002 直连。

---

## 2. CI 门禁（GitHub Actions）

文件：`.github/workflows/ci.yml`，触发 `push`/`PR` 到 `main` 以及手动 `workflow_dispatch`。

| 任务 | 内容 |
|---|---|
| `lint` | `ruff check`（配置见 `ruff.toml`，聚焦正确性 F/E9，忽略存量 F401） |
| `test` | 后端全量 `pytest`（conftest 强制临时 SQLite + mock + 关 Redis，离线跑） |
| `eval-regression` | 评测集检索回归（候选召回门禁） |
| `compose-validate` | `docker compose config -q` 校验编排文件 |
| `frontend-build` | `pnpm exec vite build`（与部署镜像一致，跳过 vue-tsc） |

全部离线，无需任何 API Key / 外部数据库。本地预检：

```bash
cd backend && python -m ruff check . --config ../ruff.toml
cd backend && LLM_PROVIDER=mock EMBEDDING_PROVIDER=hash RERANK_PROVIDER=cross_encoder_local \
  REDIS_ENABLED=False VECTOR_BACKEND=local QUALITY_INSPECT_ENABLED=False python -m pytest -q
```

> 说明：`ruff.toml` 仅做"正确性"门禁（未定义名/重复定义/死代码/语法），不阻塞风格现代化问题；
> 项目运行于 Python 3.9，代码中 `List`/`Optional` 等仍须从 `typing` 显式导入，勿改用 `list[str]` 内置泛型。

---

## 3. 备份与恢复

### 3.1 手动备份

```bash
cd /root/terraforge
bash tools/backup.sh
# 产出：backups/YYYYMMDD-HHMMSS/{terraforge.sql.gz, vectorstore.tar.gz, data.tar.gz, tf_redis.jsonl}
```

备份内容：

| 部件 | 方式 | 说明 |
|---|---|---|
| MySQL `terraforge` 库 | `mysqldump`（自动探测 13307 容器） | 关系型元数据主数据 |
| `docker_vector/` | `tar.gz` | BM25 索引（本地） |
| `docker_data/` | `tar.gz` | 运行时数据卷 |
| Redis `tf:` 前缀 | `tools/backup_redis.py` 经 terraforge 容器内 redis-py 导出 JSONL | **仅本平台缓存，绝不碰 KnowForge 数据** |

可调环境变量：`TF_ROOT`、`TF_MYSQL_CONTAINER`、`TF_MYSQL_ROOT_PASSWORD`（默认 `root123`）、
`TF_REDIS_HOST/PORT/DB`、`TF_BACKUP_RETENTION_DAYS`（默认 7）。

### 3.2 定时备份（systemd timer，推荐）

```bash
cp tools/terraforge-backup.service /etc/systemd/system/
cp tools/terraforge-backup.timer   /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now terraforge-backup.timer
systemctl list-timers terraforge-backup.timer
```

备选（crontab）：

```bash
(crontab -l 2>/dev/null; echo "0 2 * * * /bin/bash /root/terraforge/tools/backup.sh >> /root/terraforge/backups/cron.log 2>&1") | crontab -
```

### 3.3 恢复

```bash
# 1) MySQL（容器内向 terraforge 库导入）
docker exec -i <mysql容器> mysql -uroot -p密码 terraforge < backups/<TS>/terraforge.sql

# 2) 本地向量 / 数据
tar -xzf backups/<TS>/vectorstore.tar.gz -C /root/terraforge
tar -xzf backups/<TS>/data.tar.gz       -C /root/terraforge

# 3) Redis tf: 前缀（在 terraforge 容器内执行；默认不清空现有键，加 --flush-prefix 先清空）
docker cp backups/<TS>/tf_redis.jsonl terraforge:/tmp/tf_redis.jsonl
docker exec terraforge python /tmp/restore_redis.py \
  --redis redis://host.docker.internal:6379/1 --in /tmp/tf_redis.jsonl
```

> 注意：Redis 备份只覆盖 `tf:` 前缀键，恢复不会影响 KnowForge 的其它 Redis 数据。

---

## 5. 前端页面托管（关键）

**现象**：浏览器打开 `https://<host>/` 看到一段 JSON（`{"app":"TerraForge...","docs":"/docs",...}`），而不是 Vue 页面。

**根因**：`backend/Dockerfile` 只拷贝后端代码，**从不构建/拷贝 `frontend/dist`**。容器内无 `/app/frontend` → `app/main.py` 的 `FRONTEND_DIST` 不存在 → 走兜底分支，`GET /` 返回 JSON 信息页而非 SPA。

**修复（已落地）**：`docker-compose.yml` 的 `web` 服务挂载宿主前端产物：

```yaml
volumes:
  - ./frontend/dist:/app/frontend/dist:ro   # 检测到即由 uvicorn 托管 SPA
```

`docker compose up -d web` 生效，**无需重建镜像、VM 无需安装 Node**。

**重部署注意**：`frontend/dist/` 已被 `.gitignore` 忽略，全新环境须先在 VM 构建再启动：

```bash
cd /root/terraforge/frontend && pnpm install && pnpm build   # 产出 dist/
cd /root/terraforge && docker compose up -d web
```

> 前端 API 基址为相对路径 `/api/v1`，nginx `location /api/` 已反代到 `web:8001`，无需额外配置。
> SPA history 路由回退由 `app/main.py` 的 `spa_fallback` 处理（`/api`、`/docs`、`/health` 等保留路径除外）。
