# TerraForge 测试报告

> 土木工程智能知识平台 · 后端自动化测试报告
> 版本：v1.0.0 ｜ 生成日期：2026-08-04 ｜ 测试框架：pytest 9.x（asyncio 模式）

---

## 1. 概述

本报告记录 TerraForge 平台后端的自动化测试结果。测试目标是验证 **Stage0–Stage7 全链路 RAG 流程**、**知识库管理**、**检索与重排**、**文档切分入库**以及 **知识治理闭环** 的正确性，并锁定三类在联调（E2E）阶段发现的线上缺陷，确保"无证据不作答"等核心铁律不被破坏。

测试结果：**全部 39 个用例通过（39 passed, 0 failed）**，覆盖 5 个测试模块。

---

## 2. 测试环境

| 项目 | 配置 |
|---|---|
| Python | 3.11.1 |
| pytest | 9.0.2（asyncio 模式 `Mode.AUTO`） |
| 向量后端 | 本地 `LocalVectorStore`（零外部依赖） |
| 嵌入模型 | 内置 `HashEmbedding`（未配置 API Key 时自动降级） |
| 重排器 | 内置 `RuleReranker` |
| 大模型 | `MockLLM`（确定性输出，保证用例可复现） |
| 数据库 | 每会话独立临时 SQLite（`terraforge_test_*`），互不污染 |
| 索引目录 | 临时目录，测试间隔离 |

> 说明：零依赖默认配置（Hash 嵌入 + 本地向量库 + 规则重排 + MockLLM）使整套测试**无需任何外部服务即可运行**，可在 CI 中直接执行。生产环境只需切换 `EMBEDDING_PROVIDER` / `VECTOR_BACKEND` / `LLM_PROVIDER` 环境变量即可接入真实模型与向量库。

---

## 3. 测试策略（分层）

| 层级 | 模块 | 关注点 |
|---|---|---|
| 单元测试 | `test_retrieval.py`、`test_ingestion.py` | 嵌入相似度、BM25、规则重排排序、文档切分（章节路径/条文号/表格不切断/强制性条文识别） |
| 集成测试 | `test_rag_pipeline.py` | Stage0–Stage7 全链路、意图路由、多轮历史、安全强审、零召回缺口提示 |
| 接口测试 | `test_api.py` | HTTP 层：健康检查、知识库 CRUD、文档生命周期、问答/检索/流式、治理接口、非法文件拦截 |
| E2E 守卫 | `test_e2e_guards.py` | 锁定三类线上缺陷的回归：相关性地板、闲聊污染缺口、意图冲突 |

测试夹具（`tests/conftest.py`）提供独立的临时数据库、向量索引与上传目录，并通过 `sample_kb` 夹具一键创建标准领域知识库，保证用例间状态隔离。

---

## 4. 测试结果汇总

```
============================== 39 passed in ~8s ==============================
```

### 4.1 分模块明细

| 测试模块 | 用例数 | 结果 | 关键验证点 |
|---|---|---|---|
| `test_retrieval.py` | 4 | ✅ | Hash 嵌入相似度、BM25 索引、本地向量库增删查、规则重排排序 |
| `test_ingestion.py` | 9 | ✅ | 标题层级解析、章节路径、条文号抽取、规范编号抽取、关键词/分词、表格不切断、强制性条文识别 |
| `test_rag_pipeline.py` | 11 | ✅ | 全链路引用、意图路由（5 类）、长句不误判闲聊、多轮指代消解、零召回缺口提示、安全强审 |
| `test_api.py` | 9 | ✅ | 健康检查、知识库 CRUD、文档上传/入库/重索引、问答与流式、检索、治理接口、非法文件类型拦截 |
| `test_e2e_guards.py` | 6 | ✅ | 相关性地板拦截、弱候选拦截、缺口过滤、意图冲突消解（见第 5 节） |

> 注：`test_intent_routing` 为参数化用例（5 组输入），在汇总中计为 5 个独立用例。

---

## 5. 三类线上缺陷的回归保障（重点）

在联调阶段通过真实 HTTP 压测发现并以 E2E 守卫测试锁定了三个问题，均已修复并纳入 CI 守卫：

### 缺陷一：无关问题被"强行作答"（已修复 → 相关性地板）

- **现象**：提问"三文鱼刺身的冷藏保存温度"时，系统返回 `confidence=0.65` 并附带 4 条引用，违背"无证据不作答"铁律。
- **根因**：原逻辑只要检索到候选就进入生成，未校验相关性强弱。无关问题的典型特征是 **top1 擦边、其余分数断崖式下跌**。
- **修复**：在 `stage4_rerank` 引入**双判据相关性地板**——
  1. `top1.final_score ≥ MIN_RELEVANCE_SCORE`（默认 0.45）；
  2. 至少 `MIN_SUPPORT_COUNT`（默认 2）条候选 `final_score ≥ MIN_RELEVANCE_SCORE × MIN_SUPPORT_RATIO`（默认 0.3375）。
  
  未同时满足则置 `below_relevance_floor=True`，清空候选，`stage6` 返回专属缺口提示（`BELOW_FLOOR_ANSWER`），`stage7` 置 `confidence=0` 且强制人工复核。
