"""评测体系 API（Sprint 5）。

- GET  /eval/golden       查看黄金评测集
- POST /eval/golden       新增评测样本（auth）
- DELETE /eval/golden/{id} 删除评测样本（auth）
- POST /eval/run          运行评测，返回 Recall@K / MRR / NDCG@K（auth）
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.logging import get_trace_id
from app.core.security import get_current_user, get_tenant_id
from app.db.session import get_db
from app.models.identity import User
from app.schemas.common import ApiResponse
from app.services.eval_service import load_golden, run_evaluation, save_golden

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


@router.post("/run", summary="运行检索评测（auth）")
async def run_eval(request: Request, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    tenant_id = get_tenant_id(request)
    result = await run_evaluation(db, tenant_id=tenant_id)
    agg = result.get("aggregated", {})
    msg = (f"评测 {result.get('n_queries')} 题 | "
           f"Recall@5={agg.get('delivered_recall@k', {}).get(5)} "
           f"MRR={agg.get('delivered_mrr')} "
           f"命中率={agg.get('hit_rate')}")
    return ApiResponse.ok(result, msg, trace_id=get_trace_id())
