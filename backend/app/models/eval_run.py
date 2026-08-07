"""Sprint7 评测运行快照模型：每次 /eval/run 落库，支撑趋势曲线与回归检测。

与 QualityReport 的分工：
- QualityReport：知识库"静态资产"质量（切片/文档层面的缺陷）。
- EvalRun（本表）：检索系统"动态效果"质量（Recall@K/MRR/NDCG@K 随时间的变化），
  用于回答"这次改动到底让检索变好了还是变差了"。

核心指标做了扁平化冗余存储（recall_at_5 等），避免趋势查询时逐行解 JSON。
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (JSON, Column, DateTime, Float, Index, Integer, String)

from app.db.session import Base


def _uid() -> str:
    return uuid.uuid4().hex


class EvalRun(Base):
    """一次检索评测的持久化快照。"""
    __tablename__ = "tf_eval_run"

    id = Column(String(32), primary_key=True, default=_uid)
    tenant_id = Column(String(32), nullable=False, default="default", index=True)
    kb_ids = Column(JSON, default=list, comment="本次评测覆盖的知识库 id 列表")

    golden_version = Column(Integer, default=1, comment="黄金集版本")
    n_queries = Column(Integer, default=0)
    n_positive = Column(Integer, default=0)
    n_negative = Column(Integer, default=0)

    # ---- 扁平化核心指标（趋势曲线直接取这些列）----
    recall_at_1 = Column(Float, default=0.0)
    recall_at_3 = Column(Float, default=0.0)
    recall_at_5 = Column(Float, default=0.0)
    ndcg_at_5 = Column(Float, default=0.0)
    mrr = Column(Float, default=0.0)
    hit_rate = Column(Float, default=0.0)
    full_hit_rate = Column(Float, default=0.0)
    below_floor_rate = Column(Float, default=0.0)
    correct_rejection_rate = Column(Float, default=0.0)
    candidate_recall_at_20 = Column(Float, default=0.0)

    # ---- 完整数据与基线对比 ----
    aggregated = Column(JSON, default=dict, comment="完整聚合指标")
    per_query = Column(JSON, default=list, comment="逐题结果（精简版，去掉 ranked_ids 明细）")
    baseline_delta = Column(JSON, default=dict, comment="相对基线的差值 {metric: delta}")

    status = Column(String(16), default="ok", index=True,
                    comment="improved=优于基线 | ok=持平 | regressed=低于基线")
    source = Column(String(16), default="api", comment="api | ci | schedule")
    duration_ms = Column(Integer, default=0)
    note = Column(String(255), default="")

    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index("idx_evalrun_tenant", "tenant_id"),
        Index("idx_evalrun_created", "created_at"),
    )
