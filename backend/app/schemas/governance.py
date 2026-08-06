"""Stage7 知识治理 Schema。"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class GovernanceTaskCreate(BaseModel):
    task_type: str = Field(..., description="expire_check/duplicate_merge/gap_fill/conflict_resolve")
    title: str
    description: str = ""
    target_doc_ids: List[str] = []
    kb_id: str = ""
    priority: str = "medium"
    assignee: str = ""
    watchers: List[str] = []
    due_date: Optional[datetime] = None


class GovernanceTaskUpdate(BaseModel):
    status: Optional[str] = None
    assignee: Optional[str] = None
    priority: Optional[str] = None
    description: Optional[str] = None
    watchers: Optional[List[str]] = None


class GovernanceTaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    task_type: str
    title: str
    description: str = ""
    target_doc_ids: List[str] = []
    kb_id: str = ""
    priority: str = "medium"
    status: str = "open"
    assignee: str = ""
    watchers: List[str] = []
    due_date: Optional[datetime] = None
    created_at: Optional[datetime] = None


class HealthIssue(BaseModel):
    issue_type: str          # expired / expiring_soon / no_owner / duplicate / stale / empty_summary
    severity: str = "medium"  # high/medium/low
    doc_id: str = ""
    doc_title: str = ""
    kb_id: str = ""
    detail: str = ""
    suggestion: str = ""


class KBHealthReport(BaseModel):
    generated_at: datetime
    total_kb: int = 0
    total_docs: int = 0
    total_chunks: int = 0
    valid_docs: int = 0
    need_update_docs: int = 0
    deprecated_docs: int = 0
    failed_docs: int = 0
    issues: List[HealthIssue] = []
    score: float = 100.0
    suggestions: List[str] = []


class KnowledgeGap(BaseModel):
    query: str
    count: int = 0
    avg_confidence: float = 0.0
    suggestion: str = ""


class KnowledgeGapOut(BaseModel):
    """持久化知识缺口（治理待办）。"""
    model_config = ConfigDict(from_attributes=True)
    id: str
    query: str
    query_key: str = ""
    intent: str = ""
    domains: List[str] = []
    user_id: str = "anonymous"
    occurrence_count: int = 1
    last_asked_at: Optional[datetime] = None
    status: str = "open"          # open/accepted/rejected/resolved
    suggested_kb_id: str = ""
    suggested_title: str = ""
    linked_task_id: str = ""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class KnowledgeGapAccept(BaseModel):
    assignee: str = ""
    kb_id: str = ""
    priority: str = ""
    due_days: int = 14


class GovernanceDashboard(BaseModel):
    period_days: int = 30
    gap_total: int = 0
    gap_by_status: dict = {}
    gap_by_intent: dict = {}
    open_gaps: int = 0
    task_total: int = 0
    task_by_status: dict = {}
    pending_tasks: int = 0
    answer_rate: float = 0.0
    total_queries: int = 0
    domain_doc_count: dict = {}
    top_gaps: List[dict] = []


class OperationReport(BaseModel):
    """知识库运营周报/月报"""
    period: str
    start: datetime
    end: datetime
    new_docs: int = 0
    new_chunks: int = 0
    total_queries: int = 0
    unanswered_queries: int = 0
    answer_rate: float = 0.0
    avg_confidence: float = 0.0
    avg_latency_ms: int = 0
    hot_topics: List[dict] = []
    knowledge_gaps: List[KnowledgeGap] = []
    pending_tasks: int = 0
    suggestions: List[str] = []
