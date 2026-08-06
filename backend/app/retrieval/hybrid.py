"""
混合检索器（Stage2-Stage4 核心）
==============================
双通道并行召回 -> RRF 融合 + 加权分数 -> 领域优先级加权 -> 阈值过滤
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from app.core.config import settings
from app.core.logging import get_logger
from app.llm.factory import get_embedding
from app.retrieval.bm25_index import get_bm25_index
from app.vectorstore.factory import get_vector_store

logger = get_logger(__name__)


@dataclass
class Candidate:
    chunk_id: str
    content: str = ""
    meta: Dict = field(default_factory=dict)
    vector_score: float = 0.0
    bm25_score: float = 0.0
    vector_rank: int = 0
    bm25_rank: int = 0
    fusion_score: float = 0.0

    @property
    def doc_id(self) -> str:
        return self.meta.get("doc_id", "")

    @property
    def domain(self) -> str:
        return self.meta.get("domain", "")


class HybridRetriever:
    """向量 + BM25 双通道混合检索。"""

    def __init__(self):
        self.vs = get_vector_store()
        self.bm25 = get_bm25_index()
        self.embed = get_embedding()

    async def retrieve(self, query: str, *, top_k: int | None = None,
                       kb_ids: Optional[List[str]] = None,
                       domains: Optional[List[str]] = None,
                       domain_priority: Optional[List[str]] = None) -> List[Candidate]:
        top_k = top_k or settings.RETRIEVAL_TOP_K

        vec_task = asyncio.create_task(self._vector_search(query, top_k, kb_ids, domains))
        bm_task = asyncio.to_thread(self.bm25.search, query, top_k, kb_ids, domains)
        vec_hits, bm_hits = await asyncio.gather(vec_task, bm_task)

        pool: Dict[str, Candidate] = {}
        for rank, h in enumerate(vec_hits, start=1):
            pool[h.id] = Candidate(chunk_id=h.id, content=h.content, meta=h.meta,
                                   vector_score=round(h.score, 6), vector_rank=rank)
        for rank, (cid, score, meta) in enumerate(bm_hits, start=1):
            c = pool.get(cid)
            if c:
                c.bm25_score, c.bm25_rank = score, rank
            else:
                pool[cid] = Candidate(chunk_id=cid, content=meta.get("content", ""),
                                      meta=meta, bm25_score=score, bm25_rank=rank)

        # ---- RRF + 加权融合 ----
        k = settings.RRF_K
        wv, wb = settings.HYBRID_VECTOR_WEIGHT, settings.HYBRID_BM25_WEIGHT
        prio = {d: 1.0 + 0.06 * (len(domain_priority) - i)
                for i, d in enumerate(domain_priority or [])}

        for c in pool.values():
            rrf = 0.0
            if c.vector_rank:
                rrf += wv / (k + c.vector_rank)
            if c.bm25_rank:
                rrf += wb / (k + c.bm25_rank)
            weighted = wv * c.vector_score + wb * c.bm25_score
            both = 1.12 if (c.vector_rank and c.bm25_rank) else 1.0  # 双通道命中加成
            score = (0.5 * rrf * k + 0.5 * weighted) * both * prio.get(c.domain, 1.0)
            c.fusion_score = round(score, 6)

        result = sorted(pool.values(), key=lambda x: x.fusion_score, reverse=True)
        result = [c for c in result if c.fusion_score >= settings.SCORE_THRESHOLD]
        logger.info("混合检索 | 向量%d 关键词%d 融合后%d", len(vec_hits), len(bm_hits), len(result))
        return result[:top_k]

    async def _vector_search(self, query: str, top_k: int,
                             kb_ids: Optional[List[str]], domains: Optional[List[str]]):
        try:
            qv = await self.embed.embed_query(query)
            return await asyncio.to_thread(self.vs.search, qv, top_k, kb_ids, domains)
        except Exception as e:  # noqa: BLE001
            logger.error("向量通道失败，仅用关键词通道: %s", e)
            return []


_retriever: HybridRetriever | None = None


def get_retriever() -> HybridRetriever:
    global _retriever
    if _retriever is None:
        _retriever = HybridRetriever()
    return _retriever
