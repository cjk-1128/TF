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
from app.schemas.quality import (QualityInspectRequest, QualityIssueConvert,
                                  QualityReportOut, QualityReportSummary)
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
