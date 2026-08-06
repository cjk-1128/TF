# TerraForge · 技术架构说明书

> 版本 1.0.0

---

## 1. 设计目标

| 目标 | 落地方式 |
| --- | --- |
| **企业级** | 可观测（Trace-ID + Stage 埋点）、可治理（Stage7 闭环）、可扩展（分层解耦） |
| **可回答** | 答案必须来自知识库；引用条文与章节路径可追溯；禁止自由发挥 |
| **可治理** | 健康体检 / 治理事项 / 知识盲区 / 运营报告四件套 |
| **可替换** | LLM / Embedding / Rerank / 向量库全部接口化，业务代码与厂商无关 |
| **零依赖启动** | 默认 Mock LLM + Hash Embedding + 本地向量库 + SQLite，**无需任何 API Key 或外部服务** |

---

## 2. 总体架构

```
                ┌─────────────────────────────────────────────┐
                │          Vue3 + TypeScript + Element Plus    │
                │  ChatView │ SearchView │ KB │ Doc │ Governance│
                └────────────────────┬────────────────────────┘
                                     │ axios / JSON (/api/v1)
                                     ▼
   ┌──────────────────────────────────────────────────────────────┐
   │                       FastAPI 网关                            │
   │  Trace-ID 中间件 · CORS · 统一异常处理 · OpenAPI / Swagger     │
   │  SPA 静态托管与 history 回退                                  │
   └────────────────────┬─────────────────────────────────────────┘
                        │
       ┌────────────────┼──────────────────┐
       ▼                ▼                  ▼
   /knowledge         /rag             /governance
   知识库·文档       智能问答          知识治理
       │                │                  │
       ▼                ▼                  ▼
  ┌──────────┐   ┌──────────────┐   ┌──────────────┐
  │Knowledge │   │ RAGPipeline  │   │ Governance   │
  │ Service  │   │ Stage0 - 7   │   │  Service     │
  └────┬─────┘   └──────┬───────┘   └──────┬───────┘
       │                │                  │
       ▼                ▼                  ▼
  ┌────────────────────────────────────────────────┐
  │  检索 / 生成 / 索引 层                          │
  │  VectorStore(Milvus│Local) · BM25Index          │
  │  HybridRetriever(RRF+Weighted)                  │
  │  EngineeringChunker · Parsers(PDF/Word/Excel)   │
  │  LLM Factory(Mock│OpenAI-Compatible)            │
  └───────────────────┬────────────────────────────┘
                      ▼
  ┌────────────────────────────────────────────────┐
  │  数据层                                         │
  │  SQLAlchemy 2.0 → SQLite / MySQL                │
  │  Pickle → 本地向量矩阵 / BM25 索引              │
  │  可选 Milvus / Redis                            │
  └────────────────────────────────────────────────┘
```

### 目录结构

```
terraforge/
├── backend/
│   ├── app/
│   │   ├── api/v1/endpoints/   # knowledge / chat / governance 路由
│   │   ├── core/               # config / logging / constants / exceptions
│   │   ├── db/                 # session & Base
│   │   ├── models/             # SQLAlchemy ORM
│   │   ├── schemas/            # Pydantic v2 DTO
│   │   ├── ingestion/          # parsers + EngineeringChunker
│   │   ├── retrieval/          # BM25Index + HybridRetriever
│   │   ├── vectorstore/        # base / local / milvus / factory
│   │   ├── llm/                # base / local_impl / openai_client / factory
│   │   ├── rag/                # state / prompts / stages / pipeline
│   │   ├── services/           # 业务编排
│   │   └── main.py
│   ├── scripts/seed_data.py
│   └── tests/                  # 33 个用例
├── frontend/                   # Vue3 + Vite + Element Plus
├── deploy/                     # Dockerfile / compose / nginx / sql
└── docs/                       # API / 用户手册 / 架构
```

---

## 3. RAG 流水线（Stage0 → Stage7）

实现位于 `backend/app/rag/`。若环境中存在 `langgraph`，使用 StateGraph 编排；否则自动降级为顺序执行器（`_run_sequential`），两条路径共享同一批 stage 函数，行为一致。

### Stage0 · 工程上下文管理

- **输入**：user_id、会话历史、`ProjectContext`（项目名称 / 类型 / 专业 / 地区）、目标 kb_ids / domains
- **关键点**：从会话历史中**排除当前用户消息**（`current_message_id`），否则会把刚提的问题当成"历史对话"喂回模型
- **输出**：结构化上下文，供 Stage2 改写与 Stage6 生成使用

### Stage1 · 智能路由

- 规则优先：关键词 + 句式匹配 6 类意图
  `spec_lookup` / `quality_diagnosis` / `scheme_generation` / `case_retrieval` / `chitchat` / `unknown`
