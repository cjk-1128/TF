"""Phase 5 治理 admin 报告 Schema：性能报告 / 门禁报告 / 看板下钻。"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class LatencyStat(BaseModel):
    """直方图聚合（秒）。"""
    count: int = 0
    avg: float = 0.0
    p50: Optional[float] = None
    p95: Optional[float] = None
    p99: Optional[float] = None


class PerformanceReport(BaseModel):
    """检索/LLM/Embedding 性能实时快照。

    注：指标为进程内累积，服务重启后归零，属实时快照而非历史归档。
    """
    generated_at: datetime
    is_snapshot: bool = True
    requests_total: int = 0
    error_count: int = 0
    error_rate: float = 0.0
    request_duration: LatencyStat = LatencyStat()
    retrieval_duration: LatencyStat = LatencyStat()
    embedding_duration: LatencyStat = LatencyStat()
    llm_duration: LatencyStat = LatencyStat()
    cache_hits: int = 0
    cache_misses: int = 0
    cache_hit_rate: float = 0.0
    vector_count: int = 0
    bm25_count: int = 0


class GateItem(BaseModel):
    """单个知识库的入库/发布前质量门禁结果。"""
    kb_id: str = ""
    kb_name: str = ""
    total_chunks: int = 0
    chunks_with_vector: int = 0
    vector_completeness: float = 0.0     # 已分配 vector_id 的切片占比
    quality_score: Optional[float] = None  # 最近一次质量巡检分（未巡检为 None）
    missing_vector: int = 0               # 最近巡检发现未入库切片数
    zero_vector: int = 0                  # 最近巡检发现零向量切片数
    empty_domains: List[str] = []         # 零切片覆盖盲区域
    passed: bool = True
    reasons: List[str] = []               # 未通过原因（passed=False 时非空）


class GateReport(BaseModel):
    """质量门禁报告：逐知识库 + 总体结论。"""
    generated_at: datetime
    tenant_id: str = "default"
    vector_completeness_min: float = 0.99
    quality_score_min: float = 80.0
    overall_passed: bool = True
    kbs: List[GateItem] = []
    summary: dict = {}                    # {total, passed, failed}


class GovernanceDashboardKB(BaseModel):
    """治理看板按知识库下钻。"""
    kb_id: str
    kb_name: str
    health_score: float = 100.0
    health_issues: int = 0
    open_gaps: int = 0
    pending_tasks: int = 0
    quality_score: Optional[float] = None
    suggestions: List[str] = []
    top_issues: List[dict] = []           # high/medium 级体检问题明细
