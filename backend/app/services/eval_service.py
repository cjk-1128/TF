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
from app.models.knowledge import Chunk, Document, KnowledgeBase
from app.rag import stages
from app.rag.state import RAGState
from app.schemas.knowledge import DocumentMeta, KnowledgeBaseCreate
from app.services.knowledge_service import KnowledgeService

logger = get_logger(__name__)

GOLDEN_PATH = Path(__file__).resolve().parents[2] / "data" / "eval_golden.json"
CORPUS_PATH = Path(__file__).resolve().parents[2] / "data" / "eval_corpus.json"
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
                          ks: List[int] = DELIVERED_KS,
                          golden: Optional[dict] = None) -> dict:
    """运行检索评测。

    golden : 可传入自定义黄金集（如 CI 自包含语料生成的集合）。
             为 None 时使用 data/eval_golden.json（生产黄金集）。
    """
    golden = golden or load_golden()
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
            "negative": bool(item.get("negative", False)),
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
    # 负样本（越域/无关）单独统计"正确拒答率"，不污染正样本命中率
    pos = [p for p in per_query if not p["negative"]]
    neg = [p for p in per_query if p["negative"]]
    n_pos = max(1, len(pos))
    n = max(1, len(per_query))

    agg_recall = {k: round(sum(p["delivered_metrics"]["recall"][k] for p in pos) / n_pos, 4)
                  for k in ks}
    agg_ndcg = {k: round(sum(p["delivered_metrics"]["ndcg"][k] for p in pos) / n_pos, 4)
                for k in ks}
    agg_mrr = round(sum(p["delivered_metrics"]["mrr"] for p in pos) / n_pos, 4)
    agg_retrieval_recall = {k: round(sum(p["retrieval_metrics"]["recall"][k] for p in pos) / n_pos, 4)
                            for k in RETRIEVAL_KS}
    agg_cand_recall = {
        "10": round(sum(p["candidate_recall"]["10"] for p in pos) / n_pos, 4),
        "20": round(sum(p["candidate_recall"]["20"] for p in pos) / n_pos, 4),
    }
    # 命中率：正样本中至少命中 1 条相关 / 全部相关进前 N 的查询占比
    hit_rate = round(sum(1 for p in pos if p["hits_delivered"] > 0) / n_pos, 4)
    full_hit_rate = round(sum(1 for p in pos if p["hits_delivered"] == p["relevant_count"]) / n_pos, 4)
    below_floor_rate = round(sum(1 for p in pos if p["below_floor"]) / n_pos, 4)
    # 正确拒答率：负样本应被相关性门槛拦截（无相关命中）
    correct_rejection_rate = round(sum(1 for p in neg if p["hits_delivered"] == 0) / max(1, len(neg)), 4)

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
        "correct_rejection_rate": correct_rejection_rate,
        "n_negative": len(neg),
    }

    return {
        "tenant_id": tenant_id,
        "kb_ids": kb_ids,
        "ks": ks,
        "retrieval_ks": RETRIEVAL_KS,
        "n_queries": len(per_query),
        "n_positive": len(pos),
        "n_negative": len(neg),
        "golden_version": golden.get("version"),
        "aggregated": aggregated,
        "per_query": per_query,
    }


async def seed_eval_corpus(db: Session, tenant_id: str = "default",
                            path: Path = CORPUS_PATH) -> dict:
    """CI 自包含评测：把 data/eval_corpus.json 入库为一个临时 KB，
    并以"每个文档的全部切片"作为该文档查询的 ground truth，返回黄金集。
    返回的 dict 含 '_kb_id' 便于 run_evaluation 指定范围。
    幂等：KB 已存在则复用，不再重复入库。"""
    if not path.exists():
        logger.warning("评测语料不存在: %s", path)
        return {"version": 1, "tenant_id": tenant_id, "items": [], "_kb_id": None}
    data = json.loads(path.read_text(encoding="utf-8"))
    ks = KnowledgeService(db)
    kb_name = data.get("kb_name", "CI 评测规范库")
    kb = db.query(KnowledgeBase).filter(
        KnowledgeBase.name == kb_name, KnowledgeBase.tenant_id == tenant_id).first()
    if not kb:
        kb = ks.create_kb(
            KnowledgeBaseCreate(name=kb_name, domain="standard",
                                description="CI 自包含评测库（请勿手工修改）"),
            tenant_id=tenant_id)
        db.flush()

    items: List[Dict] = []
    for d in data.get("documents", []):
        existing = db.query(Chunk).join(Document).filter(
            Document.kb_id == kb.id, Document.title == d["title"],
            Chunk.is_deleted.is_(False)).first()
        if existing:
            doc_id = existing.doc_id
        else:
            meta = DocumentMeta(
                title=d.get("title"), standard_code=d.get("standard_code", ""),
                standard_name=d.get("standard_name", ""))
            doc = await ks.ingest_text(kb.id, d["title"], d["content"], meta)
            doc_id = doc.id
        chunk_ids = [c.id for c in db.query(Chunk).filter(
            Chunk.doc_id == doc_id, Chunk.is_deleted.is_(False)).all()]
        for qi, q in enumerate(d.get("queries", [])):
            items.append({
                "id": f"ci-{d['id']}-{qi + 1}",
                "query": q,
                "expected_intent": d.get("intent", "spec_lookup"),
                "relevant_chunk_ids": chunk_ids,
                "note": f"CI 自包含: {d.get('title')}",
            })

    logger.info("CI 评测语料就绪 | kb=%s | 文档=%d | 查询=%d",
                kb.id, len(data.get("documents", [])), len(items))
    return {"version": 1, "tenant_id": tenant_id, "items": items, "_kb_id": kb.id}

