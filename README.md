# TerraForge · 土木工程智能知识平台

> 企业级 RAG 智能知识平台，聚焦土木工程行业（建设规范 / 项目案例 / 企业知识），
> 从 **Stage0 工程上下文** 到 **Stage7 知识治理闭环** 的全链路架构，所有答案均来自知识库并标注条文出处。

---

## 1. 核心特性

| 模块 | 说明 |
| --- | --- |
| **Stage0 工程上下文** | 绑定项目类型 / 专业 / 地区 / 知识库，作为后续检索的约束与解释上下文 |
| **Stage1 智能路由** | 规则 + LLM 联合识别 6 类意图（规范条文 / 质量问题 / 方案生成 / 案例检索 / 闲聊 / 未知）|
| **Stage2 查询改写** | 抽取标准编号、扩展同义词、补齐工程术语，生成子问题 |
| **Stage3-4 检索核心** | 向量（稠密）+ BM25（稀疏）并行召回，RRF + 加权融合，工程重排序（强制性条文加权 / 章节位置 / 引用编号）|
| **Stage5 上下文构建** | 去重 + 配额截断 + 强制条文置顶，保证 LLM 输入信息密度 |
| **Stage6 智能生成 + 引用增强** | 答案中强制插入 `[n]` 引用编号，无来源时拒绝回答并给出知识盲区提示 |
| **Stage7 知识治理闭环** | 健康评分、治理事项、知识盲区、运营周报 / 月报，自动发现过期 / 待更新 / 重复文档 |
| **三域知识库** | 建设规范库 / 项目案例库 / 企业知识库，统一元数据模型（标准编号 / 专业 / 有效期 / 责任人）|
| **AI 自主开发规则** | 严格基于知识库；低置信度强制提示人工复核；全链路 Trace-ID；答案引用缺一不可 |

## 2. 技术栈

**后端**：Python 3.11 · FastAPI · SQLAlchemy 2.0 · Pydantic v2 · LangGraph · LangChain · Milvus / 本地向量 · rank-bm25 · jieba

**前端**：Vue 3.5 · TypeScript 5.7 · Element Plus 2.14 · Pinia · Vue Router 4 · Vite 6 · Axios

**基础设施**：SQLite（默认） / MySQL 8 · Milvus 2.4（可选） · Redis（可选）

## 3. 目录结构

```
terraforge/
├── backend/                 # FastAPI 后端
│   ├── app/
│   │   ├── core/            # 配置、日志、异常、常量
│   │   ├── db/              # SQLAlchemy Session 与初始化
│   │   ├── models/          # ORM 模型（知识库/文档/切片/会话/治理）
│   │   ├── schemas/         # Pydantic 请求/响应模型
│   │   ├── llm/             # LLM / Embedding / Rerank 抽象与实现
│   │   ├── vectorstore/     # Milvus / 本地向量存储
│   │   ├── retrieval/       # BM25 + 混合检索
│   │   ├── ingestion/       # 解析器 + 工程切片
│   │   ├── rag/             # Stage0-Stage7 流水线
│   │   ├── services/        # 业务编排
│   │   ├── api/v1/          # 接口路由
│   │   └── main.py
│   ├── scripts/seed_data.py # 演示数据
│   ├── tests/               # 33 项单元测试
│   └── requirements.txt
├── frontend/                # Vue3 + TS 前端
│   ├── src/{api,components,views,router,styles,types}
│   ├── vite.config.ts
│   └── package.json
├── deploy/                  # 部署相关
│   ├── Dockerfile           # 多阶段：前端构建 → Python 运行时
│   ├── docker-compose.yml   # 含可选 nginx 静态代理
│   ├── nginx/default.conf
│   ├── sql/init.sql         # MySQL 初始化
│   └── .env.example
├── docs/                    # 用户手册 / 架构 / API 文档
├── run.sh                   # 一键启动脚本
└── README.md
```

## 4. 快速开始（本地）

### 4.1 零依赖方式（Mock LLM + Hash Embedding + 本地向量）

```bash
# 1. 安装后端
cd backend
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. 灌入演示数据
python scripts/seed_data.py --reset

# 3. 启动（前端构建产物若存在会自动挂载）
uvicorn app.main:app --host 0.0.0.0 --port 8000

# 4. 或使用根目录一键脚本
SEED=1 ./run.sh
```

打开：
- 前端 UI：<http://localhost:8000/>
- API 文档：<http://localhost:8000/docs>
- 健康检查：<http://localhost:8000/health>

### 4.2 启用真实 LLM / 向量库

```bash
cp deploy/.env.example .env
# 修改：
#   LLM_PROVIDER=openai
#   OPENAI_API_KEY=sk-xxx
#   OPENAI_MODEL=gpt-4o-mini
#   EMBEDDING_PROVIDER=openai
#   EMBEDDING_MODEL=text-embedding-3-small
#   VECTOR_BACKEND=milvus
#   MILVUS_HOST=127.0.0.1
#   MILVUS_PORT=19530
#   DATABASE_URL=mysql+pymysql://user:pass@127.0.0.1:3306/terraforge?charset=utf8mb4
```

修改后端入口引用 `.env`，或直接以环境变量方式启动：

```bash
export $(grep -v '^#' .env | xargs)
cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## 5. Docker 部署

```bash
cd deploy
cp .env.example .env
# 按需修改 .env（默认 VECTOR_BACKEND=local 即可零外部依赖启动）
docker compose up -d --build
# 应用暴露在 http://localhost:80（nginx 反代）或 http://localhost:8000（直连后端）
```

启动成功后执行：

```bash
docker compose exec terraforge python scripts/seed_data.py --reset
```

MySQL / Milvus / Redis 等基础设施按需启用（参考 `deploy/docker-compose.yml` 中的注释片段）。

## 6. 测试

```bash
cd backend
python -m pytest -q          # 33 项测试，约 4s
```

## 7. AI 自主开发规则（已落地）

- 所有回答必须基于知识库：LLM 上下文来自 Stage5 召回，无召回时返回"请补充相关知识"提示
- 工程建议必须标注来源：Stage6 强制插入 `[n]` 编号 → 前端引用面板可跳转原文
- 低置信度提示人工复核：Stage7 置信度 < 0.45 时标记 `need_human_review=True`，前端顶部展示警示条
- 全模块可测可观测：每条请求均携带 `X-Trace-Id` 与阶段耗时，所有 Stage 入日志

## 8. 文档索引

- [API 接口文档](docs/API.md)
- [用户手册](docs/USER_MANUAL.md)
- [技术架构说明书](docs/ARCHITECTURE.md)
- [测试报告](docs/TEST_REPORT.md)

## 9. License

MIT（仅指本仓库代码；上传的规范、案例、企业资料版权归原作者所有，使用前请确认授权）。