"""Sprint7-T3 未命中原因归因 Schema。"""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class MissDiagnoseRequest(BaseModel):
    """未命中归因请求：对一条查询做根因分析（可选记录为知识缺口）。"""
    query: str = Field(..., min_length=1, description="待归因的查询")
    kb_id: Optional[str] = Field(None, description="限定检索的知识库；空=当前租户全部")
    top_k: int = Field(10, ge=1, le=50, description="召回候选数量")
    capture_gap: bool = Field(False, description="若为知识缺口则记录到治理（capture_gap）")


class MissReason(BaseModel):
    """单条归因根因。"""
    model_config = ConfigDict(from_attributes=True)
    code: str = ""                       # missing_doc | intent_misroute | rewrite_drift | chunking_bad
    label: str = ""
    confidence: float = 0.0             # 0~1，该根因的可信度
    evidence: str = ""                  # 触发该判定的管线信号证据
    suggestion: str = ""                # 可执行的修复建议


class MissDiagnoseResult(BaseModel):
    """未命中归因结果。"""
    model_config = ConfigDict(from_attributes=True)
    query: str = ""
    intent: str = ""
    intent_confidence: float = 0.0
    target_domains: List[str] = []
    out_of_scope: bool = False
    need_retrieval: bool = True
    retrieved_count: int = 0
    broad_retrieved_count: int = 0
    top_fusion_score: float = 0.0
    top_rerank_score: float = 0.0
    mean_rerank_score: float = 0.0
    top_broad_fusion_score: float = 0.0
    verdict: str = "mixed"              # missing_doc | intent_misroute | chunking_bad | rewrite_drift | retrieval_ok | mixed
    reasons: List[MissReason] = []
    gap_captured: bool = False
    gap_id: str = ""
