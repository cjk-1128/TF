"""Sprint7 评测运行快照与趋势 Schema。"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class EvalRunRequest(BaseModel):
    """运行评测请求。"""
    persist: bool = Field(True, description="是否落库为趋势快照")
    source: str = Field("api", description="来源标记：api | ci | schedule")
    note: str = Field("", max_length=255, description="备注，如本次改动说明")


class EvalRunSummary(BaseModel):
    """趋势列表 / 曲线用的精简快照（不含 per_query）。"""
    id: str
    tenant_id: str = "default"
    n_queries: int = 0
    n_positive: int = 0
    n_negative: int = 0
    golden_version: int = 1

    recall_at_1: float = 0.0
    recall_at_3: float = 0.0
    recall_at_5: float = 0.0
    ndcg_at_5: float = 0.0
    mrr: float = 0.0
    hit_rate: float = 0.0
    full_hit_rate: float = 0.0
    below_floor_rate: float = 0.0
    correct_rejection_rate: float = 0.0
    candidate_recall_at_20: float = 0.0

    baseline_delta: Dict[str, float] = {}
    status: str = "ok"
    source: str = "api"
    duration_ms: int = 0
    note: str = ""
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class EvalRunDetail(EvalRunSummary):
    """单次快照详情（含完整聚合与逐题）。"""
    kb_ids: List[str] = []
    aggregated: Dict[str, Any] = {}
    per_query: List[Dict[str, Any]] = []


class TrendPoint(BaseModel):
    """趋势曲线上的一个点。"""
    id: str
    created_at: Optional[datetime] = None
    recall_at_5: float = 0.0
    ndcg_at_5: float = 0.0
    mrr: float = 0.0
    hit_rate: float = 0.0
    correct_rejection_rate: float = 0.0
    status: str = "ok"
    source: str = "api"
    note: str = ""


class TrendSeries(BaseModel):
    """趋势响应：点序列 + 首末对比 + 基线。"""
    points: List[TrendPoint] = []
    count: int = 0
    baseline: Dict[str, float] = {}
    latest: Dict[str, float] = {}
    first_to_latest_delta: Dict[str, float] = {}
    regressed_count: int = 0
    improved_count: int = 0
