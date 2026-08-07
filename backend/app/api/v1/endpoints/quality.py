"""Sprint6 知识库质量巡检 API。

在治理"文档级体检"之上，提供"切片级 + 检索级"的质量巡检、历史快照与
"问题采纳为治理任务"的闭环入口。全部端点需 RBAC 鉴权。
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.core.logging import get_trace_id
from app.core.security import get_current_user, get_tenant_id
from app.db.session import get_db
from app.models.identity import User
from app.schemas.common import ApiResponse, PageData
from app.schemas.governance import GovernanceTaskOut
from app.schemas.quality import (AlertResolveRequest, QualityAlertOut,
                                  QualityInspectRequest, QualityIssueConvert,
                                  QualityReportOut, QualityReportSummary,
                                  QualityScheduleRequest, ScheduleRunResult,
                                  ScoreTrendSeries)
from app.services.alert_service import (build_score_trend, delete_alert,
                                         get_alert, list_alerts, resolve_alert,
                                         run_scheduled_inspection)
from app.services.quality_service import QualityInspector

# RBAC：质量巡检接口全部要求有效 API Key
router = APIRouter(dependencies=[Depends(get_current_user)])


@router.post("/inspect", response_model=ApiResponse[QualityReportOut],
             summary="运行知识库质量巡检（切片级+检索级），可落库为快照")
async def inspect(payload: QualityInspectRequest, request: Request,
                  db: Session = Depends(get_db)):
    tenant_id = get_tenant_id(request)
    result = await QualityInspector(db).inspect(
        tenant_id=tenant_id, kb_id=payload.kb_id,
        dup_threshold=payload.dup_threshold,
        orphan_threshold=payload.orphan_threshold,
        max_chunk_chars=payload.max_chunk_chars,
        min_chunk_chars=payload.min_chunk_chars,
        run_recall_probe=payload.run_recall_probe,
        run_vector_checks=payload.run_vector_checks,
        feed_governance_gaps=payload.feed_governance_gaps,
        sparse_domain_threshold=payload.sparse_domain_threshold,
        persist=payload.persist,
        max_issue_detail=payload.max_issue_detail,
    )
    return ApiResponse.ok(QualityReportOut(**result),
                          f"巡检完成，发现 {result['issue_count']} 个问题",
                          get_trace_id())


@router.get("/reports", response_model=ApiResponse[PageData[QualityReportSummary]],
            summary="质量巡检历史快照（用于趋势对比）")
def list_reports(request: Request, kb_id: Optional[str] = None,
                 page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                 db: Session = Depends(get_db)):
    tenant_id = get_tenant_id(request)
    items, total = QualityInspector(db).list_reports(
        tenant_id=tenant_id, kb_id=kb_id,
        limit=page_size, offset=(page - 1) * page_size)
    return ApiResponse.ok(PageData[QualityReportSummary](
        items=[QualityReportSummary.model_validate(i) for i in items],
        total=total, page=page, page_size=page_size), trace_id=get_trace_id())


@router.get("/reports/{report_id}", response_model=ApiResponse[QualityReportOut],
            summary="质量巡检报告详情（含问题明细）")
def get_report(report_id: str, db: Session = Depends(get_db)):
    rep = QualityInspector(db).get_report(report_id)
    if not rep:
        raise NotFoundError(f"质量报告不存在: {report_id}")
    return ApiResponse.ok(QualityReportOut.model_validate(rep), trace_id=get_trace_id())


@router.post("/issues/convert", response_model=ApiResponse[GovernanceTaskOut],
             summary="把一条质量问题采纳为治理任务（闭环）")
def convert_issue(payload: QualityIssueConvert, db: Session = Depends(get_db)):
    t = QualityInspector(db).convert_to_task(
        issue_type=payload.issue_type, doc_id=payload.doc_id, kb_id=payload.kb_id,
        title=payload.title, detail=payload.detail, suggestion=payload.suggestion,
        assignee=payload.assignee, priority=payload.priority, due_days=payload.due_days)
    return ApiResponse.ok(GovernanceTaskOut.model_validate(t),
                          "已生成治理任务", get_trace_id())


# ------------------------------------------------------------------ Sprint7-T2
@router.post("/schedule/trigger", response_model=ApiResponse[ScheduleRunResult],
             summary="立即巡检并评估阈值告警（手动触发一次调度周期）")
async def schedule_trigger(payload: QualityScheduleRequest, request: Request,
                           db: Session = Depends(get_db)):
    tenant_id = get_tenant_id(request)
    report_result, alerts = await run_scheduled_inspection(
        db, tenant_id, kb_id=payload.kb_id or None,
        score_threshold=payload.score_threshold,
        new_high_threshold=payload.new_high_threshold,
        dup_threshold=payload.dup_threshold,
        orphan_threshold=payload.orphan_threshold,
        max_chunk_chars=payload.max_chunk_chars,
        min_chunk_chars=payload.min_chunk_chars,
        run_recall_probe=payload.run_recall_probe,
    )
    result = ScheduleRunResult(
        report=QualityReportOut(**report_result),
        alerts=[QualityAlertOut.model_validate(a) for a in alerts],
        score_threshold=payload.score_threshold,
        new_high_threshold=payload.new_high_threshold,
    )
    msg = (f"巡检完成，质量分 {report_result['score']:.1f}"
           + (f"，触发 {len(alerts)} 条告警" if alerts else "，未触发告警"))
    return ApiResponse.ok(result, msg, get_trace_id())


@router.get("/alerts", response_model=ApiResponse[PageData[QualityAlertOut]],
            summary="质量巡检告警列表（可按解决状态筛选）")
def list_alert_endpoint(request: Request, resolved: Optional[bool] = None,
                        page: int = Query(1, ge=1),
                        page_size: int = Query(50, ge=1, le=200),
                        db: Session = Depends(get_db)):
    tenant_id = get_tenant_id(request)
    items, total = list_alerts(
        db, tenant_id=tenant_id, resolved=resolved,
        limit=page_size, offset=(page - 1) * page_size)
    return ApiResponse.ok(PageData[QualityAlertOut](
        items=[QualityAlertOut.model_validate(i) for i in items],
        total=total, page=page, page_size=page_size), trace_id=get_trace_id())


@router.get("/alerts/{alert_id}", response_model=ApiResponse[QualityAlertOut],
            summary="告警详情")
def get_alert_endpoint(alert_id: str, db: Session = Depends(get_db)):
    al = get_alert(db, alert_id)
    if not al:
        raise NotFoundError(f"告警不存在: {alert_id}")
    return ApiResponse.ok(QualityAlertOut.model_validate(al), trace_id=get_trace_id())


@router.post("/alerts/{alert_id}/resolve", response_model=ApiResponse[QualityAlertOut],
             summary="解决/关闭告警")
def resolve_alert_endpoint(alert_id: str, payload: AlertResolveRequest,
                           db: Session = Depends(get_db)):
    al = resolve_alert(db, alert_id, note=payload.note)
    if not al:
        raise NotFoundError(f"告警不存在: {alert_id}")
    return ApiResponse.ok(QualityAlertOut.model_validate(al),
                          "告警已解决", get_trace_id())


@router.delete("/alerts/{alert_id}", response_model=ApiResponse[None],
               summary="删除告警记录")
def delete_alert_endpoint(alert_id: str, db: Session = Depends(get_db)):
    if not delete_alert(db, alert_id):
        raise NotFoundError(f"告警不存在: {alert_id}")
    return ApiResponse.ok(None, "已删除告警", get_trace_id())


@router.get("/score-trend", response_model=ApiResponse[ScoreTrendSeries],
            summary="质量分趋势（用于趋势曲线，依赖 T1 趋势基础设施）")
def score_trend_endpoint(request: Request,
                         kb_id: Optional[str] = None,
                         limit: int = Query(30, ge=2, le=100),
                         threshold: float = Query(80.0, ge=0.0, le=100.0),
                         db: Session = Depends(get_db)):
    tenant_id = get_tenant_id(request)
    series = build_score_trend(db, tenant_id=tenant_id,
                               kb_id=kb_id or None, limit=limit,
                               threshold=threshold)
    return ApiResponse.ok(series, trace_id=get_trace_id())