- 规则置信度不足时调用 LLM 兜底分类
- 意图决定：**是否检索**（chitchat 直接跳过 Stage3-5）、**领域优先级**（`INTENT_DOMAIN_ROUTING`）、**生成指令**（`INTENT_INSTRUCTIONS`）

### Stage2 · 查询改写

- 抽取标准编号（`extract_standard_code`）与条文号（`extract_clause_no`）
- 工程同义词扩展（养护 → 保湿 / 浇水 / 覆盖 / 洒水养护）
- 指代消解：结合 Stage0 历史补全"它 / 该规范"等指代
- 复杂问题拆分为 `sub_queries`
- 输出 `rewritten_query` + `sub_queries`

### Stage3 · 混合检索

并行两路召回后融合：

| 通路 | 实现 | 说明 |
| --- | --- | --- |
| 向量 | `LocalVectorStore`（numpy cosine）或 `MilvusVectorStore` | 按 kb_ids / domains 过滤 |
| 关键词 | `BM25Index`（rank-bm25，持久化 pickle） | jieba + 工程术语词典分词 |

融合策略：

```python
# RRF
score_rrf = Σ 1 / (RRF_K + rank_i)          # RRF_K = 60
# 加权
score_w   = 0.6 * vec_norm + 0.4 * bm25_norm
final     = score_rrf + score_w
```

工程加权：
- 命中查询中的标准编号：`+0.15`
- 命中子问题：`+0.10 / 命中数`
- 领域优先级匹配（由 Stage1 决定）：小幅提权

输出 `RETRIEVAL_TOP_K = 20` 条候选。

### Stage4 · 工程重排序

`RuleReranker`（默认，零依赖）多信号打分：

| 信号 | 权重方向 |
| --- | --- |
| 词覆盖率 | 正 |
| 关键短语命中 | `+0.10 / 短语` |
| 条文号命中 | `+0.20` |
| **强制性条文** | `+0.30` |
| 章节位置（越靠前越相关） | 正 |
| 治理状态 `deprecated` | 负（降权） |

可切换 `CrossEncoderAPIReranker` 调用 bge-reranker / Cohere。输出 `RERANK_TOP_N = 6`。

### Stage5 · 上下文构建

- 按 chunk_id 去重
- 强制性条文置顶
- 按字符配额截断，避免超出 LLM 窗口
- 编号化为 `[1] 来源\n正文` 的结构注入提示词

### Stage6 · 智能生成 + 引用增强

- 提示词 = `SYSTEM_BASE`（禁止无依据推测 + 必须标注 `[n]`）+ `INTENT_INSTRUCTIONS[intent]` + `USER_TEMPLATE`（历史 → 上下文 → 当前问题）
- 生成后解析答案中出现的 `[n]`，与 Stage5 编号对齐，产出 `citations[]`
- **MockLLM**：无 API Key 时用抽取式生成——按查询相关度挑选原文句子，优先含数字 / 单位的句子，逐条附 `[n]`。仍然满足"基于原文 + 带引用"的硬性要求，因此离线也能演示完整闭环

### Stage7 · 知识治理闭环

置信度六信号：

| 信号 | 含义 | 权重 |
| --- | --- | --- |
| `rel` | 最高相关性得分 | 0.35 |
| `cnt` | 引用集中度（最高分 / 总分） | 0.25 |
| `cite` | 答案中引用编号占比 | 0.15 |
| `cov` | 引用覆盖关键事实比例 | 0.15 |
| `cit1` | 是否至少 1 条有效引用 | 0.10 |
| `penalty` | 废止文档 / 解析失败惩罚 | −0.20 |

```python
confidence = clamp(0.35*rel + 0.25*cnt + 0.15*cite + 0.15*cov + 0.10*cit1 - 0.20*penalty, 0, 1)
```

分级与动作：

| 区间 | 级别 | 动作 |
| --- | --- | --- |
| ≥ 0.75 | `high` | 正常返回 |
| 0.45 ~ 0.75 | `medium` | 正常返回，前端标注中等置信 |
| < 0.45 | `low` | **强制 `need_human_review=True`**，前端展示复核告警 |

此外，涉及安全 / 强制性条文的意图会**强制触发人工复核标记**，即便置信度较高。

每次问答写入 `QueryLog`，成为知识盲区与运营报告的数据源。

---

## 4. 数据模型

### 4.1 实体关系

```
KnowledgeBase 1 ── N Document 1 ── N Chunk
Conversation  1 ── N Message  1 ── N Citation
GovernanceTask / FeedbackRecord / QueryLog （独立表）
```

