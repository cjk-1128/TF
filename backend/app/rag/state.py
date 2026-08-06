"""RAG Pipeline 全局状态对象（在 Stage0-Stage7 间流转）。"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.core.constants import ConfidenceLevel, KnowledgeDomain, QueryIntent
from app.retrieval.hybrid import Candidate


@dataclass
class StageRecord:
    stage: str
    name: str
    elapsed_ms: int = 0
    detail: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CitationItem:
    index_no: int
    chunk_id: str = ""
    doc_id: str = ""
    doc_title: str = ""
    standard_code: str = ""
    section_path: str = ""
    clause_no: str = ""
    page_no: int = 0
    snippet: str = ""
    score: float = 0.0
    domain: str = ""


@dataclass
class RAGState:
    # ---- 输入 ----
    query: str
    conversation_id: str = ""
    user_id: str = "anonymous"
    kb_ids: List[str] = field(default_factory=list)
    domains: List[str] = field(default_factory=list)
    top_k: Optional[int] = None

    # ---- Stage0 工程上下文 ----
    project_name: str = ""
    project_type: str = ""
    discipline: str = "general"
    region: str = ""
    history: List[Dict[str, str]] = field(default_factory=list)

    # ---- Stage1 路由 ----
    intent: QueryIntent = QueryIntent.UNKNOWN
    intent_confidence: float = 0.0
    need_retrieval: bool = True
    target_domains: List[str] = field(default_factory=list)

    # ---- Stage2 查询改写 ----
    rewritten_query: str = ""
    sub_queries: List[str] = field(default_factory=list)
    extracted_codes: List[str] = field(default_factory=list)

    # ---- Stage3-4 检索 & 重排 ----
    candidates: List[Candidate] = field(default_factory=list)
    reranked: List[Candidate] = field(default_factory=list)
    rejected: List[Candidate] = field(default_factory=list)  # 被相关性地板拦截的候选
    below_relevance_floor: bool = False  # 检索结果未达相关性门槛（无证据不作答）

    # ---- Stage5 上下文 ----
    context_text: str = ""
    context_chunks: List[Candidate] = field(default_factory=list)

    # ---- Stage6 生成 ----
    answer: str = ""
    citations: List[CitationItem] = field(default_factory=list)
    token_usage: Dict[str, int] = field(default_factory=dict)

    # ---- 可信度 ----
    confidence: float = 0.0
    confidence_level: ConfidenceLevel = ConfidenceLevel.LOW
    need_human_review: bool = True
    review_hint: str = ""

    # ---- 追踪 ----
    traces: List[StageRecord] = field(default_factory=list)
    started_at: float = field(default_factory=time.perf_counter)
    message_id: str = ""
    current_message_id: str = ""  # 当前轮 user 消息 id，加载历史时需排除
    error: str = ""

    def trace(self, stage: str, name: str, started: float, **detail) -> None:
        self.traces.append(StageRecord(
            stage=stage, name=name,
            elapsed_ms=int((time.perf_counter() - started) * 1000),
            detail=detail,
        ))

    @property
    def latency_ms(self) -> int:
        return int((time.perf_counter() - self.started_at) * 1000)

    @property
    def effective_query(self) -> str:
        return self.rewritten_query or self.query
