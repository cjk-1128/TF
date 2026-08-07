"""
Sprint 评测回归测试（pytest，CI 自包含）
========================================
不依赖 VM / 生产库：自动用临时 SQLite + mock 模式（hash 嵌入 / 本地 CrossEncoder
重排），把 data/eval_corpus.json 入库为独立 KB，并以"每个文档的全部切片"作为该文档
查询的 ground truth，跑真实检索管线 Stage1→Stage4，断言检索质量未退化。

运行：
    cd backend && python -m pytest tests/test_eval_regression.py -q
或（仓库根）：
    pytest backend/tests/test_eval_regression.py -q

判定口径：
  - 检索层召回命中率（candidate_hit_rate）：候选池中"含相关文档"的查询占比。
    这是最稳定的检索回归指标——只衡量混合检索是否找得到相关文档，不受
    Stage4 相关性地板策略（含 mock 模式下 LLM 缺失导致的 unknown 意图拒答）影响。
  - 候选召回@20：候选池覆盖度硬下限。
  - 交付层指标（Recall@5 / MRR）：若 data/eval_corpus_baseline.json 存在，则
    当前值不得低于基线 - 容差（TOL），用于检测渐进式退化。首次运行无基线时该
    部分自动 skip，可运行 capture_corpus_baseline.py 在 VM 上生成。
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

try:
    from app.db.session import SessionLocal
    from app.services.eval_service import run_evaluation, seed_eval_corpus
except Exception:  # noqa: BLE001
    pytest.skip("后端依赖不可用", allow_module_level=True)

CORPUS_BASELINE = Path(__file__).resolve().parents[1] / "data" / "eval_corpus_baseline.json"
TOL = 0.05  # 交付层指标允许的绝对退化上限（Recall@5 / MRR）


@pytest.fixture(scope="module")
def golden():
    db = SessionLocal()
    try:
        data = asyncio.run(seed_eval_corpus(db, tenant_id="default"))
    finally:
        db.close()
    assert data.get("_kb_id"), "CI 评测语料 KB 未创建"
    assert data.get("items"), "CI 黄金集为空"
    return data


def _run(db, golden):
    return asyncio.run(run_evaluation(
        db, tenant_id="default", kb_ids=[golden["_kb_id"]], golden=golden))


def test_ci_eval_retrieval_recall(golden):
    """检索层回归门禁：混合检索须能召回相关文档（候选池口径，稳定不被地板污染）。"""
    db = SessionLocal()
    try:
        result = _run(db, golden)
    finally:
        db.close()

    pos = [p for p in result["per_query"] if not p.get("negative")]
    cand_hit = sum(1 for p in pos if p["hits_candidates"] > 0) / max(1, len(pos))
    assert cand_hit >= 0.95, f"检索层召回命中率过低: {cand_hit}"

    agg = result["aggregated"]
    assert agg["candidate_recall@20"] >= 0.9, (
        f"候选召回@20 过低: {agg['candidate_recall@20']}")
    # 交付层软下限（即便无基线文件也能拦住严重回退）
    assert agg["hit_rate"] >= 0.5, f"交付命中率过低: {agg['hit_rate']}"


def test_ci_eval_no_regression_vs_baseline(golden):
    """交付层指标不低于捕获基线 - 容差。"""
    if not CORPUS_BASELINE.exists():
        pytest.skip("未找到 eval_corpus_baseline.json（首次运行请执行 capture_corpus_baseline.py 生成）")

    db = SessionLocal()
    try:
        result = _run(db, golden)
    finally:
        db.close()

    agg = result["aggregated"]
    kr = agg["delivered_recall@k"]
    base = json.loads(CORPUS_BASELINE.read_text(encoding="utf-8")).get("aggregated", {})
    base_r5 = base["delivered_recall@k"]["5"]
    base_mrr = base["delivered_mrr"]
    assert kr[5] >= round(base_r5 - TOL, 4), (
        f"Recall@5 退化: {kr[5]} < {base_r5 - TOL}")
    assert agg["delivered_mrr"] >= round(base_mrr - TOL, 4), (
        f"MRR 退化: {agg['delivered_mrr']} < {base_mrr - TOL}")


def test_ci_eval_golden_complete(golden):
    """每条 CI 黄金样本都应有相关 chunk 标注，且检索层能召回其相关文档。"""
    for it in golden["items"]:
        assert it["relevant_chunk_ids"], f"{it['id']} 缺少相关 chunk 标注"
    db = SessionLocal()
    try:
        result = _run(db, golden)
    finally:
        db.close()
    for pq in result["per_query"]:
        assert pq["hits_candidates"] > 0, (
            f"{pq['id']} 检索层未召回任何相关切片（query={pq['query']}）")
