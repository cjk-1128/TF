"""
检索评测指标（Sprint 5 评测体系）
=================================
纯函数、零依赖。用于评测 RAG 检索/重排质量：
  - Recall@K   : 前 K 条结果中命中相关文档的比例（按查询平均）
  - MRR        : 首个相关结果排名的倒数均值（Mean Reciprocal Rank）
  - NDCG@K     : 归一化折损累计增益（二元相关性）

所有函数接受：
  relevant : 相关 chunk_id 列表（ground truth）
  ranked   : 模型返回的 chunk_id 列表（按相关性降序）
"""
from __future__ import annotations

from typing import Dict, List, Optional


def recall_at_k(relevant: List[str], ranked: List[str], k: int) -> float:
    """前 k 条里命中的相关 chunk 占全部相关 chunk 的比例 [0,1]。"""
    if not relevant:
        return 0.0
    rel_set = set(relevant)
    top = ranked[:k]
    hits = sum(1 for cid in top if cid in rel_set)
    return hits / len(relevant)


def mrr_at_k(relevant: List[str], ranked: List[str], k: Optional[int] = None) -> float:
    """首个相关结果的排名倒数；若无命中则为 0。"""
    rel_set = set(relevant)
    limit = k if k else len(ranked)
    for i, cid in enumerate(ranked[:limit], start=1):
        if cid in rel_set:
            return 1.0 / i
    return 0.0


def _discounted_gain(ids: List[str], relevant: set, k: int) -> float:
    """二元增益的 DCG：gain=1 命中，否则 0；位置折扣 1/log2(i+2)。"""
    s = 0.0
    for i, cid in enumerate(ids[:k]):
        if cid in relevant:
            s += 1.0 / (i + 2)  # 等价于 1/log2(i+2)
    return s


def ndcg_at_k(relevant: List[str], ranked: List[str], k: int) -> float:
    """归一化 DCG [0,1]；理想序为所有相关 chunk 排在最前。"""
    if not relevant:
        return 0.0
    rel_set = set(relevant)
    dcg = _discounted_gain(ranked, rel_set, k)
    idcg = _discounted_gain(list(rel_set), rel_set, k)  # 理想排序就是相关项本身
    return dcg / idcg if idcg > 0 else 0.0


def evaluate_ranked(relevant: List[str], ranked: List[str],
                    ks: List[int]) -> Dict[str, object]:
    """对单次查询计算完整指标集合。"""
    return {
        "recall": {k: round(recall_at_k(relevant, ranked, k), 4) for k in ks},
        "mrr": round(mrr_at_k(relevant, ranked), 4),
        "ndcg": {k: round(ndcg_at_k(relevant, ranked, k), 4) for k in ks},
    }


def aggregate(per_query: List[Dict], ks: List[int]) -> Dict[str, object]:
    """对多查询结果做均值聚合。per_query 每项须含 'metrics' 字段
    （来自 evaluate_ranked）。"""
    n = max(1, len(per_query))
    agg: Dict[str, object] = {"recall": {}, "ndcg": {}, "mrr": 0.0}
    for k in ks:
        agg["recall"][k] = round(
            sum(p["metrics"]["recall"][k] for p in per_query) / n, 4)
        agg["ndcg"][k] = round(
            sum(p["metrics"]["ndcg"][k] for p in per_query) / n, 4)
    agg["mrr"] = round(sum(p["metrics"]["mrr"] for p in per_query) / n, 4)
    return agg