### 4.2 关键字段

| 表 | 字段 | 作用 |
| --- | --- | --- |
| `documents` | `standard_code` | Stage3 加权 |
| | `governance_status` | Stage4 降权 + Stage7 体检 |
| | `effective_date` / `expire_date` | 时效核查 |
| | `status` / `error_msg` | 入库流水状态 |
| `chunks` | `section_path` | 章节路径继承，引用展示 |
| | `clause_no` | 条文号，Stage4 精确加权 |
| | `is_mandatory` | 强制性条文，重排 `+0.30` |
| | `vector_id` | 与向量库对齐，删除时同步清理 |
| `messages` | `confidence` / `need_human_review` | 治理与审计 |
| `query_logs` | `confidence` / `retrieved_count` | 知识盲区聚合 |

### 4.3 索引

- **向量**：本地 `numpy.float32` 矩阵 + pickle 持久化；设置 `VECTOR_BACKEND=milvus` 后自动切换，失败回退本地
- **BM25**：`rank_bm25.BM25Okapi` + pickle
- **关系库**：SQLite（默认，开启 WAL + foreign_keys）/ MySQL 8.0（连接池）
- 双索引写入在同一个 ingest 事务内完成，删除文档时同步 purge，避免索引悬挂

---

## 5. 检索核心实现

### 5.1 本地向量检索

```python
def search(query_vec, top_k=20, kb_filter=None, domain_filter=None):
    q = query_vec / np.linalg.norm(query_vec)
    scores = self.matrix @ q               # 已归一化，点积即 cosine
    if kb_filter or domain_filter:
        scores = np.where(mask, scores, -1.0)
    idx = np.argpartition(-scores, top_k)[:top_k]
    return [(self.ids[i], float(scores[i])) for i in idx[np.argsort(-scores[idx])]]
```

### 5.2 BM25 的小语料陷阱

小语料下 BM25 的 IDF 可能整体为负，导致全部得分 ≤ 0 被过滤掉，出现"明明有匹配却零召回"。处理方式：

```python
if max(scores) <= 0:
    scores = [token_overlap_ratio(q_tokens, doc_tokens) for doc_tokens in corpus]
else:
    scores = [s + 0.01 * overlap for s, overlap in zip(scores, overlaps)]
```

### 5.3 标准编号正则

中文字符属于 `\w`，`\b` 边界在"按JGJ130-2011"这类文本上会失效。改用显式前后向断言：

```python
STANDARD_CODE_RE = re.compile(
    r'(?<![A-Za-z0-9])((?:GB|GBT|JGJ|JTG|CJJ|DB|TB|SL|CECS)[/T]*\s?\d{2,5}(?:[-—]\d{4})?)(?![0-9])'
)
```

---

## 6. 工程感知切片

`EngineeringChunker` 与通用切分器的区别：

| 能力 | 说明 |
| --- | --- |
| 章节路径继承 | 解析出的标题层级构成 `section_path`，子块自动继承父级路径 |
| 表格块保留 | 表格作为整体不被拆散，避免行列错位 |
| 条文号抽取 | 识别 `7.4.1` 这类条文编号写入 `clause_no` |
| 强制性条文识别 | 命中"必须 / 严禁 / 应 / 不应 / 不得"等强制语气写入 `is_mandatory` |
| 句子边界切分 | 按中文句号 / 分号切分，配置 overlap 保持语义连续 |

这些元数据直接决定了 Stage4 的重排质量和引用展示的可读性。

---

## 7. 抽象层与可替换性

### 7.1 LLM

```python
class BaseLLM(Protocol):
    async def chat(self, messages: list[ChatMessage], *, temperature: float = 0.0) -> LLMResult: ...
```

| Provider | 适用场景 | 需要 Key |
| --- | --- | --- |
| `MockLLM` | 离线演示 / 单测 / CI | 否 |
| `OpenAICompatibleLLM` | OpenAI / DeepSeek / Moonshot / 通义（兼容模式）/ vLLM 自托管 | 是 |

### 7.2 Embedding

| Provider | 维度 | 说明 |
| --- | --- | --- |
| `HashEmbedding` | 384 | md5 + bigram + jieba，确定性、零依赖 |
| `OpenAICompatibleEmbedding` | 依模型 | `text-embedding-3-small`、`bge-m3` 等 |

> 切换 Embedding 后必须对全部文档执行重建索引，否则新旧向量空间不一致。

### 7.3 Rerank

| Provider | 说明 |
| --- | --- |
| `RuleReranker` | 规则加权，默认 |
| `CrossEncoderAPIReranker` | bge-reranker / Cohere Rerank API |

### 7.4 向量库

