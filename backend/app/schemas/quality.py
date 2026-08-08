"""Sprint6 知识库质量巡检 Schema。"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class QualityIssue(BaseModel):
    """单条质量问题。"""
    issue_type: str = Field(..., description=(
        "oversized_chunk/tiny_chunk/missing_standard_code/missing_location/"
        "duplicate_chunk/orphan_chunk/low_recall_intent/"
        "missing_vector/zero_vector/domain_coverage_gap/isolated_query"))
    severity: str = "medium"          # high/medium/low
    chunk_id: str = ""
    doc_id: str = ""
    doc_title: str = ""
    kb_id: str = ""
    detail: str = ""
    suggestion: str = ""
    extra: dict = {}                  # 相似度、关联切片、命中率、域、意图等补充信息


class QualityInspectRequest(BaseModel):
    kb_id: Optional[str] = None       # 空=全租户全部知识库
    dup_threshold: float = Field(0.92, ge=0.5, le=0.999,
                                 description="近重复切片余弦阈值")
    orphan_threshold: float = Field(0.12, ge=0.0, le=0.9,
                                    description="孤立切片：与其他切片最大相似度低于此值")
    max_chunk_chars: int = Field(1200, ge=200, le=8000, description="超大切片阈值")
    min_chunk_chars: int = Field(40, ge=1, le=500, description="碎片切片阈值")
    run_recall_probe: bool = Field(True, description="是否跑黄金集低召回意图探针")
    run_vector_checks: bool = Field(True, description="是否做向量质量体检（零向量/未入库）")
    feed_governance_gaps: bool = Field(False, description="是否把孤立查询回流为治理知识缺口")
    sparse_domain_threshold: int = Field(3, ge=1, le=100,
                                         description="域覆盖盲区判定：某域切片数≤该值视为稀疏")
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
    vector_health: Optional[dict] = None   # Sprint8：向量质量体检摘要（早期快照可能为 NULL）
    coverage: Optional[dict] = None        # Sprint8：域覆盖分布与稀疏域（早期快照可能为 NULL）
    isolated_queries: List[dict] = []  # Sprint8：零召回的孤立查询（仅本次响应，不落库）
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


# ---------------- Sprint7-T2 定时巡检 + 阈值告警 ----------------
class QualityScheduleRequest(BaseModel):
    """手动「立即巡检并告警」请求，可覆盖默认阈值。"""
    kb_id: Optional[str] = None
    score_threshold: float = Field(80.0, ge=0.0, le=100.0,
                                   description="质量分低于该值触发低分告警")
    new_high_threshold: int = Field(1, ge=0,
                                    description="相对上次新增高危问题数≥该值触发告警")
    dup_threshold: float = Field(0.92, ge=0.5, le=0.999)
    orphan_threshold: float = Field(0.12, ge=0.0, le=0.9)
    max_chunk_chars: int = Field(1200, ge=200, le=8000)
    min_chunk_chars: int = Field(40, ge=1, le=500)
    run_recall_probe: bool = Field(True, description="是否跑黄金集低召回意图探针")


class QualityAlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str = ""
    tenant_id: str = "default"
    kb_id: str = ""
    scope: str = "all"
    alert_type: str = "low_score"
    severity: str = "high"
    score: float = 100.0
    threshold: float = 80.0
    new_high_issue_count: int = 0
    prev_high_issue_count: int = 0
    high_issue_count: int = 0
    issue_count: int = 0
    title: str = ""
    detail: str = ""
    report_id: str = ""
    resolved: bool = False
    resolved_at: Optional[datetime] = None
    resolve_note: str = ""
    created_at: Optional[datetime] = None


class AlertResolveRequest(BaseModel):
    note: str = ""


class ScheduleRunResult(BaseModel):
    """「立即巡检并告警」的返回：本次巡检报告 + 产生的告警。"""
    report: QualityReportOut
    alerts: List[QualityAlertOut] = []
    score_threshold: float = 80.0
    new_high_threshold: int = 1


class ScoreTrendPoint(BaseModel):
    created_at: Optional[datetime] = None
    score: float = 100.0
    issue_count: int = 0
    high_issue_count: int = 0


class ScoreTrendSeries(BaseModel):
    points: List[ScoreTrendPoint] = []
    count: int = 0
    threshold: float = 80.0
    latest: Optional[float] = None
    first_to_latest_delta: Optional[float] = None
