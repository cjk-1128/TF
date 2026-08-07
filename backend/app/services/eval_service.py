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
BASELINE_PATH = Path(__file__).resolve().parents[2] / "data" / "eval_baseline.json"
DELIVERED_KS = [1, 3, 5]        # 重排后进入上下文的条数上限（RERANK_TOP_N=6）
RETRIEVAL_KS = [1, 3, 5, 10, 20]  # 候选池诊断口径

# 趋势/回归判定：核心指标低于基线超过该容差判为 regressed，高出则 improved
REGRESSION_TOLERANCE = 0.02
TREND_METRICS = ["recall_at_5", "ndcg_at_5", "mrr", "hit_rate",
                 "correct_rejection_rate"]


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



# ======================================================================
# Sprint7：评测趋势持久化 + 基线对比 + 回归检测
# ======================================================================
from datetime import datetime  # noqa: E402
from app.models.eval_run import EvalRun  # noqa: E402


def load_baseline() -> dict:
    """读取基线聚合指标（eval_baseline.json 的 data.aggregated）。缺失返回空。"""
    if not BASELINE_PATH.exists():
        return {}
    try:
        raw = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
        return (raw.get("data") or {}).get("aggregated", {}) or {}
    except Exception:  # noqa: BLE001
        logger.warning("基线文件解析失败：%s", BASELINE_PATH)
        return {}


def _flat_metrics(aggregated: dict) -> Dict[str, float]:
    """把嵌套聚合指标扁平化为趋势用的核心标量。"""
    rc = aggregated.get("delivered_recall@k", {}) or {}
    nd = aggregated.get("delivered_ndcg@k", {}) or {}

    def _g(d: dict, k) -> float:
        # 兼容 int / str 两种键
        return float(d.get(k, d.get(str(k), 0.0)) or 0.0)

    return {
        "recall_at_1": _g(rc, 1),
        "recall_at_3": _g(rc, 3),
        "recall_at_5": _g(rc, 5),
        "ndcg_at_5": _g(nd, 5),
        "mrr": float(aggregated.get("delivered_mrr", 0.0) or 0.0),
        "hit_rate": float(aggregated.get("hit_rate", 0.0) or 0.0),
        "full_hit_rate": float(aggregated.get("full_hit_rate", 0.0) or 0.0),
        "below_floor_rate": float(aggregated.get("below_floor_rate", 0.0) or 0.0),
        "correct_rejection_rate": float(aggregated.get("correct_rejection_rate", 0.0) or 0.0),
        "candidate_recall_at_20": float(aggregated.get("candidate_recall@20", 0.0) or 0.0),
    }


def compute_baseline_delta(aggregated: dict,
                            baseline: Optional[dict] = None) -> Dict[str, float]:
    """当前聚合指标相对基线的差值（正=更好；correct_rejection 同向）。"""
    baseline = baseline if baseline is not None else load_baseline()
    if not baseline:
        return {}
    cur = _flat_metrics(aggregated)
    base = _flat_metrics(baseline)
    return {m: round(cur[m] - base[m], 4) for m in TREND_METRICS if m in cur and m in base}


def classify_status(delta: Dict[str, float]) -> str:
    """根据核心指标差值判定 improved / regressed / ok。
    任一核心指标跌破容差 → regressed；否则若有明显提升 → improved；其余 ok。"""
    if not delta:
        return "ok"
    if any(v < -REGRESSION_TOLERANCE for v in delta.values()):
        return "regressed"
    if any(v > REGRESSION_TOLERANCE for v in delta.values()):
        return "improved"
    return "ok"


