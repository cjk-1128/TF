"""对话服务：会话管理 + RAG 问答落库 + 反馈。"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.models.conversation import Citation, Conversation, Message
from app.models.governance import FeedbackRecord, QueryLog
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
                           limit: int = 20) -> Tuple[List[Conversation], int]:
        q = self.db.query(Conversation)
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

    # ==================== RAG 问答 ====================
    async def chat(self, req: ChatRequest) -> ChatResponse:
        # 1. 会话准备
        if req.conversation_id:
            conv = self.get_conversation(req.conversation_id)
        else:
            conv = self.create_conversation(ConversationCreate(
                title=truncate(req.query, 30), user_id=req.user_id,
                kb_ids=req.kb_ids,
                context=req.context or ConversationCreate().context,
            ))
        if req.context:
            conv.project_name = req.context.project_name or conv.project_name
            conv.project_type = req.context.project_type or conv.project_type
            conv.discipline = req.context.discipline or conv.discipline
            conv.region = req.context.region or conv.region
        if req.kb_ids:
            conv.kb_ids = req.kb_ids

        # 2. 用户消息落库
        user_msg = Message(conversation_id=conv.id, role="user", content=req.query)
        self.db.add(user_msg)
        self.db.flush()

        # 3. 执行 Pipeline
        state = RAGState(
            query=req.query, conversation_id=conv.id, user_id=req.user_id,
            kb_ids=req.kb_ids or list(conv.kb_ids or []),
            domains=[d.value for d in req.domains],
            top_k=req.top_k,
            project_name=conv.project_name or "", project_type=conv.project_type or "",
            discipline=conv.discipline or "general", region=conv.region or "",
            current_message_id=user_msg.id,
        )
        state = await get_pipeline().run(state, self.db)

        # 4. 助手消息 + 引用落库
        assistant = Message(
            conversation_id=conv.id, role="assistant", content=state.answer,
            intent=state.intent.value, rewritten_query=state.rewritten_query,
            confidence=state.confidence, confidence_level=state.confidence_level.value,
            need_human_review=1 if state.need_human_review else 0,
            latency_ms=state.latency_ms,
            stage_trace={t.stage: {"name": t.name, "ms": t.elapsed_ms, **t.detail}
                         for t in state.traces},
            token_usage=state.token_usage or {},
        )
        self.db.add(assistant)
        self.db.flush()
        state.message_id = assistant.id

        for c in state.citations:
            self.db.add(Citation(
                message_id=assistant.id, index_no=c.index_no, chunk_id=c.chunk_id,
                doc_id=c.doc_id, doc_title=c.doc_title, standard_code=c.standard_code,
                section_path=c.section_path, clause_no=c.clause_no, page_no=c.page_no,
                snippet=c.snippet, score=c.score, domain=c.domain,
            ))

        conv.message_count = (conv.message_count or 0) + 2
        conv.updated_at = datetime.utcnow()

        # 5. 查询日志（Stage7 治理数据源）
        self.db.add(QueryLog(
            conversation_id=conv.id, user_id=req.user_id, query=req.query,
            intent=state.intent.value, hit_count=len(state.context_chunks),
            confidence=state.confidence,
            answered=bool(state.context_chunks) and state.confidence > 0,
            latency_ms=state.latency_ms,
        ))
        self.db.flush()

        return ChatResponse(
            conversation_id=conv.id, message_id=assistant.id, query=req.query,
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
