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
from app.utils.text import truncate

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
            ))
        return out
