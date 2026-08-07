"""Sprint6 知识库质量巡检 Schema。"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class QualityIssue(BaseModel):
    """单条质量问题。"""
    issue_type: str = Field(..., description=(
        "oversized_chunk/tiny_chunk/missing_standard_code/missing_location/"
        "duplicate_chunk/orphan_chunk/low_recall_intent"))
    severity: str = "medium"          # high/medium/low
    chunk_id: str = ""
    doc_id: str = ""
    doc_title: str = ""
    kb_id: str = ""
    detail: str = ""
    suggestion: str = ""
    extra: dict = {}                  # 相似度、关联切片、命中率等补充信息


class QualityInspectRequest(BaseModel):
    kb_id: Optional[str] = None       # 空=全租户全部知识库
    dup_threshold: float = Field(0.92, ge=0.5, le=0.999,
                                 description="近重复切片余弦阈值")
    orphan_threshold: float = Field(0.12, ge=0.0, le=0.9,
                                    description="孤立切片：与其他切片最大相似度低于此值")
    max_chunk_chars: int = Field(1200, ge=200, le=8000, description="超大切片阈值")
    min_chunk_chars: int = Field(40, ge=1, le=500, description="碎片切片阈值")
    run_recall_probe: bool = Field(True, description="是否跑黄金集低召回意图探针")
    persist: bool = Field(True, description="是否把本次巡检快照落库")
    max_issue_detail: int = Field(200, ge=10, le=2000, description="明细最多保存条数")


class QualityReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str = ""
    kb_id: str = ""
    tenant_id: str = "default"
    scope: str = "all"
    score: float = 100.0
    total_docs: int = 0
    total_chunks: int = 0
    issue_count: int = 0
    issue_counts: dict = {}
    issues: List[QualityIssue] = []
    suggestions: List[str] = []
    created_at: Optional[datetime] = None


class QualityReportSummary(BaseModel):
    """报告列表项（不含明细，用于历史趋势）。"""
    model_config = ConfigDict(from_attributes=True)
    id: str
    kb_id: str = ""
    scope: str = "all"
    score: float = 100.0
    total_docs: int = 0
    total_chunks: int = 0
    issue_count: int = 0
    issue_counts: dict = {}
    created_at: Optional[datetime] = None


class QualityIssueConvert(BaseModel):
    """把一条质量问题采纳为治理任务。"""
    issue_type: str
    doc_id: str = ""
    kb_id: str = ""
    title: str = ""
    detail: str = ""
    suggestion: str = ""
    assignee: str = ""
    priority: str = "medium"
    due_days: int = 14
