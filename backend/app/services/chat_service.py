"""对话服务：会话管理 + RAG 问答落库 + 反馈。"""
from __future__ import annotations

from datetime import datetime
import time
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.constants import QueryIntent
from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.core.security import can_access_kb
from app.models.conversation import Citation, Conversation, Message
from app.models.governance import FeedbackRecord, QueryLog
from app.models.identity import User
from app.models.knowledge import KnowledgeBase
from app.rag.pipeline import get_pipeline
from app.rag.state import RAGState
from app.schemas.chat import (ChatRequest, ChatResponse, CitationOut,
                              ConversationCreate, RetrievedChunk, StageTrace)
from app.utils.text import truncate

logger = get_logger(__name__)


class ChatService:
    def __init__(self, db: Session):
        self.db = db

    # ==================== 会话 ====================
    def create_conversation(self, payload: ConversationCreate) -> Conversation:
        conv = Conversation(
            title=payload.title, user_id=payload.user_id,
            kb_ids=payload.kb_ids or [],
            project_name=payload.context.project_name,
            project_type=payload.context.project_type,
            discipline=payload.context.discipline,
            region=payload.context.region,
        )
        self.db.add(conv)
        self.db.flush()
        return conv

    def get_conversation(self, conv_id: str) -> Conversation:
        c = self.db.query(Conversation).filter(Conversation.id == conv_id).first()
        if not c:
            raise NotFoundError(f"会话不存在: {conv_id}")
        return c

    def list_conversations(self, user_id: str = "", offset: int = 0,
                           limit: int = 20, tenant_id: Optional[str] = None
                           ) -> Tuple[List[Conversation], int]:
        q = self.db.query(Conversation)
        if tenant_id:
            q = q.filter(Conversation.tenant_id == tenant_id)
        if user_id:
            q = q.filter(Conversation.user_id == user_id)
        total = q.count()
        items = q.order_by(Conversation.updated_at.desc()).offset(offset).limit(limit).all()
        return items, total

    def delete_conversation(self, conv_id: str) -> None:
        self.db.delete(self.get_conversation(conv_id))

    def list_messages(self, conv_id: str) -> List[Message]:
        self.get_conversation(conv_id)
        return (self.db.query(Message)
                .filter(Message.conversation_id == conv_id)
                .order_by(Message.created_at).all())

    def _resolve_kb_ids(self, requested, tenant_id: str,
                        user: User | None) -> List[str]:
        """解析检索范围：仅保留当前租户内用户可访问的知识库 ID。"""
        q = self.db.query(KnowledgeBase).filter(KnowledgeBase.is_active.is_(True))
        if requested:
            kbs = q.filter(KnowledgeBase.id.in_(list(requested))).all()
        else:
            kbs = q.filter(KnowledgeBase.tenant_id == tenant_id).all()
        return [kb.id for kb in kbs if can_access_kb(user, kb)]

    # ==================== RAG 问答 ====================
    async def chat(self, req: ChatRequest, tenant_id: str = "default",
                   user: User | None = None) -> ChatResponse:
        t0 = time.perf_counter()
        # 1. 会话准备
        if req.conversation_id:
            conv = self.get_conversation(req.conversation_id)
        else:
            conv = self.create_conversation(ConversationCreate(
                title=truncate(req.query, 30), user_id=req.user_id,
                kb_ids=req.kb_ids,
                context=req.context or ConversationCreate().context,
            ))
        conv.tenant_id = tenant_id  # Sprint4 多租户隔离
        if req.context:
            conv.project_name = req.context.project_name or conv.project_name
            conv.project_type = req.context.project_type or conv.project_type
            conv.discipline = req.context.discipline or conv.discipline
            conv.region = req.context.region or conv.region
        if req.kb_ids:
            conv.kb_ids = req.kb_ids

        # 解析检索范围：仅限当前租户内用户可访问的知识库（防止跨租户泄漏）
        resolved_kb_ids = self._resolve_kb_ids(req.kb_ids, tenant_id, user)

        # 2. 用户消息落库
        user_msg = Message(conversation_id=conv.id, role="user", content=req.query)
        self.db.add(user_msg)
        self.db.flush()

        # 3. 答案缓存（仅首轮无历史参与，避免多轮上下文串缓存）
        #    命中后跳过 Stage0-7 全链路 + LLM，但仍走持久化（消息/引用/查询日志）。
        ans_key = None
        cached = None
        first_turn = (conv.message_count or 0) == 0
        if settings.CACHE_ANSWER_ENABLED and first_turn:
            from app.core.cache import default_cache, answer_cache_key
            ctx = req.context
            ans_key = answer_cache_key(
                req.query, tid=tenant_id,
                kb=tuple(resolved_kb_ids),
                dom=tuple(d.value for d in req.domains),
                tk=req.top_k,
                ctx=(ctx.project_name, ctx.project_type, ctx.discipline, ctx.region)
                if ctx else ("", "", "general", ""),
            )
            cached = default_cache.get(ans_key)

        if cached is not None:
            resp = ChatResponse(**cached)
            assistant = self._persist_response(
                resp, conv, user_msg, req, tenant_id, capture_gap=False)
            resp.conversation_id = conv.id
            resp.message_id = assistant.id
            # 命中缓存本应更快：回报本次实际耗时，反映缓存提速
            resp.latency_ms = int((time.perf_counter() - t0) * 1000)
            logger.info("答案缓存命中 | query=%s | 实际耗时%dms",
                        truncate(req.query, 40), resp.latency_ms)
            return resp

        # 4. 执行 Pipeline（首轮未命中缓存，或多轮始终重算）
        state = RAGState(
            query=req.query, conversation_id=conv.id, user_id=req.user_id,
            tenant_id=tenant_id,
            kb_ids=resolved_kb_ids,
            domains=[d.value for d in req.domains],
            top_k=req.top_k,
            project_name=conv.project_name or "", project_type=conv.project_type or "",
            discipline=conv.discipline or "general", region=conv.region or "",
            current_message_id=user_msg.id,
        )
        state = await get_pipeline().run(state, self.db)

        resp = ChatResponse(
            conversation_id=conv.id, message_id="", query=req.query,
            rewritten_query=state.rewritten_query,
            intent=state.intent.value, intent_label=state.intent.label,
            intent_confidence=state.intent_confidence,
            retrieval_strategy=state.retrieval_plan.strategy if state.retrieval_plan else "",
            target_domains=state.target_domains,
            out_of_scope=state.out_of_scope,
            answer=state.answer,
            citations=[CitationOut(**c.__dict__) for c in state.citations],
            confidence=state.confidence,
            confidence_level=state.confidence_level.value,
            need_human_review=state.need_human_review,
            review_hint=state.review_hint,
            below_relevance_floor=state.below_relevance_floor,
            retrieved=[RetrievedChunk(
                chunk_id=c.chunk_id, doc_id=c.doc_id,
                doc_title=c.meta.get("doc_title", ""),
                standard_code=c.meta.get("standard_code", ""),
                section_path=c.meta.get("section_path", ""),
                clause_no=c.meta.get("clause_no", ""),
                page_no=int(c.meta.get("page_no", 0) or 0),
                domain=c.domain, content=truncate(c.content, 300),
                is_mandatory=bool(c.meta.get("is_mandatory")),
                vector_score=c.vector_score, bm25_score=c.bm25_score,
                fusion_score=c.fusion_score,
                rerank_score=float(c.meta.get("rerank_score", 0.0)),
                final_score=float(c.meta.get("final_score", 0.0)),
            ) for c in state.reranked],
            stage_traces=[StageTrace(stage=t.stage, name=t.name,
                                     elapsed_ms=t.elapsed_ms, detail=t.detail)
                          for t in state.traces],
            latency_ms=state.latency_ms,
            token_usage=state.token_usage or {},
        )

        assistant = self._persist_response(
            resp, conv, user_msg, req, tenant_id, capture_gap=True, state=state)
        resp.conversation_id = conv.id
        resp.message_id = assistant.id

        if ans_key is not None:
            from app.core.cache import default_cache
            try:
                default_cache.set(ans_key, resp.model_dump(), ttl=settings.CACHE_ANSWER_TTL)
            except Exception as e:  # noqa: BLE001
                logger.warning("答案缓存写入失败（不影响主流程）: %s", e)

        return resp

    # ==================== 持久化（命中/未命中共用） ====================
    def _persist_response(self, resp: ChatResponse, conv, user_msg, req, tenant_id,
                          capture_gap: bool, state=None) -> Message:
        """落库助手消息 + 引用 + 查询日志（缓存命中与未命中共用）。

        capture_gap=True 时（仅未命中分支）触发治理 Agent 自动捕获知识缺口；
        命中分支跳过，避免同一问题重复生成待办。state 为 None 时（命中分支）
        用 resp.retrieved 数量近似 hit_count。
        """
        assistant = Message(
            conversation_id=conv.id, role="assistant", content=resp.answer,
            intent=resp.intent, rewritten_query=resp.rewritten_query,
            confidence=resp.confidence, confidence_level=resp.confidence_level,
            need_human_review=1 if resp.need_human_review else 0,
            latency_ms=resp.latency_ms,
            stage_trace={t.stage: {"name": t.name, "ms": t.elapsed_ms, **t.detail}
                         for t in resp.stage_traces},
            token_usage=resp.token_usage or {},
        )
        self.db.add(assistant)
        self.db.flush()

        for c in resp.citations:
            self.db.add(Citation(
                message_id=assistant.id, index_no=c.index_no, chunk_id=c.chunk_id,
                doc_id=c.doc_id, doc_title=c.doc_title, standard_code=c.standard_code,
                section_path=c.section_path, clause_no=c.clause_no, page_no=c.page_no,
                snippet=c.snippet, score=c.score, domain=c.domain,
            ))

        conv.message_count = (conv.message_count or 0) + 2
        conv.updated_at = datetime.utcnow()

        if capture_gap and state is not None:
            if (state.intent != QueryIntent.CHITCHAT
                    and (not state.context_chunks
                         or state.confidence < 0.45
                         or state.below_relevance_floor)):
                try:
                    from app.services.governance_service import GovernanceService
                    GovernanceService(self.db).capture_gap(
                        query=req.query, intent=state.intent.value,
                        domains=state.target_domains, user_id=req.user_id,
                        confidence=state.confidence)
                except Exception as e:  # noqa: BLE001
                    logger.warning("知识缺口自动捕获失败（不影响主流程）: %s", e)

        hit_count = len(state.context_chunks) if state is not None else len(resp.retrieved)
        self.db.add(QueryLog(
            conversation_id=conv.id, user_id=req.user_id, query=req.query,
            intent=resp.intent, hit_count=hit_count,
            confidence=resp.confidence,
            answered=bool(hit_count) and resp.confidence > 0,
            latency_ms=resp.latency_ms,
        ))
        self.db.flush()
        return assistant

    # ==================== 反馈 ====================
    def add_feedback(self, message_id: str, rating: int, reason: str = "",
                     comment: str = "") -> FeedbackRecord:
        msg = self.db.query(Message).filter(Message.id == message_id).first()
        if not msg:
            raise NotFoundError(f"消息不存在: {message_id}")
        fb = FeedbackRecord(message_id=message_id, conversation_id=msg.conversation_id,
                            rating=rating, reason=reason, comment=comment)
        self.db.add(fb)
        self.db.flush()
        return fb
