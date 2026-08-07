"""Sprint6 知识库质量巡检模型：巡检报告快照。

与 GovernanceTask/KnowledgeGap 的分工：
- health_report（治理服务）：文档级问题（过期/无负责人/重复文档/解析失败/缺摘要）。
- QualityReport（本表）：切片级 + 检索级质量快照（超大/碎片切片、缺规范号、缺定位、
  近重复切片、孤立切片、低召回意图），可随时间对比，支撑质量巡检 Agent 闭环。
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (JSON, Column, DateTime, Float, Index, Integer, String)

from app.db.session import Base


def _uid() -> str:
    return uuid.uuid4().hex


class QualityReport(Base):
    """一次知识库质量巡检的持久化快照。"""
    __tablename__ = "tf_quality_report"

    id = Column(String(32), primary_key=True, default=_uid)
    kb_id = Column(String(32), default="", index=True, comment="被巡检的知识库；空=全部")
    tenant_id = Column(String(32), nullable=False, default="default", index=True)
    scope = Column(String(16), default="all", comment="all=全库 | kb=单库")

    score = Column(Float, default=100.0, comment="综合质量分 0~100")
    total_docs = Column(Integer, default=0)
    total_chunks = Column(Integer, default=0)
    issue_count = Column(Integer, default=0)

    issue_counts = Column(JSON, default=dict, comment="按类型计数 {issue_type: n}")
    issues = Column(JSON, default=list, comment="问题明细列表（截断保存前 N 条）")
    suggestions = Column(JSON, default=list, comment="巡检 Agent 给出的行动建议")

    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index("idx_quality_kb", "kb_id"),
        Index("idx_quality_tenant", "tenant_id"),
    )
