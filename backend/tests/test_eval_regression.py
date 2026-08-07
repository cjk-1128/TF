"""
Sprint 5 评测回归测试（pytest）
==============================
在后端运行环境内直接调用 run_evaluation，对黄金集跑真实检索管线，
断言检索质量未退化（Recall@K / MRR 不低于捕获基线 - 容差）。

运行：
    cd backend && python -m pytest tests/test_eval_regression.py -q
前置：
    - 后端依赖已安装（sqlalchemy / 向量与 BM25 索引可用）
    - 数据库中存在黄金集对应的切片（默认 default 租户 77 切片库）
若环境无法连接数据库，测试自动 skip，不阻塞 CI。

基线：backend/data/eval_baseline.json（由 verify_sprint5.py 在 VM 上捕获）
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

try:
    from app.db.session import SessionLocal
    from app.services.eval_service import run_evaluation
except Exception:  # noqa: BLE001
    pytest.skip("后端依赖不可用", allow_module_level=True)

BASELINE_PATH = Path(__file__).resolve().parents[1] / "data" / "eval_baseline.json"
TOL = 0.10  # 允许的绝对退化上限


def _load_baseline():
    if not BASELINE_PATH.exists():
        return None
    return json.loads(BASELINE_PATH.read_text(encoding="utf-8")).get("data", {}).get("aggregated")


@pytest.fixture(scope="module")
def baseline():
    return _load_baseline()


def test_eval_metrics_no_regression(baseline):
    """检索质量不低于基线 - 容差；命中率与地板率满足硬下限。"""
    if baseline is None:
        pytest.skip("未找到 eval_baseline.json，跳过回归断言")

    try:
        db = SessionLocal()
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"无法连接数据库: {e}")

    try:
        result = asyncio.run(run_evaluation(db, tenant_id="default"))
    finally:
        db.close()

    agg = result["aggregated"]
    assert agg["hit_rate"] >= 0.9, f"命中率过低: {agg['hit_rate']}"
    assert agg["below_floor_rate"] <= 0.1, f"地板拒答率过高: {agg['below_floor_rate']}"

    cur_r5 = agg["delivered_recall@k"]["5"]
    base_r5 = baseline["delivered_recall@k"]["5"]
    assert cur_r5 >= base_r5 - TOL, f"Recall@5 退化: {cur_r5} < {base_r5 - TOL}"

    cur_mrr = agg["delivered_mrr"]
    base_mrr = baseline["delivered_mrr"]
    assert cur_mrr >= base_mrr - TOL, f"MRR 退化: {cur_mrr} < {base_mrr - TOL}"

    cur_c20 = agg["candidate_recall@20"]
    assert cur_c20 >= 0.9, f"候选Recall@20 过低: {cur_c20}"


def test_eval_golden_nonempty():
    """黄金集非空且每条含 query 与相关 chunk。"""
    try:
        db = SessionLocal()
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"无法连接数据库: {e}")
    try:
        result = asyncio.run(run_evaluation(db, tenant_id="default"))
    finally:
        db.close()
    assert result["n_queries"] >= 10, "黄金集样本过少"
    for pq in result["per_query"]:
        assert pq["relevant_count"] > 0, f"{pq['id']} 缺少相关 chunk 标注"