def _slim_per_query(per_query: List[dict]) -> List[dict]:
    """趋势快照只保留逐题的关键字段，剔除超长 ranked_ids。"""
    slim = []
    for p in per_query:
        dm = p.get("delivered_metrics", {})
        slim.append({
            "id": p.get("id"),
            "query": p.get("query"),
            "expected_intent": p.get("expected_intent"),
            "intent": p.get("intent"),
            "negative": p.get("negative"),
            "below_floor": p.get("below_floor"),
            "hits_delivered": p.get("hits_delivered"),
            "relevant_count": p.get("relevant_count"),
            "recall@5": (dm.get("recall", {}) or {}).get(5, (dm.get("recall", {}) or {}).get("5")),
            "mrr": dm.get("mrr"),
        })
    return slim


def persist_eval_run(db: Session, result: dict, *, tenant_id: str = "default",
                      source: str = "api", note: str = "",
                      duration_ms: int = 0) -> EvalRun:
    """把一次评测结果落库为趋势快照，并计算相对基线的状态。"""
    aggregated = result.get("aggregated", {}) or {}
    flat = _flat_metrics(aggregated)
    delta = compute_baseline_delta(aggregated)
    status = classify_status(delta)

    run = EvalRun(
        tenant_id=tenant_id,
        kb_ids=result.get("kb_ids", []),
        golden_version=result.get("golden_version") or 1,
        n_queries=result.get("n_queries", 0),
        n_positive=result.get("n_positive", 0),
        n_negative=result.get("n_negative", 0),
        aggregated=aggregated,
        per_query=_slim_per_query(result.get("per_query", [])),
        baseline_delta=delta,
        status=status,
        source=source,
        duration_ms=duration_ms,
        note=note[:255],
        created_at=datetime.utcnow(),
        **flat,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    logger.info("评测快照落库 | id=%s | status=%s | recall@5=%.4f | mrr=%.4f",
                run.id, status, flat["recall_at_5"], flat["mrr"])
    return run


def list_eval_runs(db: Session, tenant_id: str = "default",
                    limit: int = 50, offset: int = 0):
    """按时间倒序列出评测快照。返回 (items, total)。"""
    q = db.query(EvalRun).filter(EvalRun.tenant_id == tenant_id)
    total = q.count()
    items = (q.order_by(EvalRun.created_at.desc())
             .offset(offset).limit(limit).all())
    return items, total


def get_eval_run(db: Session, run_id: str) -> Optional[EvalRun]:
    return db.query(EvalRun).filter(EvalRun.id == run_id).first()


def delete_eval_run(db: Session, run_id: str) -> bool:
    run = get_eval_run(db, run_id)
    if not run:
        return False
    db.delete(run)
    db.commit()
    return True


def build_trend(db: Session, tenant_id: str = "default", limit: int = 30) -> dict:
    """构建趋势序列（时间正序），含基线、最新值、首末差值与回归/改进计数。"""
    runs, _ = list_eval_runs(db, tenant_id=tenant_id, limit=limit, offset=0)
    runs = list(reversed(runs))  # 时间正序，便于画曲线
    points = [{
        "id": r.id,
        "created_at": r.created_at,
        "recall_at_5": r.recall_at_5,
        "ndcg_at_5": r.ndcg_at_5,
        "mrr": r.mrr,
        "hit_rate": r.hit_rate,
        "correct_rejection_rate": r.correct_rejection_rate,
        "status": r.status,
        "source": r.source,
        "note": r.note or "",
    } for r in runs]

    baseline = _flat_metrics(load_baseline()) if load_baseline() else {}
    baseline = {m: baseline.get(m, 0.0) for m in TREND_METRICS} if baseline else {}

    latest, first_to_latest_delta = {}, {}
    if runs:
        last = runs[-1]
        latest = {m: getattr(last, m) for m in TREND_METRICS}
        if len(runs) >= 2:
            first = runs[0]
            first_to_latest_delta = {
                m: round(getattr(last, m) - getattr(first, m), 4) for m in TREND_METRICS}

    return {
        "points": points,
        "count": len(points),
        "baseline": baseline,
        "latest": latest,
        "first_to_latest_delta": first_to_latest_delta,
        "regressed_count": sum(1 for r in runs if r.status == "regressed"),
        "improved_count": sum(1 for r in runs if r.status == "improved"),
    }
