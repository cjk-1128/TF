"""Sprint7-T2 质量巡检定时化 + 阈值告警服务。

把「一次巡检」包装成「一次带告警评估的巡检周期」：
- 跑 QualityInspector.inspect 落库快照；
- 与上次快照对比，质量分低于阈值 或 新增高危问题 时写入 QualityAlert；
- 提供告警的列表/详情/解决/删除 与 质量分趋势构建。
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.alert import QualityAlert
from app.models.quality import QualityReport
from app.schemas.quality import (QualityAlertOut, ScoreTrendPoint,
                                 ScoreTrendSeries)
from app.services.quality_service import QualityInspector

logger = get_logger(__name__)

# 被认定为「高危」的问题类型（质量巡检中 severity=high 的只有低召回意图）。
HIGH_SEVERITY_TYPES = {"low_recall_intent"}


def _high_count(issue_counts: dict) -> int:
    return sum(int(issue_counts.get(t, 0) or 0) for t in HIGH_SEVERITY_TYPES)


# ---------------------------------------------------------------- 周期巡检 + 告警
async def run_scheduled_inspection(
    db: Session, tenant_id: str = "default", *,
    kb_id: Optional[str] = None,
    score_threshold: float = 80.0,
    new_high_threshold: int = 1,
    dup_threshold: float = 0.92,
    orphan_threshold: float = 0.12,
    max_chunk_chars: int = 1200,
    min_chunk_chars: int = 40,
    run_recall_probe: bool = True,
) -> Tuple[dict, List[QualityAlert]]:
    """运行一次巡检并把快照落库，随后评估阈值产出告警。

    返回 (report_result, created_alerts)。
    """
    report_result = await QualityInspector(db).inspect(
        tenant_id=tenant_id, kb_id=kb_id,
        dup_threshold=dup_threshold, orphan_threshold=orphan_threshold,
        max_chunk_chars=max_chunk_chars, min_chunk_chars=min_chunk_chars,
        run_recall_probe=run_recall_probe, persist=True,
    )
    alerts = evaluate_and_persist_alerts(
        db, report_result, score_threshold=score_threshold,
        new_high_threshold=new_high_threshold)
    return report_result, alerts


def evaluate_and_persist_alerts(
    db: Session, report_result: dict, *,
    score_threshold: float = 80.0, new_high_threshold: int = 1,
) -> List[QualityAlert]:
    """根据本次巡检结果与上次快照对比，落库告警记录。"""
    report_id = report_result.get("id", "")
    tenant_id = report_result.get("tenant_id", "default")
    kb_id = report_result.get("kb_id", "")
    score = float(report_result.get("score", 100.0))
    issue_counts = report_result.get("issue_counts") or {}
    current_high = _high_count(issue_counts)

    # 上次快照（同租户同范围，排除本次）
    prev: Optional[QualityReport] = (
        db.query(QualityReport)
        .filter(QualityReport.tenant_id == tenant_id,
                QualityReport.kb_id == kb_id,
                QualityReport.id != report_id)
        .order_by(QualityReport.created_at.desc())
        .first()
    )
    prev_high = _high_count(prev.issue_counts or {}) if prev else 0
    new_high = max(0, current_high - prev_high)

    created: List[QualityAlert] = []
    scope = report_result.get("scope", "all")

    # 1) 低分告警
    if score < score_threshold:
        al = QualityAlert(
            tenant_id=tenant_id, kb_id=kb_id, scope=scope,
            alert_type="low_score", severity="high",
            score=round(score, 1), threshold=score_threshold,
            new_high_issue_count=0, prev_high_issue_count=prev_high,
            high_issue_count=current_high,
            issue_count=int(report_result.get("issue_count", 0)),
            title=f"质量分偏低：{score:.1f} < 阈值 {score_threshold:.0f}",
            detail=(f"本次巡检综合质量分 {score:.1f}，低于告警阈值 {score_threshold:.0f}；"
                    f"发现问题 {report_result.get('issue_count', 0)} 项，"
                    f"其中高危 {current_high} 项。建议查看明细并对重点问题采纳治理任务。"),
            report_id=report_id,
        )
        db.add(al)
        created.append(al)

    # 2) 新增高危问题告警
    if new_high >= new_high_threshold:
        al = QualityAlert(
            tenant_id=tenant_id, kb_id=kb_id, scope=scope,
            alert_type="new_high_severity", severity="high",
            score=round(score, 1), threshold=float(new_high_threshold),
            new_high_issue_count=new_high, prev_high_issue_count=prev_high,
            high_issue_count=current_high,
            issue_count=int(report_result.get("issue_count", 0)),
            title=f"新增 {new_high} 个高危问题（上次 {prev_high} 项）",
            detail=(f"相对上次巡检，高危问题（{', '.join(sorted(HIGH_SEVERITY_TYPES))}）"
                    f"由 {prev_high} 增至 {current_high} 项（新增 {new_high}）。"
                    f"当前质量分 {score:.1f}。建议优先补充对应意图的规范/案例资料。"),
            report_id=report_id,
        )
        db.add(al)
        created.append(al)

    if created:
        db.commit()
        for al in created:
            db.refresh(al)
        logger.warning("巡检告警 | tenant=%s | 新增 %d 条（低分=%s, 新高危=%d）",
                       tenant_id, len(created),
                       score < score_threshold, new_high)
    return created


# ---------------------------------------------------------------- 告警 CRUD
def list_alerts(db: Session, tenant_id: str = "default",
                resolved: Optional[bool] = None,
                limit: int = 50, offset: int = 0
                ) -> Tuple[List[QualityAlert], int]:
    q = db.query(QualityAlert).filter(QualityAlert.tenant_id == tenant_id)
    if resolved is not None:
        q = q.filter(QualityAlert.resolved == resolved)
    total = q.count()
    items = (q.order_by(QualityAlert.created_at.desc())
             .offset(offset).limit(limit).all())
    return items, total


def get_alert(db: Session, alert_id: str) -> Optional[QualityAlert]:
    return (db.query(QualityAlert)
            .filter(QualityAlert.id == alert_id).first())


def resolve_alert(db: Session, alert_id: str, note: str = "") -> Optional[QualityAlert]:
    al = get_alert(db, alert_id)
    if not al:
        return None
    al.resolved = True
    al.resolved_at = datetime.utcnow()
    al.resolve_note = note or ""
    db.commit()
    db.refresh(al)
    return al


def delete_alert(db: Session, alert_id: str) -> bool:
    al = get_alert(db, alert_id)
    if not al:
        return False
    db.delete(al)
    db.commit()
    return True


# ---------------------------------------------------------------- 质量分趋势
def build_score_trend(db: Session, tenant_id: str = "default",
                      kb_id: Optional[str] = None, limit: int = 30,
                      threshold: float = 80.0) -> ScoreTrendSeries:
    q = db.query(QualityReport).filter(QualityReport.tenant_id == tenant_id)
    if kb_id is not None:
        q = q.filter(QualityReport.kb_id == kb_id)
    reports = (q.order_by(QualityReport.created_at.asc())
               .limit(limit).all())
    points = [ScoreTrendPoint(
        created_at=r.created_at, score=float(r.score),
        issue_count=int(r.issue_count),
        high_issue_count=_high_count(r.issue_counts or {}),
    ) for r in reports]
    latest = points[-1].score if points else None
    first = points[0].score if points else None
    delta = round(latest - first, 2) if (latest is not None and first is not None) else None
    return ScoreTrendSeries(
        points=points, count=len(points), threshold=threshold,
        latest=latest, first_to_latest_delta=delta)
