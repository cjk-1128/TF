"""
评测服务（Sprint 5 评测体系）
=============================
对黄金集每条查询，跑真实的检索管线 Stage1→Stage4（意图路由→查询改写→
混合检索→重排），得到最终排序的 chunk 列表，再与人工标注的相关 chunk
计算 Recall@K / MRR / NDCG@K，并做均值聚合。

评测对象 = 交付给用户的重排结果（state.reranked，即最终进入上下文、
作为引用的前 N 条）；同时给出候选级召回（stage3 candidates）作为诊断，
用于区分"检索不到"与"重排/相关性门槛误杀"。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.core.metrics import evaluate_ranked, recall_at_k
from app.models.knowledge import KnowledgeBase
from app.rag import stages
from app.rag.state import RAGState

logger = get_logger(__name__)

GOLDEN_PATH = Path(__file__).resolve().parents[2] / "data" / "eval_golden.json"
DELIVERED_KS = [1, 3, 5]        # 重排后进入上下文的条数上限（RERANK_TOP_N=6）
RETRIEVAL_KS = [1, 3, 5, 10, 20]  # 候选池诊断口径


def load_golden(path: Path = GOLDEN_PATH) -> dict:
    if not path.exists():
        return {"version": 1, "tenant_id": "default", "items": []}
    return json.loads(path.read_text(encoding="utf-8"))


def save_golden(data: dict, path: Path = GOLDEN_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _resolve_scope(db: Session, tenant_id: str) -> List[str]:
    """默认评测范围 = 当前租户下全部 active KB（模拟"向整个知识库提问"）。"""
    kbs = db.query(KnowledgeBase).filter(
        KnowledgeBase.tenant_id == tenant_id,
        KnowledgeBase.is_active == True,  # noqa: E712
    ).all()
    return [k.id for k in kbs]


async def run_evaluation(db: Session, tenant_id: str = "default",
                          kb_ids: Optional[List[str]] = None,
                          ks: List[int] = DELIVERED_KS) -> dict:
    golden = load_golden()
    if kb_ids is None:
        kb_ids = _resolve_scope(db, tenant_id)

    per_query: List[Dict] = []
    for item in golden.get("items", []):
        q = item["query"]
        relevant = item.get("relevant_chunk_ids", [])

        # ---- 跑真实检索管线 Stage1→Stage4 ----
        state = RAGState(query=q, kb_ids=list(kb_ids), top_k=None)
        await stages.stage1_route(state)          # 意图路由 + 自适应检索策略
        await stages.stage2_rewrite(state)        # 查询改写/术语扩展
        state.need_retrieval = True               # 评测强制走检索（即便被判闲聊）
        state.below_relevance_floor = False
        await stages.stage3_retrieve(state)       # 混合检索（向量+BM25 RRF）
        await stages.stage4_rerank(state)         # 重排 + 相关性门槛

        delivered = [c.chunk_id for c in state.reranked]      # 最终交付（前 N）
        candidates = [c.chunk_id for c in state.candidates]   # 候选池（未截断）
        rel_set = set(relevant)

        delivered_metrics = evaluate_ranked(relevant, delivered, ks)
        retrieval_metrics = evaluate_ranked(relevant, candidates, RETRIEVAL_KS)
        cand_recall = {str(k): round(recall_at_k(relevant, candidates, k), 4)
                       for k in (10, 20)}

        per_query.append({
            "id": item["id"],
            "query": q,
            "expected_intent": item.get("expected_intent"),
            "intent": state.intent.value,
            "need_retrieval": state.need_retrieval,
            "below_floor": state.below_relevance_floor,
            "delivered_count": len(delivered),
            "candidate_count": len(candidates),
            "relevant_count": len(relevant),
            "hits_delivered": sum(1 for cid in delivered if cid in rel_set),
            "hits_candidates": sum(1 for cid in candidates if cid in rel_set),
            "delivered_metrics": delivered_metrics,
            "retrieval_metrics": retrieval_metrics,
            "candidate_recall": cand_recall,
            "ranked_ids": delivered,
        })

    # ---- 聚合（delivered 为主，retrieval 作诊断）----
    n = max(1, len(per_query))
    agg_recall = {k: round(sum(p["delivered_metrics"]["recall"][k] for p in per_query) / n, 4)
                  for k in ks}
    agg_ndcg = {k: round(sum(p["delivered_metrics"]["ndcg"][k] for p in per_query) / n, 4)
                for k in ks}
    agg_mrr = round(sum(p["delivered_metrics"]["mrr"] for p in per_query) / n, 4)
    agg_retrieval_recall = {k: round(sum(p["retrieval_metrics"]["recall"][k] for p in per_query) / n, 4)
                            for k in RETRIEVAL_KS}
    agg_cand_recall = {
        "10": round(sum(p["candidate_recall"]["10"] for p in per_query) / n, 4),
        "20": round(sum(p["candidate_recall"]["20"] for p in per_query) / n, 4),
    }
    # 命中率：至少命中 1 条相关 / 全部相关进前 N 的查询占比
    hit_rate = round(sum(1 for p in per_query if p["hits_delivered"] > 0) / n, 4)
    full_hit_rate = round(sum(1 for p in per_query if p["hits_delivered"] == p["relevant_count"]) / n, 4)
    below_floor_rate = round(sum(1 for p in per_query if p["below_floor"]) / n, 4)

    aggregated = {
        "delivered_recall@k": agg_recall,
        "delivered_ndcg@k": agg_ndcg,
        "delivered_mrr": agg_mrr,
        "retrieval_recall@k": agg_retrieval_recall,
        "candidate_recall@10": agg_cand_recall["10"],
        "candidate_recall@20": agg_cand_recall["20"],
        "hit_rate": hit_rate,
        "full_hit_rate": full_hit_rate,
        "below_floor_rate": below_floor_rate,
    }

    return {
        "tenant_id": tenant_id,
        "kb_ids": kb_ids,
        "ks": ks,
        "retrieval_ks": RETRIEVAL_KS,
        "n_queries": len(per_query),
        "golden_version": golden.get("version"),
        "aggregated": aggregated,
        "per_query": per_query,
    }
