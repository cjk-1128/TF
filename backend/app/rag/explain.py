"""
检索可解释性（Sprint 6-T3）
=========================
把一次检索的内部决策"摊开"给用户看：
  - 意图路由：意图 / 置信度 / 越域 / 检索策略
  - 查询改写：改写后查询 / 子查询 / 抽取到的规范编号
  - 每个候选切片的多路打分：向量分 / BM25分 / RRF融合分 / 重排分 / 最终分
  - 命中词：查询词面与切片词面的交集（解释"为什么召回这条"）
  - 相关性地板：是否因未达门槛被拦截，及原因

该模块把 RAGState 加工成一个前端可直接渲染的 dict。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.rag.state import RAGState
from app.utils.text import tokenize, truncate


def _intent_info(state: RAGState) -> Dict[str, Any]:
    intent = state.intent
    if hasattr(intent, "value"):
        intent_value = intent.value
        intent_label = getattr(intent, "label", "") or ""
    else:
        intent_value = str(intent)
        intent_label = ""
    if state.retrieval_plan is not None:
        strategy = state.retrieval_plan.strategy
    elif not state.need_retrieval:
        strategy = "none"
    else:
        strategy = "default"
    return {
        "intent": intent_value,
        "intent_label": intent_label,
        "intent_confidence": round(float(state.intent_confidence), 4),
        "out_of_scope": bool(state.out_of_scope),
        "retrieval_strategy": strategy,
    }


def _explain_candidate(c, query_tokens: set, used: bool) -> Dict[str, Any]:
    chunk_tokens = set(tokenize(c.content))
    matched = sorted(query_tokens & chunk_tokens)
    return {
        "chunk_id": c.chunk_id,
        "doc_id": c.doc_id,
        "doc_title": c.meta.get("doc_title", ""),
        "standard_code": c.meta.get("standard_code", ""),
        "section_path": c.meta.get("section_path", ""),
        "clause_no": c.meta.get("clause_no", ""),
        "domain": c.domain,
        "snippet": truncate(c.content, 160),
        "vector_score": round(float(c.vector_score), 6),
        "bm25_score": round(float(c.bm25_score), 6),
        "vector_rank": c.vector_rank,
        "bm25_rank": c.bm25_rank,
        "fusion_score": round(float(c.fusion_score), 6),
        "rerank_score": round(float(c.meta.get("rerank_score", 0.0)), 6),
        "final_score": round(float(c.meta.get("final_score", c.fusion_score)), 6),
        "matched_terms": matched,
        "match_count": len(matched),
        "is_mandatory": bool(c.meta.get("is_mandatory")),
        "governance_status": c.meta.get("governance_status", "valid"),
        "used": used,
    }


def build_explanation(state: RAGState) -> Dict[str, Any]:
    """从 RAGState 抽取可解释性信息。"""
    query_tokens = set(tokenize(state.query))

    # 优先展示最终入选的切片；若被相关性地板拦截，则展示被拒候选（供排查）
    if state.reranked:
        pool = state.reranked
        used_ids = {c.chunk_id for c in state.reranked}
    elif state.rejected:
        pool = state.rejected
        used_ids = set()
    else:
        pool = state.candidates
        used_ids = set()

    rows = [_explain_candidate(c, query_tokens, c.chunk_id in used_ids) for c in pool]
    rows.sort(key=lambda r: r["final_score"], reverse=True)

    rejection_reason: Optional[str] = None
    if state.below_relevance_floor:
        for t in state.traces:
            if t.stage == "stage4" and t.detail.get("rejected_by_floor"):
                rejection_reason = t.detail.get("reason")
                break

    info = _intent_info(state)
    return {
        "query": state.query,
        "effective_query": state.effective_query,
        **info,
        "rewritten_query": state.rewritten_query,
        "sub_queries": state.sub_queries,
        "extracted_codes": state.extracted_codes,
        "need_retrieval": state.need_retrieval,
        "below_relevance_floor": state.below_relevance_floor,
        "rejection_reason": rejection_reason,
        "candidate_count": len(state.candidates),
        "final_count": len(state.reranked),
        "candidates": rows,
    }
