"""Phase 5 治理 admin 报告服务。

- performance_report(): 聚合进程内 Prometheus 指标 + 缓存统计 + 向量/BM25 计数，
  产出检索/LLM/Embedding 性能实时快照。
- gate_reports(tenant_id): 入库/发布前质量门禁，按知识库评估向量完整率、覆盖率、
  质量分，给出 pass/fail 结论（纯 DB 计算，不触发重量级语义巡检）。
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.constants import KnowledgeDomain
from app.core.logging import get_logger
from app.core import prom_metrics as app_metrics
from app.models.knowledge import Chunk, KnowledgeBase
from app.models.quality import QualityReport

logger = get_logger(__name__)


class AdminReportService:
    def __init__(self, db: Session):
        self.db = db

    # ==================== 性能报告 ====================
    def performance_report(self) -> dict:
        # 刷新向量/BM25 计数 gauge，保证快照数值最新
        try:
            from app.vectorstore.factory import get_vector_store
            from app.retrieval.bm25_index import get_bm25_index
            app_metrics.set_gauge("terraforge_vector_count", get_vector_store().count())
            app_metrics.set_gauge("terraforge_bm25_count", get_bm25_index().count())
        except Exception as e:  # noqa: BLE001
            logger.warning("刷新 vector/bm25 gauge 失败：%s", e)

        snap = app_metrics.snapshot()
        try:
            from app.core.cache import cache_stats
            cs = cache_stats()
        except Exception:  # noqa: BLE001
            cs = {}

        hist = snap.get("histograms", {})

        def lat(name: str) -> dict:
            h = hist.get(name)
            if not h or not h.get("count"):
                return {"count": 0, "avg": 0.0, "p50": None, "p95": None, "p99": None}
            return {
                "count": h["count"],
                "avg": round(h["avg"], 4),
                "p50": round(h["p50"], 4) if h.get("p50") is not None else None,
                "p95": round(h["p95"], 4) if h.get("p95") is not None else None,
                "p99": round(h["p99"], 4) if h.get("p99") is not None else None,
            }

        req_total = int(snap.get("counters", {}).get("terraforge_requests_total", 0) or 0)
        err = app_metrics.request_error_count()
        gauges = snap.get("gauges", {})

        return {
            "generated_at": datetime.utcnow(),
            "is_snapshot": True,
            "requests_total": req_total,
            "error_count": err,
            "error_rate": round(err / req_total, 4) if req_total else 0.0,
            "request_duration": lat("terraforge_request_duration_seconds"),
            "retrieval_duration": lat("terraforge_retrieval_duration_seconds"),
            "embedding_duration": lat("terraforge_embedding_duration_seconds"),
            "llm_duration": lat("terraforge_llm_duration_seconds"),
            "cache_hits": int(cs.get("l1_hit", 0) or 0) + int(cs.get("l2_hit", 0) or 0),
            "cache_misses": int(cs.get("miss", 0) or 0),
            "cache_hit_rate": float(cs.get("hit_rate", 0.0) or 0.0),
            "vector_count": int(gauges.get("terraforge_vector_count", 0) or 0),
            "bm25_count": int(gauges.get("terraforge_bm25_count", 0) or 0),
        }

    # ==================== 门禁报告 ====================
    def gate_reports(self, tenant_id: str) -> dict:
        min_comp = float(settings.GATE_VECTOR_COMPLETENESS_MIN)
        min_score = float(settings.GATE_QUALITY_SCORE_MIN)

        kbs = (self.db.query(KnowledgeBase)
               .filter(KnowledgeBase.tenant_id == tenant_id,
                       KnowledgeBase.is_active.is_(True))
               .all())

        items: list[dict] = []
        overall_pass = True
        for kb in kbs:
            total = (self.db.query(func.count(Chunk.id))
                     .filter(Chunk.kb_id == kb.id, Chunk.is_deleted.is_(False))
                     .scalar() or 0)
            with_vid = (self.db.query(func.count(Chunk.id))
                        .filter(Chunk.kb_id == kb.id, Chunk.is_deleted.is_(False),
                                Chunk.vector_id.isnot(None), Chunk.vector_id != "")
                        .scalar() or 0)
            completeness = round(with_vid / total, 4) if total else 1.0

            # 覆盖率：从切片实际统计各域分布（自洽，不依赖质量巡检快照）
            domain_rows = (self.db.query(Chunk.domain, func.count(Chunk.id))
                           .filter(Chunk.kb_id == kb.id, Chunk.is_deleted.is_(False))
                           .group_by(Chunk.domain).all())
            domain_counts = {d: c for d, c in domain_rows}
            empty_domains = [d.value for d in KnowledgeDomain
                             if domain_counts.get(d.value, 0) == 0]

            # 质量分 + 向量体检：取该库最近一次质量巡检快照
            rep = (self.db.query(QualityReport)
                   .filter(QualityReport.kb_id == kb.id,
                           QualityReport.tenant_id == tenant_id)
                   .order_by(QualityReport.created_at.desc()).first())
            score = rep.score if rep else None
            vh = (rep.vector_health or {}) if rep else {}
            missing_v = int(vh.get("missing", 0) or 0)
            zero_v = int(vh.get("zero", 0) or 0)

            passed = True
            reasons: list[str] = []
            if completeness < min_comp:
                passed = False
                reasons.append(f"向量完整率 {completeness:.2%} < 阈值 {min_comp:.0%}")
            if score is not None and score < min_score:
                passed = False
                reasons.append(f"质量分 {score:.1f} < 阈值 {min_score:.0f}")
            if missing_v:
                passed = False
                reasons.append(f"{missing_v} 个切片缺失向量")
            if zero_v:
                passed = False
                reasons.append(f"{zero_v} 个零向量")
            if empty_domains:
                passed = False
                reasons.append(f"覆盖盲区(零切片域): {', '.join(empty_domains)}")
            if score is None:
                reasons.append("尚未运行质量巡检，质量分未知")

            overall_pass = overall_pass and passed
            items.append({
                "kb_id": kb.id,
                "kb_name": kb.name,
                "total_chunks": total,
                "chunks_with_vector": with_vid,
                "vector_completeness": completeness,
                "quality_score": score,
                "missing_vector": missing_v,
                "zero_vector": zero_v,
                "empty_domains": empty_domains,
                "passed": passed,
                "reasons": reasons,
            })

        passed_n = sum(1 for i in items if i["passed"])
        return {
            "generated_at": datetime.utcnow(),
            "tenant_id": tenant_id,
            "vector_completeness_min": min_comp,
            "quality_score_min": min_score,
            "overall_passed": overall_pass,
            "kbs": items,
            "summary": {
                "total": len(items),
                "passed": passed_n,
                "failed": len(items) - passed_n,
            },
        }
