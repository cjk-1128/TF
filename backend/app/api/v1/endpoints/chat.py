"""RAG 问答与会话 API。"""
from __future__ import annotations

import json
from typing import List

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.logging import get_trace_id
from app.core.security import get_current_user, get_tenant_id
from app.db.session import get_db
from app.models.identity import User
from app.schemas.chat import (ChatRequest, ChatResponse, ConversationCreate,
                              ConversationOut, FeedbackRequest, MessageOut,
                              RetrievedChunk, SearchRequest)
from app.schemas.common import ApiResponse, PageData
from app.schemas.retrieval import MissDiagnoseRequest, MissDiagnoseResult
from app.services.chat_service import ChatService
from app.services.miss_attribution import MissAttributor
from app.services.search_service import SearchService

router = APIRouter()


@router.post("/chat", response_model=ApiResponse[ChatResponse], summary="工程智能问答")
async def chat(req: ChatRequest, request: Request,
              db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    tenant_id = get_tenant_id(request)
    res = await ChatService(db).chat(req, tenant_id=tenant_id, user=user)
    return ApiResponse.ok(res, trace_id=get_trace_id())


@router.post("/chat/stream", summary="工程智能问答（SSE 流式）")
async def chat_stream(req: ChatRequest, request: Request,
                     db: Session = Depends(get_db),
                     user: User = Depends(get_current_user)):
    """
    先完整跑完 Stage0-Stage7（保证引用与可信度完整），
    再按字符流式推送答案，最后推送引用与追踪信息。
    """
    tenant_id = get_tenant_id(request)

    async def gen():
        res = await ChatService(db).chat(req, tenant_id=tenant_id, user=user)
        yield f"event: meta\ndata: {json.dumps({'conversation_id': res.conversation_id, 'message_id': res.message_id, 'intent': res.intent, 'intent_label': res.intent_label, 'retrieval_strategy': res.retrieval_strategy, 'out_of_scope': res.out_of_scope}, ensure_ascii=False)}\n\n"
        buf = res.answer
        for i in range(0, len(buf), 20):
            yield f"event: delta\ndata: {json.dumps({'text': buf[i:i + 20]}, ensure_ascii=False)}\n\n"
        payload = {
            "citations": [c.model_dump() for c in res.citations],
            "confidence": res.confidence,
            "confidence_level": res.confidence_level,
            "need_human_review": res.need_human_review,
            "review_hint": res.review_hint,
            "stage_traces": [t.model_dump() for t in res.stage_traces],
            "latency_ms": res.latency_ms,
        }
        yield f"event: done\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})


@router.post("/search", response_model=ApiResponse[List[RetrievedChunk]],
             summary="纯检索（不生成）")
async def search(req: SearchRequest, request: Request,
                db: Session = Depends(get_db),
                user: User = Depends(get_current_user)):
    tenant_id = get_tenant_id(request)
    # 检索范围限制在当前租户内可访问的知识库
    req.kb_ids = ChatService(db)._resolve_kb_ids(req.kb_ids, tenant_id, user)
    items = await SearchService(db).search(req, tenant_id=tenant_id)
    return ApiResponse.ok(items, f"命中 {len(items)} 条", get_trace_id())


@router.post("/explain", summary="检索可解释性（意图路由 + 多路打分明细）")
async def explain(req: SearchRequest, request: Request,
                  db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)):
    tenant_id = get_tenant_id(request)
    req.kb_ids = ChatService(db)._resolve_kb_ids(req.kb_ids, tenant_id, user)
    data = await SearchService(db).explain(req, tenant_id=tenant_id)
    return ApiResponse.ok(data, "检索可解释性明细", get_trace_id())


@router.post("/diagnose", response_model=ApiResponse[MissDiagnoseResult],
             summary="未命中原因归因（检索失败/低置信根因分析）")
async def diagnose(req: MissDiagnoseRequest, request: Request,
                   db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    """对一条查询做根因归因：缺文档 / 意图误路由 / 改写漂移 / 切分过碎，
    并可把确属知识缺口的归因喂给治理 Agent（capture_gap）。"""
    tenant_id = get_tenant_id(request)
    kb_ids = (ChatService(db)._resolve_kb_ids([req.kb_id], tenant_id, user)
              if req.kb_id else None)
    result = await MissAttributor(db).diagnose(
        query=req.query, tenant_id=tenant_id, kb_ids=kb_ids,
        top_k=req.top_k, capture_gap=req.capture_gap,
        user_id=user.id if user else "anonymous")
    return ApiResponse.ok(result, "未命中归因完成", get_trace_id())


# ==================== 会话 ====================
@router.post("/conversations", response_model=ApiResponse[ConversationOut], summary="创建会话")
def create_conversation(payload: ConversationCreate, request: Request,
                        db: Session = Depends(get_db),
                        user: User = Depends(get_current_user)):
    c = ChatService(db).create_conversation(payload)
    c.tenant_id = get_tenant_id(request)
    return ApiResponse.ok(ConversationOut.model_validate(c), "创建成功", get_trace_id())


@router.get("/conversations", response_model=ApiResponse[PageData[ConversationOut]],
            summary="会话列表")
def list_conversations(user_id: str = "", page: int = Query(1, ge=1),
                       page_size: int = Query(20, ge=1, le=100),
                       request: Request = None,
                       db: Session = Depends(get_db)):
    tenant_id = get_tenant_id(request) if request else None
    items, total = ChatService(db).list_conversations(
        user_id, (page - 1) * page_size, page_size, tenant_id=tenant_id)
    return ApiResponse.ok(PageData[ConversationOut](
        items=[ConversationOut.model_validate(i) for i in items],
        total=total, page=page, page_size=page_size), trace_id=get_trace_id())


@router.get("/conversations/{conv_id}/messages",
            response_model=ApiResponse[List[MessageOut]], summary="会话消息")
def list_messages(conv_id: str, db: Session = Depends(get_db)):
    msgs = ChatService(db).list_messages(conv_id)
    return ApiResponse.ok([MessageOut.model_validate(m) for m in msgs],
                          trace_id=get_trace_id())


@router.delete("/conversations/{conv_id}", response_model=ApiResponse[dict], summary="删除会话")
def delete_conversation(conv_id: str, db: Session = Depends(get_db)):
    ChatService(db).delete_conversation(conv_id)
    return ApiResponse.ok({"deleted": conv_id}, "删除成功", get_trace_id())


@router.post("/feedback", response_model=ApiResponse[dict], summary="答案反馈")
def feedback(req: FeedbackRequest, db: Session = Depends(get_db)):
    fb = ChatService(db).add_feedback(req.message_id, req.rating, req.reason, req.comment)
    return ApiResponse.ok({"id": fb.id}, "感谢反馈", get_trace_id())
