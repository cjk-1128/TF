"""检索评测指标单元测试（纯函数，无需数据库，CI 必跑）。"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.metrics import (aggregate, evaluate_ranked, mrr_at_k, ndcg_at_k,
                              recall_at_k)


def test_recall_at_k_basic():
    rel = ["a", "b", "c"]
    ranked = ["x", "a", "b", "c", "y"]
    assert recall_at_k(rel, ranked, 1) == 0.0          # 前1条未命中
    assert recall_at_k(rel, ranked, 3) == pytest.approx(2 / 3)  # 前3命中 a,b
    assert recall_at_k(rel, ranked, 5) == 1.0          # 全命中


def test_recall_at_k_empty_relevant():
    assert recall_at_k([], ["a", "b"], 5) == 0.0


def test_mrr_at_k():
    rel = ["a", "b"]
    assert mrr_at_k(rel, ["x", "a", "b"], 5) == 0.5     # 第2位命中
    assert mrr_at_k(rel, ["a", "x", "b"], 5) == 1.0     # 第1位命中
    assert mrr_at_k(rel, ["x", "y", "z"], 5) == 0.0     # 无命中


def test_ndcg_at_k_ideal_first():
    rel = ["a", "b"]
    # 理想序：相关项全在最前 -> NDCG=1
    assert ndcg_at_k(rel, ["a", "b", "x"], 3) == pytest.approx(1.0, abs=1e-6)


def test_ndcg_at_k_worse_than_ideal():
    rel = ["a", "b"]
    v = ndcg_at_k(rel, ["x", "a", "b"], 3)
    assert 0.0 < v < 1.0


def test_evaluate_ranked_structure():
    rel = ["a", "b", "c"]
    ranked = ["a", "b", "c"]
    out = evaluate_ranked(rel, ranked, [1, 3, 5])
    assert set(out.keys()) == {"recall", "mrr", "ndcg"}
    assert out["recall"][1] == pytest.approx(1 / 3, abs=1e-3)  # 指标四舍五入至 4 位
    assert out["mrr"] == 1.0
    assert out["ndcg"][1] == pytest.approx(1.0, abs=1e-6)


def test_aggregate_mean():
    per = [
        {"metrics": evaluate_ranked(["a"], ["a"], [1, 3])},
        {"metrics": evaluate_ranked(["a"], ["x", "a"], [1, 3])},
    ]
    agg = aggregate(per, [1, 3])
    # 第1题 R@1=1，第2题 R@1=0 -> 均值 0.5
    assert agg["recall"][1] == pytest.approx(0.5)
    assert agg["mrr"] == pytest.approx(0.75)  # 1.0 与 0.5 均值
