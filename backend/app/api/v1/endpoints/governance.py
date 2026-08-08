"""Stage7 知识治理 API。"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.logging import get_trace_id
from app.core.security import get_current_user
from app.db.session import get_db
from app.schemas.common import ApiResponse, PageData
from app.schemas.governance import (GovernanceDashboard, GovernanceTaskCreate,
                                    GovernanceTaskOut, GovernanceTaskUpdate,
                                    KBHealthReport, KnowledgeGap, KnowledgeGapAccept,
                                    KnowledgeGapOut, OperationReport)
from app.schemas.admin_report import GovernanceDashboardKB
from app.services.governance_service import GovernanceService

# Sprint4 RBAC：治理接口全部要求有效 API Key
router = APIRouter(dependencies=[Depends(get_current_user)])


@router.get("/health-report", response_model=ApiResponse[KBHealthReport],
            summary="知识库体检报告")
def health_report(kb_id: Optional[str] = None, db: Session = Depends(get_db)):
    return ApiResponse.ok(GovernanceService(db).health_report(kb_id), trace_id=get_trace_id())


# ==================== 知识缺口闭环 ====================
@router.get("/gaps", response_model=ApiResponse[List[KnowledgeGapOut]],
            summary="知识缺口清单（持久化待办，可按状态/意图过滤）")
def list_gaps(status: str = "", intent: str = "",
              limit: int = Query(50, ge=1, le=200),
              offset: int = Query(0, ge=0), db: Session = Depends(get_db)):
    items, total = GovernanceService(db).list_knowledge_gaps(status, intent, limit, offset)
    return ApiResponse.ok([KnowledgeGapOut.model_validate(i) for i in items],
                          trace_id=get_trace_id())


@router.post("/gaps/{gap_id}/accept", response_model=ApiResponse[GovernanceTaskOut],
             summary="采纳缺口：生成'补充资料'治理任务（闭环）")
def accept_gap(gap_id: str, payload: KnowledgeGapAccept, db: Session = Depends(get_db)):
    t = GovernanceService(db).accept_gap(
        gap_id, assignee=payload.assignee, kb_id=payload.kb_id,
        priority=payload.priority, due_days=payload.due_days)
    return ApiResponse.ok(GovernanceTaskOut.model_validate(t),
                          "已生成治理任务，缺口进入闭环", get_trace_id())


@router.post("/gaps/{gap_id}/reject", response_model=ApiResponse[KnowledgeGapOut],
             summary="驳回缺口：标记为暂不处理")
def reject_gap(gap_id: str, db: Session = Depends(get_db)):
    g = GovernanceService(db).reject_gap(gap_id)
    return ApiResponse.ok(KnowledgeGapOut.model_validate(g), "已驳回", get_trace_id())


@router.get("/dashboard", response_model=ApiResponse[GovernanceDashboard],
            summary="治理总览看板（缺口/任务/覆盖/高频缺口）")
def dashboard(days: int = Query(30, ge=1, le=365), db: Session = Depends(get_db)):
    return ApiResponse.ok(GovernanceDashboard(**GovernanceService(db).governance_dashboard(days)),
                          trace_id=get_trace_id())


@router.get("/dashboard/kb/{kb_id}", response_model=ApiResponse[GovernanceDashboardKB],
            summary="治理看板按知识库下钻（健康/缺口/任务/质量分）")
def dashboard_kb(kb_id: str, db: Session = Depends(get_db)):
    return ApiResponse.ok(
        GovernanceDashboardKB(**GovernanceService(db).dashboard_kb(kb_id)),
        trace_id=get_trace_id())


@router.post("/tasks", response_model=ApiResponse[GovernanceTaskOut], summary="创建治理事项")
def create_task(payload: GovernanceTaskCreate, db: Session = Depends(get_db)):
    t = GovernanceService(db).create_task(payload)
    return ApiResponse.ok(GovernanceTaskOut.model_validate(t), "创建成功", get_trace_id())


@router.post("/tasks/auto-generate", response_model=ApiResponse[List[GovernanceTaskOut]],
             summary="根据体检结果自动生成治理事项")
def auto_generate(kb_id: Optional[str] = None, assignee: str = "",
                  db: Session = Depends(get_db)):
    tasks = GovernanceService(db).generate_tasks_from_health(kb_id, assignee)
    return ApiResponse.ok([GovernanceTaskOut.model_validate(t) for t in tasks],
                          f"生成 {len(tasks)} 条治理事项", get_trace_id())


@router.get("/tasks", response_model=ApiResponse[PageData[GovernanceTaskOut]],
            summary="治理事项列表")
def list_tasks(status: str = "", assignee: str = "", kb_id: str = "", task_type: str = "",
               page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200),
               db: Session = Depends(get_db)):
    items, total = GovernanceService(db).list_tasks(
        status, assignee, kb_id, (page - 1) * page_size, page_size, task_type)
    return ApiResponse.ok(PageData[GovernanceTaskOut](
        items=[GovernanceTaskOut.model_validate(i) for i in items],
        total=total, page=page, page_size=page_size), trace_id=get_trace_id())


@router.put("/tasks/{task_id}", response_model=ApiResponse[GovernanceTaskOut],
            summary="更新治理事项")
def update_task(task_id: str, payload: GovernanceTaskUpdate, db: Session = Depends(get_db)):
    t = GovernanceService(db).update_task(task_id, **payload.model_dump(exclude_none=True))
    return ApiResponse.ok(GovernanceTaskOut.model_validate(t), "更新成功", get_trace_id())


@router.get("/knowledge-gaps", response_model=ApiResponse[List[KnowledgeGap]],
            summary="知识缺口清单")
def knowledge_gaps(days: int = Query(30, ge=1, le=365), limit: int = Query(20, ge=1, le=100),
                   db: Session = Depends(get_db)):
    return ApiResponse.ok(GovernanceService(db).knowledge_gaps(days, limit),
                          trace_id=get_trace_id())


@router.get("/operation-report", response_model=ApiResponse[OperationReport],
            summary="知识库运营报告（周报/月报）")
def operation_report(days: int = Query(7, ge=1, le=365), db: Session = Depends(get_db)):
    return ApiResponse.ok(GovernanceService(db).operation_report(days), trace_id=get_trace_id())
