"""Stage0-Stage7 全链路测试。"""
from __future__ import annotations

import pytest

from app.core.constants import ConfidenceLevel, QueryIntent
from app.rag.stages import _rule_intent
from app.schemas.chat import ChatRequest
from app.schemas.knowledge import DocumentMeta
from app.services.chat_service import ChatService
from app.services.knowledge_service import KnowledgeService
from tests.conftest import SAMPLE_TEXT


@pytest.mark.parametrize("query,expected", [
    ("GB50204规定混凝土保护层厚度是多少", QueryIntent.SPEC_LOOKUP),
    ("墙面出现裂缝是什么原因造成的", QueryIntent.QUALITY_DIAGNOSIS),
    ("帮我编制一份深基坑开挖专项方案", QueryIntent.SCHEME_GENERATION),
    ("有没有类似工程的案例可以参考", QueryIntent.CASE_RETRIEVAL),
    ("你好", QueryIntent.CHITCHAT),
])
def test_intent_routing(query, expected):
    intent, conf = _rule_intent(query)
    assert intent == expected, f"{query} -> {intent}"
    assert 0 < conf <= 1.0


def test_chitchat_not_hijack_long_query():
    """"你好，混凝土养护要求"不应判为闲聊。"""
    intent, _ = _rule_intent("你好，请问混凝土养护时间的规范要求是多少")
    assert intent != QueryIntent.CHITCHAT


@pytest.fixture
async def kb_with_doc(db, sample_kb):
    svc = KnowledgeService(db)
    await svc.ingest_text(sample_kb.id, "混凝土验收规范测试样本", SAMPLE_TEXT,
                          DocumentMeta(standard_code="GB50204-2015", owner="张工"))
    db.commit()
    return sample_kb


@pytest.mark.asyncio
async def test_full_pipeline_with_citations(db, sample_kb):
    svc = KnowledgeService(db)
    doc = await svc.ingest_text(sample_kb.id, "混凝土验收规范样本", SAMPLE_TEXT,
                                DocumentMeta(standard_code="GB50204-2015", owner="张工"))
    db.commit()
    assert doc.status == "ready" and doc.chunk_count > 0

    res = await ChatService(db).chat(ChatRequest(
        query="C60混凝土养护时间不得少于多少天", kb_ids=[sample_kb.id]))
    db.commit()

    assert res.answer
    assert res.intent == QueryIntent.SPEC_LOOKUP.value
    assert res.citations, "必须返回引用来源"
    assert res.confidence > 0
    assert res.conversation_id and res.message_id
    # Stage 追踪完整
    stages = {t.stage for t in res.stage_traces}
    assert {"stage0", "stage1", "stage2", "stage3", "stage4",
            "stage5", "stage6", "stage7"} <= stages
    # 引用可追溯到源文档
    assert any(c.doc_id == doc.id for c in res.citations)


@pytest.mark.asyncio
async def test_no_context_returns_gap_hint(db, sample_kb):
    """零召回时必须明确提示知识库未覆盖，不得编造。"""
    res = await ChatService(db).chat(ChatRequest(
        query="量子纠缠在星际航行中的相位补偿算法参数", kb_ids=[sample_kb.id]))
    db.commit()
    assert res.confidence < 0.45 or "未" in res.answer
    if not res.citations:
        assert res.need_human_review


@pytest.mark.asyncio
async def test_chitchat_skips_retrieval(db):
    res = await ChatService(db).chat(ChatRequest(query="你好"))
    db.commit()
    assert res.intent == QueryIntent.CHITCHAT.value
    assert not res.citations
    assert res.need_human_review is False


@pytest.mark.asyncio
async def test_safety_query_forces_review(db, sample_kb):
    svc = KnowledgeService(db)
    await svc.ingest_text(sample_kb.id, "安全样本", SAMPLE_TEXT, DocumentMeta())
    db.commit()
    res = await ChatService(db).chat(ChatRequest(
        query="脚手架坍塌安全事故如何处理", kb_ids=[sample_kb.id]))
    db.commit()
    assert res.need_human_review, "安全类问题必须强制人工复核"
    assert "安全" in res.review_hint


@pytest.mark.asyncio
async def test_multi_turn_history(db, sample_kb):
    svc = KnowledgeService(db)
    await svc.ingest_text(sample_kb.id, "多轮样本", SAMPLE_TEXT, DocumentMeta())
    db.commit()
    cs = ChatService(db)
    r1 = await cs.chat(ChatRequest(query="混凝土养护时间要求", kb_ids=[sample_kb.id]))
    db.commit()
    r2 = await cs.chat(ChatRequest(query="那它拆模有什么要求", kb_ids=[sample_kb.id],
                                   conversation_id=r1.conversation_id))
    db.commit()
    assert r2.conversation_id == r1.conversation_id
    msgs = cs.list_messages(r1.conversation_id)
    assert len(msgs) == 4
    # 历史不应把当前问题算进去导致自引用
    assert "那它拆模有什么要求" not in (r2.rewritten_query or "").replace(r2.query, "")
