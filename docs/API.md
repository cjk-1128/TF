# TerraForge · API 接口文档

> 完整可交互文档可在服务运行时访问 **/docs**（Swagger UI）和 **/redoc**（ReDoc）。

所有接口统一返回结构：

```json
{ "code": 0, "message": "success", "data": <payload>, "trace_id": "abc123..." }
```

错误时 `code` 为非 0 值，`message` 携带可读原因，`data` 为 `null`。

---

## 1. 知识库管理 `/api/v1/knowledge`

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/kb` | 创建知识库 |
| GET | `/kb` | 列表（支持 `domain` / `keyword` 过滤） |
| GET | `/kb/{kb_id}` | 详情 |
| PUT | `/kb/{kb_id}` | 更新（名称 / 描述 / 责任人 / 标签 / 是否启用） |
| DELETE | `/kb/{kb_id}` | 级联删除知识库及文档、切片、索引 |
| GET | `/stats` | 总览统计（知识库 / 文档 / 切片 / 强制性条文数 / 三域分别数量） |

### 创建知识库

```http
POST /api/v1/knowledge/kb
Content-Type: application/json

{
  "name": "国家建设标准规范库",
  "domain": "standard",
  "description": "收录国家/行业/地方标准、规范、图集、强制性条文",
  "owner": "技术质量部-张工",
  "tags": ["结构", "地基基础"]
}
```

### 文档管理 `/documents`

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/documents/upload` | 多文件上传（form: `kb_id`, `files`, `meta`） |
| POST | `/documents/text` | 文本直接入库（会议纪要 / FAQ / 复盘） |
| GET | `/documents` | 列表（支持 `kb_id` / `status` / `governance_status` / `keyword` / 分页） |
| GET | `/documents/{doc_id}` | 详情 |
| PUT | `/documents/{doc_id}` | 更新元数据（标题 / 标准编号 / 专业 / 治理状态等） |
| DELETE | `/documents/{doc_id}` | 删除文档及索引 |
| POST | `/documents/{doc_id}/reindex` | 重建索引（解析 → 切片 → Embedding → BM25） |
| GET | `/documents/{doc_id}/chunks` | 切片列表（支持 `keyword` / 分页） |

#### 上传示例

```bash
curl -X POST http://localhost:8000/api/v1/knowledge/documents/upload \
  -F "kb_id=<kb_id>" \
  -F 'meta={"standard_code":"GB50204-2015","discipline":"structure"}' \
  -F "files=@混凝土验收规范.pdf" \
  -F "files=@施工指南.docx"
```

支持扩展名：`.pdf` `.doc` `.docx` `.xls` `.xlsx` `.md` `.txt`

#### 文本入库示例

```bash
curl -X POST http://localhost:8000/api/v1/knowledge/documents/text \
  -H "Content-Type: application/json" \
  -d '{
    "kb_id":"<kb_id>",
    "title":"3 月 12 日深基坑变形专家会议纪要",
    "content":"## 一、变形情况\n......",
    "meta":{"discipline":"geotech","owner":"项目部-王工"}
  }'
```

---

