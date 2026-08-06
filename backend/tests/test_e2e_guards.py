"""E2E 守卫测试：锁定三类已修复的线上问题。

1. 无关问题必须触发"无证据不作答"（相关性地板或零召回），不得强行编造答案。
2. 闲聊类问题不得进入"知识缺口"（知识治理闭环污染）。
3. "质量问题描述 + 案例参考"的意图冲突须判为案例检索，而非质量分析。
"""
from __future__ import annotations

import pytest

from app.core.constants import QueryIntent
from app.llm.local_impl import RuleReranker
from app.models.governance import QueryLog
from app.rag import prompts
from app.rag.stages import _rule_intent, stage4_rerank, stage6_generate
from app.rag.state import RAGState
from app.retrieval.hybrid import Candidate
from app.schemas.chat import ChatRequest
from app.schemas.knowledge import DocumentMeta
from app.services.chat_service import ChatService
from app.services.governance_service import GovernanceService
from app.services.knowledge_service import KnowledgeService
from tests.conftest import SAMPLE_TEXT


# ---------------------------------------------------------------
# 守卫一：无证据不作答（相关性地板 / 零召回）
# ---------------------------------------------------------------
@pytest.mark.asyncio
async def test_unrelated_query_no_forced_answer(db, sample_kb):
    """与工程无关的问题不得返回高置信度答案与引用（回归：曾返回 conf 0.65 + 4 引用）。"""
    svc = KnowledgeService(db)
    await svc.ingest_text(sample_kb.id, "规范样本", SAMPLE_TEXT,
                          DocumentMeta(standard_code="GB50204-2015", owner="张工"))
    db.commit()

    res = await ChatService(db).chat(ChatRequest(
        query="三文鱼刺身的冷藏保存温度应该设多少度", kb_ids=[sample_kb.id]))
    db.commit()

    assert not res.citations, "无关问题不应返回任何引用"
    assert res.confidence < 0.45, "无关问题可信度应低于地板阈值"
    assert res.need_human_review is True
    assert ("门槛" in res.answer or "未检索" in res.answer
            or "未提供" in res.answer), "应给出明确的缺口提示"


@pytest.mark.asyncio
async def test_relevant_query_passes_floor(db, sample_kb):
    """真正命中的工程问题应通过地板并给出有引用的答案。"""
    svc = KnowledgeService(db)
    await svc.ingest_text(sample_kb.id, "规范样本", SAMPLE_TEXT,
                          DocumentMeta(standard_code="GB50204-2015", owner="张工"))
    db.commit()

    res = await ChatService(db).chat(ChatRequest(
        query="C60混凝土养护时间不得少于多少天", kb_ids=[sample_kb.id]))
    db.commit()

    assert res.below_relevance_floor is False
    assert res.citations, "应返回命中引用"
    assert res.confidence > 0


@pytest.mark.asyncio
async def test_relevance_floor_blocks_weak_candidates():
    """检索到少量内容但相关性不足时，必须被地板拦截（top1 擦边 + 其余断崖）。

    直接对 stage4 注入低质候选：查询为食品话题，候选为工程条文，
    两者无词面重叠，重排后 final_score 远低于门槛且支撑数不足。
    """
    query = "三文鱼刺身冷藏保存温度应该设多少度"
    chunks = [
        "混凝土浇筑后应及时进行保湿养护，养护时间不得少于 14 天。",
        "模板拆除时混凝土强度应达到设计强度的 75% 以上方可拆模。",
        "钢筋保护层厚度允许偏差为 +5mm，-3mm，应符合设计要求。",
        "基坑开挖应遵循分层分段、随挖随撑的原则组织施工。",
        "脚手架立杆基础应夯实并设置扫地杆与垫板。",
        "防水混凝土的抗渗等级应根据埋置深度确定并满足设计要求。",
    ]
    state = RAGState(
        query=query,
        candidates=[Candidate(chunk_id=f"c{i}", content=t,
                              meta={"doc_id": "d1", "doc_title": "规范", "domain": "standard"})
                    for i, t in enumerate(chunks)],
    )
    out = await stage4_rerank(state)

    assert out.below_relevance_floor is True, "低质候选应触发相关性地板"
    assert out.reranked == [], "被拦截时不应有通过重排的候选"
    assert len(out.rejected) == len(chunks), "被拦截候选应保留供排查"


@pytest.mark.asyncio
async def test_below_floor_yields_gap_hint(db):
    """below_relevance_floor 时 stage6 必须给出专属的"相关性不足"缺口提示。"""
    state = RAGState(query="某无关问题", intent=QueryIntent.SPEC_LOOKUP,
                     below_relevance_floor=True)
    out = await stage6_generate(state, db)
    assert out.answer == prompts.BELOW_FLOOR_ANSWER
    assert out.citations == []


# ---------------------------------------------------------------
# 守卫二：闲聊不得污染知识缺口
# ---------------------------------------------------------------
def test_chitchat_excluded_from_knowledge_gaps(db):
    chitchat = QueryLog(
        query="你好，你是谁？", intent=QueryIntent.CHITCHAT.value,
        hit_count=0, confidence=1.0, answered=True)
    real_gap = QueryLog(
        query="装配式钢结构的防火涂层厚度要求", intent=QueryIntent.SPEC_LOOKUP.value,
        hit_count=0, confidence=0.0, answered=False)
    db.add_all([chitchat, real_gap])
    db.commit()

    gaps = GovernanceService(db).knowledge_gaps(days=30, limit=20)
    gap_queries = {g.query for g in gaps}

    assert "你好，你是谁？" not in gap_queries, "闲聊不应进入知识缺口"
    assert "装配式钢结构的防火涂层厚度要求" in gap_queries, "真实零召回缺口应保留"


# ---------------------------------------------------------------
# 守卫三：质量描述 + 案例参考 → 案例检索
# ---------------------------------------------------------------
def test_case_retrieval_wins_quality_tie():
    """"混凝土裂缝的案例可以参考"同时命中质量与案例关键词，须判为案例检索。"""
    intent, conf = _rule_intent("混凝土裂缝的案例可以参考")
    assert intent == QueryIntent.CASE_RETRIEVAL, f"应判为案例检索，实际 {intent}"
    assert conf > 0.7
