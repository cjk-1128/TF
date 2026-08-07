"""纯检索服务：不经过 LLM，直接返回带出处的检索结果。"""
from __future__ import annotations

from typing import List

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.llm.factory import get_reranker
from app.models.knowledge import Document
from app.retrieval.hybrid import get_retriever
from app.schemas.chat import RetrievedChunk, SearchRequest
from app.utils.text import tokenize, truncate

logger = get_logger(__name__)


class SearchService:
    def __init__(self, db: Session):
        self.db = db

    async def search(self, req: SearchRequest) -> List[RetrievedChunk]:
        cands = await get_retriever().retrieve(
            req.query, top_k=max(req.top_k * 3, settings.RETRIEVAL_TOP_K),
            kb_ids=req.kb_ids or None,
            domains=[d.value for d in req.domains] or None,
        )
        if not cands:
            return []

        if req.use_rerank:
            pairs = await get_reranker().rerank(req.query, [c.content for c in cands],
                                                top_n=req.top_k)
            ordered = []
            for idx, score in pairs:
                c = cands[idx]
                c.meta["rerank_score"] = round(score, 6)
                c.meta["final_score"] = round(0.65 * score + 0.35 * min(c.fusion_score, 1.0), 6)
                ordered.append(c)
            ordered.sort(key=lambda x: x.meta.get("final_score", 0), reverse=True)
            cands = ordered
        cands = cands[:req.top_k]

        doc_ids = list({c.doc_id for c in cands if c.doc_id})
        doc_map = {d.id: d for d in self.db.query(Document)
                   .filter(Document.id.in_(doc_ids)).all()} if doc_ids else {}

        out: List[RetrievedChunk] = []
        for c in cands:
            d = doc_map.get(c.doc_id)
            out.append(RetrievedChunk(
                chunk_id=c.chunk_id, doc_id=c.doc_id,
                doc_title=d.title if d else c.meta.get("doc_title", ""),
                standard_code=(d.standard_code if d else "") or c.meta.get("standard_code", ""),
                section_path=c.meta.get("section_path", ""),
                clause_no=c.meta.get("clause_no", ""),
                page_no=int(c.meta.get("page_no", 0) or 0),
                domain=c.domain, content=truncate(c.content, 500),
                is_mandatory=bool(c.meta.get("is_mandatory")),
                vector_score=c.vector_score, bm25_score=c.bm25_score,
                fusion_score=c.fusion_score,
                rerank_score=float(c.meta.get("rerank_score", 0.0)),
                final_score=float(c.meta.get("final_score", c.fusion_score)),
                matched_terms=sorted(set(tokenize(req.query)) & set(tokenize(c.content))),
            ))
        return out

    async def explain(self, req: SearchRequest) -> dict:
        """检索可解释性：跑通 意图路由 -> 查询改写 -> 混合检索 -> 重排序，
        返回每路打分、命中词与路由决策的明细，不经过 LLM 生成。"""
        from app.rag import stages
        from app.rag.explain import build_explanation
        from app.rag.state import RAGState

        state = RAGState(
            query=req.query,
            kb_ids=list(req.kb_ids or []),
            domains=[d.value for d in req.domains] or [],
            top_k=req.top_k,
        )
        state = await stages.stage1_route(state)
        if not state.need_retrieval:
            state.explain = build_explanation(state)
            return state.explain

        state = await stages.stage2_rewrite(state)
        state = await stages.stage3_retrieve(state)
        state = await stages.stage4_rerank(state)
        state.explain = build_explanation(state)
        # 归因（T3 闭环）：把"为什么没答好"的根因一并透出，与可解释性联动
        try:
            from app.services.miss_attribution import MissAttributor
            attr = await MissAttributor(self.db).diagnose(
                req.query, kb_ids=list(req.kb_ids or []) or None, capture_gap=False)
            state.explain["attribution"] = attr
        except Exception as e:  # noqa: BLE001
            logger.warning("归因附加至可解释性失败（不影响主解释）: %s", e)
        return state.explain
