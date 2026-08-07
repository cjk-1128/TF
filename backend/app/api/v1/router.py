"""API v1 路由聚合。"""
from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.endpoints import chat, governance, knowledge, eval, quality

api_router = APIRouter()
api_router.include_router(knowledge.router, prefix="/knowledge", tags=["知识库管理"])
api_router.include_router(chat.router, prefix="/rag", tags=["智能问答"])
api_router.include_router(governance.router, prefix="/governance", tags=["知识治理"])
api_router.include_router(eval.router, prefix="/eval", tags=["评测体系"])
api_router.include_router(quality.router, prefix="/quality", tags=["质量巡检"])
