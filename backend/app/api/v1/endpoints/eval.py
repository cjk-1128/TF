"""评测体系 API（Sprint 5 + Sprint 7 趋势）。

- GET  /eval/golden        查看黄金评测集
- POST /eval/golden        新增评测样本（auth）
- DELETE /eval/golden/{id} 删除评测样本（auth）
- POST /eval/run           运行评测，返回 Recall@K / MRR / NDCG@K（auth，默认落库快照）
- GET  /eval/runs          历史评测快照列表（auth）
- GET  /eval/runs/{id}     单次快照详情（auth）
- DELETE /eval/runs/{id}   删除快照（auth）
- GET  /eval/trend         趋势序列（含基线对比与回归计数）（auth）
"""
from __future__ import annotations

import time
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.core.logging import get_trace_id
from app.core.security import get_current_user, get_tenant_id
from app.db.session import get_db
from app.models.identity import User
from app.schemas.common import ApiResponse, PageData
from app.schemas.eval import (EvalRunDetail, EvalRunRequest, EvalRunSummary,
                              TrendSeries)
from app.services.eval_service import (build_trend, delete_eval_run,
                                       get_eval_run, list_eval_runs,
                                       load_golden, persist_eval_run,
                                       run_evaluation, save_golden)

router = APIRouter()


@router.get("/golden", summary="查看黄金评测集")
def get_golden(request: Request, db: Session = Depends(get_db),
               user: User = Depends(get_current_user)):
    data = load_golden()
    items = data.get("items", [])
    # 列表页不返回超长的 ranked_ids，仅摘要
    summary = [{
        "id": i.get("id"),
        "query": i.get("query"),
        "expected_intent": i.get("expected_intent"),
        "relevant_count": len(i.get("relevant_chunk_ids", [])),
        "note": i.get("note", ""),
    } for i in items]
    return ApiResponse.ok({
        "version": data.get("version"),
        "tenant_id": data.get("tenant_id"),
        "count": len(items),
        "items": summary,
    }, trace_id=get_trace_id())


@router.post("/golden", summary="新增评测样本（auth）")
def add_golden(payload: dict, request: Request, db: Session = Depends(get_db),
               user: User = Depends(get_current_user)):
    if not payload.get("query") or not payload.get("relevant_chunk_ids"):
        return ApiResponse(code=400, message="query 与 relevant_chunk_ids 必填",
                            trace_id=get_trace_id())
    data = load_golden()
    items = data.setdefault("items", [])
    pid = payload.get("id") or f"g{len(items) + 1:02d}"
    payload["id"] = pid
    # 去重：同 id 覆盖
    items[:] = [i for i in items if i.get("id") != pid]
    items.append(payload)
    save_golden(data)
    return ApiResponse.ok({"id": pid}, "已添加评测样本", trace_id=get_trace_id())


@router.delete("/golden/{item_id}", summary="删除评测样本（auth）")
def del_golden(item_id: str, request: Request, db: Session = Depends(get_db),
               user: User = Depends(get_current_user)):
    data = load_golden()
    items = data.get("items", [])
    kept = [i for i in items if i.get("id") != item_id]
    if len(kept) == len(items):
        return ApiResponse(code=404, message=f"未找到样本 {item_id}",
                            trace_id=get_trace_id())
    data["items"] = kept
    save_golden(data)
    return ApiResponse.ok({"deleted": item_id}, "已删除", trace_id=get_trace_id())


@router.post("/run", summary="运行检索评测（auth，默认落库趋势快照）")
async def run_eval(request: Request, payload: Optional[EvalRunRequest] = None,
                   db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    tenant_id = get_tenant_id(request)
    payload = payload or EvalRunRequest()
    t0 = time.time()
    result = await run_evaluation(db, tenant_id=tenant_id, kb_ids=payload.kb_ids)
    duration_ms = int((time.time() - t0) * 1000)

    if payload.persist:
        run = persist_eval_run(db, result, tenant_id=tenant_id,
                               source=payload.source, note=payload.note,
                               duration_ms=duration_ms)
        result["run_id"] = run.id
        result["status"] = run.status
        result["baseline_delta"] = run.baseline_delta
        result["duration_ms"] = duration_ms

    agg = result.get("aggregated", {})
    msg = (f"评测 {result.get('n_queries')} 题 | "
           f"Recall@5={agg.get('delivered_recall@k', {}).get(5)} "
           f"MRR={agg.get('delivered_mrr')} "
           f"命中率={agg.get('hit_rate')}"
           + (f" | {result.get('status')}" if payload.persist else ""))
    return ApiResponse.ok(result, msg, trace_id=get_trace_id())


@router.get("/runs", summary="历史评测快照列表（auth）",
            response_model=ApiResponse[PageData[EvalRunSummary]])
def list_runs(request: Request, page: int = Query(1, ge=1),
              page_size: int = Query(20, ge=1, le=200),
              db: Session = Depends(get_db),
              user: User = Depends(get_current_user)):
    tenant_id = get_tenant_id(request)
    items, total = list_eval_runs(db, tenant_id=tenant_id,
                                  limit=page_size, offset=(page - 1) * page_size)
    page_data = PageData[EvalRunSummary](
        items=[EvalRunSummary.model_validate(i) for i in items],
        total=total, page=page, page_size=page_size)
    return ApiResponse.ok(page_data, trace_id=get_trace_id())


@router.get("/trend", summary="评测趋势序列（auth）",
            response_model=ApiResponse[TrendSeries])
def get_trend(request: Request, limit: int = Query(30, ge=2, le=100),
              db: Session = Depends(get_db),
              user: User = Depends(get_current_user)):
    tenant_id = get_tenant_id(request)
    trend = build_trend(db, tenant_id=tenant_id, limit=limit)
    return ApiResponse.ok(TrendSeries(**trend), trace_id=get_trace_id())


@router.get("/runs/{run_id}", summary="单次评测快照详情（auth）",
            response_model=ApiResponse[EvalRunDetail])
def get_run(run_id: str, request: Request, db: Session = Depends(get_db),
            user: User = Depends(get_current_user)):
    run = get_eval_run(db, run_id)
    if not run:
        raise NotFoundError(f"未找到评测快照 {run_id}")
    return ApiResponse.ok(EvalRunDetail.model_validate(run), trace_id=get_trace_id())


@router.delete("/runs/{run_id}", summary="删除评测快照（auth）")
def del_run(run_id: str, request: Request, db: Session = Depends(get_db),
            user: User = Depends(get_current_user)):
    if not delete_eval_run(db, run_id):
        raise NotFoundError(f"未找到评测快照 {run_id}")
    return ApiResponse.ok({"deleted": run_id}, "已删除", trace_id=get_trace_id())