| Backend | 说明 |
| --- | --- |
| `local` | numpy + pickle，适合 10 万级以内 |
| `milvus` | 生产规模；连接失败自动回退 local，保证可用性 |

工厂函数（`llm/factory.py`、`vectorstore/factory.py`）用 `lru_cache` 缓存实例，按 `settings` 切换，业务层完全无感。

---

## 8. 治理算法

### 8.1 健康评分

```python
score = 100.0
for issue in issues:
    score -= SEVERITY_WEIGHT[issue.severity]      # high=5, medium=3, low=1
score -= failed_docs * 5
return max(round(score, 1), 0.0)
```

### 8.2 自动生成治理事项

以健康报告为输入，按问题类型映射到事项类型，同一文档同类问题去重，避免重复建单：

```
expired / expiring_soon → expire_check
no_owner                → owner_assign
duplicate               → duplicate_merge
parse_failed / no_chunk → quality_fix
```

### 8.3 知识盲区

```sql
SELECT query, COUNT(*) AS cnt, AVG(confidence) AS avg_conf
FROM query_logs
WHERE created_at >= :since AND confidence < :low_threshold
GROUP BY query
ORDER BY cnt DESC, avg_conf ASC
LIMIT :limit
```

### 8.4 运营报告

区间聚合 `QueryLog` / `Document` / `Chunk` / `GovernanceTask`：

```
answer_rate = 1 - unanswered_queries / total_queries
```

`suggestions` 根据阈值自动生成（回答率 < 0.8 提示补录；平均置信度 < 0.6 提示优化切片或换 Embedding；待办事项积压提示分派责任人）。

---

## 9. 可观测性与异常处理

- **Trace ID**：中间件为每个请求生成 12 位 ID，写入 `X-Trace-Id` 响应头、日志 `TraceFilter`、`QueryLog.trace_id`、`ApiResponse.trace_id`——四处一致，便于串联
- **阶段耗时**：Stage0-7 全部以 `StageTrace` 返回前端，前端"执行链路"面板直接渲染
- **性能头**：`X-Process-Time-Ms`
- **统一异常**：`TerraForgeError` 体系（`NotFoundError` / `ValidationError` / `DocumentParseError` / `EmbeddingError` / `VectorStoreError` / `LLMError` / `RetrievalError`）经 `register_exception_handlers` 统一转换为 `ApiResponse`，不泄漏堆栈
- **日志**：`logs/terraforge.log`，含 trace_id 字段

---

## 10. 性能与容量

当前默认配置（本地 Hash Embedding + numpy 向量库 + SQLite）实测：

| 指标 | 实测值 |
| --- | --- |
| 端到端问答延迟 | 20 ~ 40 ms（77 切片规模） |
| Stage4 重排耗时 | ~11 ms（20 → 6） |
| 索引构建 | 10 文档 / 77 切片 < 2 s |

容量建议：

| 规模 | 推荐配置 |
| --- | --- |
| < 1 万切片 | SQLite + local 向量库 |
| 1 万 ~ 10 万 | MySQL + local 向量库（内存约 `切片数 × 维度 × 4B`） |
| > 10 万 | MySQL + Milvus + 独立 Embedding 服务 |

---

## 11. 安全与合规

- 答案强约束在知识库范围内，提示词层面禁止推断性扩展
- 涉及安全 / 强制性条文的场景强制标记人工复核
- 引用可追溯到条文号与章节路径，满足工程责任可追溯要求
- 上传文件按知识库隔离存储，删除文档时同步清理文件、切片与双索引
- 所有写操作在 SQLAlchemy 事务内完成，异常自动回滚

---

## 12. 测试

`backend/tests/` 共 33 个用例，全部通过：

| 文件 | 覆盖点 |
| --- | --- |
| `test_ingestion.py` | 解析器、切片器、标准编号/条文号抽取、强制性条文识别 |
| `test_retrieval.py` | 向量检索、BM25（含小语料回退）、RRF 融合、重排序 |
| `test_rag_pipeline.py` | Stage0-7 全链路、意图路由、置信度分级、无召回兜底 |
| `test_api.py` | 知识库 / 文档 / 问答 / 治理接口的 happy path 与异常路径 |

```bash
cd backend && python -m pytest -q
```

---

## 13. 演进方向

1. 扫描件 OCR（PaddleOCR / Tesseract）接入解析链路
2. 图纸 / BIM 构件级检索（多模态 Embedding）
3. 条文冲突自动检测（同主题不同标准的差异比对）
4. 用户级权限与知识库 ACL
5. 反馈驱动的重排序模型微调（利用 `FeedbackRecord` 作为训练信号）
6. 运营报告定时推送到企业微信 / 钉钉
