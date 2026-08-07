"""对话 / RAG 问答 Schema。"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.core.constants import KnowledgeDomain


class ProjectContext(BaseModel):
    """Stage0 工程上下文"""
    project_name: str = ""
    project_type: str = ""
    discipline: str = "general"
    region: str = ""


class ConversationCreate(BaseModel):
    title: str = "新会话"
    user_id: str = "anonymous"
    kb_ids: List[str] = []
    context: ProjectContext = ProjectContext()


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    title: str
    user_id: str
    project_name: str = ""
    project_type: str = ""
    discipline: str = "general"
    region: str = ""
    kb_ids: List[str] = []
    message_count: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class CitationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    index_no: int = 1
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


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    role: str
    content: str
    intent: str = ""
    confidence: float = 0.0
    confidence_level: str = ""
    need_human_review: int = 0
    latency_ms: int = 0
    created_at: Optional[datetime] = None
    citations: List[CitationOut] = []


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    conversation_id: Optional[str] = None
    user_id: str = "anonymous"
    kb_ids: List[str] = []
    domains: List[KnowledgeDomain] = []
    context: Optional[ProjectContext] = None
    top_k: Optional[int] = None
    stream: bool = False


class RetrievedChunk(BaseModel):
    chunk_id: str
    doc_id: str
    doc_title: str = ""
    standard_code: str = ""
    section_path: str = ""
    clause_no: str = ""
    page_no: int = 0
    domain: str = ""
    content: str = ""
    is_mandatory: bool = False
    vector_score: float = 0.0
    bm25_score: float = 0.0
    fusion_score: float = 0.0
    rerank_score: float = 0.0
    final_score: float = 0.0
    matched_terms: List[str] = []


class StageTrace(BaseModel):
    stage: str
    name: str
    elapsed_ms: int = 0
    detail: Dict[str, Any] = {}


class ChatResponse(BaseModel):
    conversation_id: str
    message_id: str
    query: str
    rewritten_query: str = ""
    intent: str = ""
    intent_label: str = ""
    intent_confidence: float = 0.0
    retrieval_strategy: str = ""     # Intent Agent 给出的检索策略: precision/recall/balanced/none
    target_domains: List[str] = []  # 路由到的优先知识域
    out_of_scope: bool = False       # 与工程/资料无关，不应强答
    answer: str = ""
    citations: List[CitationOut] = []
    confidence: float = 0.0
    confidence_level: str = ""
    need_human_review: bool = False
    review_hint: str = ""
    below_relevance_floor: bool = False
    retrieved: List[RetrievedChunk] = []
    stage_traces: List[StageTrace] = []
    latency_ms: int = 0
    token_usage: Dict[str, int] = {}


class SearchRequest(BaseModel):
    """纯检索（不生成）"""
    query: str = Field(..., min_length=1)
    kb_ids: List[str] = []
    domains: List[KnowledgeDomain] = []
    top_k: int = 10
    use_rerank: bool = True


class FeedbackRequest(BaseModel):
    message_id: str
    rating: int = Field(..., ge=-1, le=1)
    reason: str = ""
    comment: str = ""