## 2. 智能问答 `/api/v1/rag`

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/chat` | 单次问答（同步） |
| POST | `/chat/stream` | 流式问答（SSE，事件格式见下） |
| POST | `/search` | 纯检索（不生成），返回混合检索 + 重排序后的片段 |
| POST | `/conversations` | 创建会话 |
| GET | `/conversations` | 会话列表（分页） |
| GET | `/conversations/{conv_id}/messages` | 消息历史（含引用） |
| DELETE | `/conversations/{conv_id}` | 删除会话 |
| POST | `/feedback` | 反馈（-1 / 1 + reason + comment） |

### 2.1 智能问答

请求：

```json
{
  "query": "C60 混凝土冬期施工养护时间要求是什么？",
  "conversation_id": null,
  "user_id": "engineer-01",
  "kb_ids": ["<kb_id>"],
  "domains": ["standard"],
  "context": {
    "project_name": "某地铁车站项目",
    "project_type": "地铁车站",
    "discipline": "structure",
    "region": "华北"
  },
  "top_k": 20,
  "stream": false
}
```

响应（节选）：

```json
{
  "code": 0, "message": "success", "trace_id": "...",
  "data": {
    "conversation_id": "...", "message_id": "...",
    "query": "C60 混凝土冬期施工养护时间要求是什么？",
    "rewritten_query": "C60混凝土冬期施工养护时间要求是什么？ 保湿 浇水 覆盖 洒水养护",
    "intent": "spec_lookup",
    "intent_label": "规范条文查询",
    "answer": "**结论与依据**\n- 抗渗混凝土、强度等级C60及以上的混凝土，养护时间不应少于14d； [1]\n- ...",
    "citations": [
      {
        "index_no": 1,
        "chunk_id": "...",
        "doc_id": "...",
        "doc_title": "混凝土结构工程施工质量验收规范（节选）",
        "standard_code": "GB50204-2015",
        "section_path": "7. 混凝土工程施工",
        "clause_no": "7.4.1",
        "page_no": 0,
        "snippet": "抗渗混凝土、强度等级C60及以上的混凝土，应在混凝土终凝前...",
        "score": 0.74,
        "domain": "standard"
      }
    ],
    "confidence": 0.82,
    "confidence_level": "high",
    "need_human_review": false,
    "review_hint": "",
    "retrieved": [...],
    "stage_traces": [
      {"stage":"stage0","name":"工程上下文管理","elapsed_ms":1,"detail":{...}},
      {"stage":"stage1","name":"智能路由","elapsed_ms":0,"detail":{...}},
      {"stage":"stage2","name":"查询改写","elapsed_ms":0,"detail":{...}},
      {"stage":"stage3","name":"混合检索","elapsed_ms":1,"detail":{"recalled":20,"top_score":0.97}},
      {"stage":"stage4","name":"重排序","elapsed_ms":11,"detail":{"input":20,"output":6}},
      {"stage":"stage5","name":"上下文构建","elapsed_ms":0,"detail":{"chunks":6,"chars":2485}},
      {"stage":"stage6","name":"智能生成与引用增强","elapsed_ms":4,"detail":{"answer_chars":236,"citations":4}},
      {"stage":"stage7","name":"知识治理闭环","elapsed_ms":0,"detail":{"confidence":0.82,"level":"high","signals":{"rel":0.6,"cnt":1,"cov":0.5},"need_review":false}}
    ],
    "latency_ms": 27,
    "token_usage": {}
  }
}
```

`stage_traces` 是端到端可观测的核心，可用于：
- 调试检索质量（召回量 / 重排序输入输出 / 上下文长度）
- 分析置信度六个信号：`rel`（相关性）、`cnt`（引用集中度）、`cov`（覆盖度）、`cite`（引用比）、`cov`（覆盖）、`penalty`（惩罚项）
- 安全审计：所有回答携带 trace_id，可在 `/logs` 中检索

### 2.2 流式问答（SSE）

`POST /chat/stream` 输出 `text/event-stream`，事件类型：

```
event: stage    data: {"stage":"stage3","name":"混合检索","elapsed_ms":1,"detail":{...}}
event: chunk    data: {"delta":"**结论与依据**\\n- 抗渗混凝土..."}
event: done     data: {"citations":[...],"confidence":0.82,"need_human_review":false,...}
event: error    data: {"message":"..."}
```

### 2.3 纯检索

```json
POST /api/v1/rag/search
{
  "query": "基坑监测报警值",
  "kb_ids": [],
  "domains": [],
  "top_k": 10,
  "use_rerank": true
}
```

返回 `RetrievedChunk[]`，每个片段包含 `vector_score` / `bm25_score` / `fusion_score` / `rerank_score` / `final_score`，便于做检索质量分析。

### 2.4 反馈

```json
POST /api/v1/rag/feedback
{
  "message_id": "msg-uuid",
  "rating": 1,
  "reason": "",
  "comment": "非常准确"
}
```

`rating` 取值 `-1`（需改进）或 `1`（有帮助）。负反馈将进入知识盲区分析。

---

## 3. 知识治理 `/api/v1/governance`

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/health-report` | 知识库体检报告（可指定 `kb_id`） |
| GET | `/tasks` | 治理事项列表（支持 `status` / `task_type` / `kb_id` / `assignee` / 分页） |
| POST | `/tasks` | 创建事项 |
| POST | `/tasks/auto-generate` | 根据体检报告自动生成治理事项 |
| PUT | `/tasks/{task_id}` | 更新事项（状态 / 责任人 / 优先级） |
| GET | `/knowledge-gaps` | 知识盲区（基于低置信度 / 无召回的提问日志） |
| GET | `/operation-report` | 运营报告（周报 / 月报：`days=7` 或 `30`） |

### 3.1 健康报告示例

```json
{
  "generated_at": "2026-08-04T12:42:00",
  "total_kb": 3, "total_docs": 10, "total_chunks": 77,
  "valid_docs": 10, "need_update_docs": 0, "deprecated_docs": 0, "failed_docs": 0,
  "issues": [
    {
      "issue_type": "expiring_soon",
      "severity": "high",
      "doc_id": "...", "doc_title": "地下工程防水技术规范（节选）",
      "kb_id": "...",
      "detail": "将于 2026-09-18 废止（剩余 44 天）",
      "suggestion": "提前准备替代版本，安排负责人跟进"
    }
  ],
  "score": 96.4,
  "suggestions": ["知识库整体健康，建议保持季度复核节奏"]
}
```

### 3.2 治理任务类型

| task_type | 含义 |
| --- | --- |
| `expire_check` | 时效核查（即将过期 / 已过期） |
| `duplicate_merge` | 重复合并 |
| `gap_fill` | 知识盲区补录 |
| `conflict_resolve` | 冲突消解 |
| `quality_fix` | 质量修复 |
| `owner_assign` | 责任人指派 |

### 3.3 运营报告

`GET /operation-report?days=7`

- `new_docs` / `new_chunks`：期间新增
- `total_queries` / `unanswered_queries` / `answer_rate`：流量与有效性
- `avg_confidence` / `avg_latency_ms`：质量与性能
- `hot_topics`：高频问题主题
- `knowledge_gaps`：待补录问题
- `suggestions`：自动生成的改进建议

---

## 4. 系统接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/health` | 健康检查（含向量库 / BM25 当前条目数） |
| GET | `/docs` | Swagger UI |
| GET | `/openapi.json` | OpenAPI Schema |

---

## 5. 错误码

| HTTP | code | 含义 |
| --- | --- | --- |
| 400 | 40000 | 请求参数错误 |
| 404 | 40400 | 资源不存在 |
| 422 | 42200 | 数据校验失败 |
| 500 | 50000 | 内部异常（详见 logs/terraforge.log） |

所有错误都包含 `trace_id`，便于在 `logs/terraforge.log` 中按 trace 串联上下文。