- **守卫**：`test_unrelated_query_no_forced_answer`、`test_relevance_floor_blocks_weak_candidates`、`test_below_floor_yields_gap_hint`、`test_relevant_query_passes_floor`。
- **线上验证**：`POST /api/v1/rag/chat` 返回 `below_relevance_floor=true, confidence=0.0, citations=0`，答案含"相关性地板"缺口提示。

### 缺陷二：闲聊污染"知识缺口"（已修复）

- **现象**："你好，你是谁？"等闲聊问题（intent=chitchat, confidence=1.0）被计入知识缺口，干扰治理看板。
- **根因**：原 `knowledge_gaps` 仅按 `(hit_count==0) | (confidence<0.45)` 过滤，闲聊 `hit_count=0` 被误纳入。
- **修复**：在过滤条件中增加 `.filter(QueryLog.intent != QueryIntent.CHITCHAT.value)`，闲聊类问题不进入缺口统计；同时保留"零召回"与"低可信度召回"两类真实缺口。
- **守卫**：`test_chitchat_excluded_from_knowledge_gaps`。
- **线上验证**：`GET /api/v1/governance/knowledge-gaps` 结果包含真实零召回问题，但不再出现"你好"类闲聊。

### 缺陷三：质量描述 + 案例参考 误判为"质量分析"（已修复）

- **现象**："混凝土裂缝的案例可以参考"被判为 `quality_diagnosis` 而非 `case_retrieval`。
- **根因**：该问句同时命中质量关键词（裂缝）与案例关键词，两者得分持平，因 `QUALITY_DIAGNOSIS` 在规则表中靠前列而胜出（平局取先）。
- **修复**：在 `_rule_intent` 增加**意图冲突消解**——当用户显式索要"案例/经验/参考"（含"参考/类似/可以/有哪些/经验/教训"等配合词）时，令 `case_retrieval` 在平局或落后时反超，优先级高于质量诊断/方案生成。
- **守卫**：`test_case_retrieval_wins_quality_tie`。
- **线上验证**：该问句 `intent=case_retrieval, confidence≈0.66`。

---

## 6. 核心质量特性验证

| 特性 | 验证方式 | 结果 |
|---|---|---|
| **无证据不作答** | 无关/零召回问题 | 返回缺口提示，置信度归零，不编造 |
| **引用可追溯** | `test_full_pipeline_with_citations` | 引用可回溯到源文档与条文号 |
| **六信号可信度** | Stage7 加权（rel/cnt/div/cite/cov/penalty） | high/medium/low 三档与人工复核标志正确 |
| **安全强审** | `test_safety_query_forces_review` | 含"安全/坍塌"等问题强制 `need_human_review` |
| **多轮上下文** | `test_multi_turn_history` | 历史指代消解，且不把当前问句计入历史 |
| **闲聊免检索** | `test_chitchat_skips_retrieval` | chitchat 直接应答，无引用、免复核 |
| **长句防误判** | `test_chitchat_not_hijack_long_query` | "你好，混凝土养护要求"不被判为闲聊 |

---

## 7. 如何运行

```bash
# 进入后端目录
cd backend

# 运行全部测试
python3 -m pytest -q

# 仅运行 E2E 守卫（三类缺陷回归）
python3 -m pytest tests/test_e2e_guards.py -v

# 仅运行全链路 RAG 测试
python3 -m pytest tests/test_rag_pipeline.py -v

# 生成覆盖率报告（如已安装 pytest-cov）
python3 -m pytest --cov=app --cov-report=term-missing
```

测试默认使用零依赖配置，无需预先启动任何外部服务。

---

## 8. 局限与后续

- **模型能力未覆盖**：测试使用 `MockLLM` / `RuleReranker` / `HashEmbedding`，验证的是**流程正确性**与**治理铁律**，不评估真实大模型/CrossEncoder 的语义质量。接入真实模型后建议补充基于真实向量的回归基线。
- **并发与性能**：当前用例为功能验证，未包含高并发压测；生产部署建议另行执行负载测试。
- **前端** 通过 Playwright 无头浏览器完成冒烟（5 个核心页面 0 控制台错误），详见《用户手册》与前端构建产物。
- **建议**：将 `pytest` 接入 CI 流水线与 `docker-compose` 的 `healthcheck` 配合，确保每次提交均满足 39/39 通过门槛。

---

*报告由自动化测试套件生成，覆盖后端 5 大模块、39 个用例，全部通过。*
