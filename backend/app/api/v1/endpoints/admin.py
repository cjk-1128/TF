"""Phase 5 治理 admin 报告 API。

提供对齐 KnowForge admin 的三类报告端点（均需 RBAC 鉴权）：
  - GET /admin/performance_reports  检索/LLM/Embedding 性能实时快照
  - GET /admin/gate_reports         入库/发布前质量门禁（向量完整率/覆盖率/质量分）
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.logging import get_trace_id
from app.core.security import get_current_user, get_tenant_id
from app.schemas.common import ApiResponse
from app.db.session import get_db
from app.schemas.admin_report import GateReport, PerformanceReport
from app.services.admin_report_service import AdminReportService

# RBAC：admin 报告接口全部要求有效 API Key
router = APIRouter(dependencies=[Depends(get_current_user)])


@router.get("/performance_reports", response_model=ApiResponse[PerformanceReport],
            summary="性能报告（检索/LLM/Embedding 性能实时快照）")
def performance_reports(request: Request, db: Session = Depends(get_db)):
    data = AdminReportService(db).performance_report()
    return ApiResponse.ok(PerformanceReport(**data), trace_id=get_trace_id())


@router.get("/gate_reports", response_model=ApiResponse[GateReport],
            summary="质量门禁报告（入库/发布前：向量完整率/覆盖率/质量分）")
def gate_reports(request: Request, db: Session = Depends(get_db)):
    tenant_id = get_tenant_id(request)
    data = AdminReportService(db).gate_reports(tenant_id)
    return ApiResponse.ok(GateReport(**data), trace_id=get_trace_id())
