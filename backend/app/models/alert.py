"""Sprint7-T2 质量巡检告警模型。

由后台定时巡检 / 手动「立即巡检并告警」触发：
- 综合质量分低于阈值（alert_type=low_score）
- 相对上次巡检新增高危问题（alert_type=new_high_severity）
告警记录可被运维「解决」以关闭，用于质量治理闭环看板。
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (Boolean, Column, DateTime, Float, Index, Integer,
                        String)

from app.db.session import Base


def _uid() -> str:
    return uuid.uuid4().hex


class QualityAlert(Base):
    """一条质量巡检告警记录。"""
    __tablename__ = "tf_quality_alert"

    id = Column(String(32), primary_key=True, default=_uid)
    tenant_id = Column(String(32), nullable=False, default="default", index=True)
    kb_id = Column(String(32), default="", index=True,
                   comment="触发告警的知识库；空串=全库")
    scope = Column(String(16), default="all", comment="all=全库 | kb=单库")

    alert_type = Column(String(24), nullable=False,
                        comment="low_score | new_high_severity")
    severity = Column(String(8), default="high", comment="high/medium/low")
    score = Column(Float, default=100.0, comment="触发时的综合质量分 0~100")
    threshold = Column(Float, default=80.0, comment="触发所依据的阈值")
    new_high_issue_count = Column(Integer, default=0,
                                  comment="本次相对上次新增的高危问题数")
    prev_high_issue_count = Column(Integer, default=0,
                                   comment="上次巡检的高危问题数（对照用）")
    high_issue_count = Column(Integer, default=0,
                              comment="本次巡检的高危问题总数")
    issue_count = Column(Integer, default=0, comment="本次巡检问题总数")

    title = Column(String(255), default="")
    detail = Column(String(1000), default="")
    report_id = Column(String(32), default="",
                       comment="触发本次告警的 QualityReport.id")

    resolved = Column(Boolean, default=False, index=True,
                      comment="是否已解决/关闭")
    resolved_at = Column(DateTime, nullable=True)
    resolve_note = Column(String(255), default="")

    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index("idx_qalert_tenant", "tenant_id"),
        Index("idx_qalert_resolved", "resolved"),
        Index("idx_qalert_created", "created_at"),
    )
