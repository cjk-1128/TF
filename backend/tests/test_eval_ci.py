"""CI 自包含检索回归测试（无需外部服务 / 知识库）。

流程：init_db -> 把 data/eval_corpus.json 入库为临时 KB ->
对语料生成的黄金集跑真实检索管线 -> 断言命中率 / 候选召回不退化。

真正验证"检索+重排+相关性门槛"整链路在 CI 中可复现，而非仅指标数学。
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import SessionLocal, init_db
from app.services.eval_service import run_evaluation, seed_eval_corpus


@pytest.fixture(scope="module")
def db():
    init_db()
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_ci_corpus_eval(db):
    golden = asyncio.run(seed_eval_corpus(db, tenant_id="default"))
    assert golden["items"], "语料未生成任何评测项"
    kb_id = golden.get("_kb_id")
    assert kb_id, "语料 KB 未创建"

    result = asyncio.run(
        run_evaluation(db, tenant_id="default", kb_ids=[kb_id], golden=golden))
    agg = result["aggregated"]

    print("\n[CI EVAL] n_queries=%d  hit_rate=%.3f  candR@20=%.3f  below_floor=%.3f"
          % (result["n_queries"], agg["hit_rate"],
             agg["candidate_recall@20"], agg["below_floor_rate"]))

    assert result["n_queries"] >= 8, "评测样本过少"
    # 候选召回（检索池诊断）必须高：证明混合检索能找到相关切片
    # （语料含 8 篇相近混凝土文档，会竞争交付前 6 条，故命中率阈值放宽）
    assert agg["candidate_recall@20"] >= 0.9, f"候选召回退化: {agg['candidate_recall@20']}"
    # 交付命中率：多数查询应在前 6 条命中自身文档切片
    assert agg["hit_rate"] >= 0.5, f"命中率退化: {agg['hit_rate']}"
    # 不应大面积误杀
    assert agg["below_floor_rate"] <= 0.5, f"地板拒答率过高: {agg['below_floor_rate']}"
