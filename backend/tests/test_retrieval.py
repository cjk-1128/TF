"""检索链路测试：向量库、BM25、混合融合、重排。"""
from __future__ import annotations

import pytest

from app.llm.local_impl import HashEmbedding, RuleReranker
from app.vectorstore.local_store import LocalVectorStore
from app.vectorstore.base import VectorRecord


@pytest.mark.asyncio
async def test_hash_embedding_similarity():
    e = HashEmbedding(dim=256)
    vs = await e.embed_texts(["混凝土养护时间不得少于7天",
                              "混凝土养护时间要求",
                              "脚手架连墙件设置规定"])
    import numpy as np
    a, b, c = (np.array(v) for v in vs)
    assert float(a @ b) > float(a @ c), "同主题相似度应高于跨主题"


@pytest.mark.asyncio
async def test_local_vector_store(tmp_path):
    store = LocalVectorStore(path=str(tmp_path))
    e = HashEmbedding(dim=128)
    texts = ["混凝土养护不少于7d", "基坑监测报警值30mm", "脚手架立杆间距要求"]
    vecs = await e.embed_texts(texts)
    store.upsert([VectorRecord(id=f"c{i}", vector=v, doc_id="d1", kb_id="k1",
                               domain="standard", content=t)
                  for i, (t, v) in enumerate(zip(texts, vecs))])
    assert store.count() == 3

    q = await e.embed_query("混凝土养护时间")
    hits = store.search(q, top_k=2)
    assert hits and hits[0].content.find("养护") >= 0

    # 过滤生效
    assert store.search(q, top_k=3, kb_ids=["not-exist"]) == []
    assert len(store.search(q, top_k=3, domains=["standard"])) == 3

    assert store.delete_by_doc("d1") == 3
    assert store.count() == 0


@pytest.mark.asyncio
async def test_rule_reranker_ordering():
    r = RuleReranker()
    docs = ["脚手架立杆纵距不应大于2m",
            "混凝土养护时间不得少于7d，抗渗混凝土不少于14d",
            "地基承载力检验数量每单位工程不应少于3点"]
    pairs = await r.rerank("混凝土养护多少天", docs, top_n=3)
    assert pairs[0][0] == 1, "养护相关文档应排第一"
    assert pairs[0][1] >= pairs[-1][1]


@pytest.mark.asyncio
async def test_bm25_index(tmp_path):
    from app.retrieval.bm25_index import BM25Index
    idx = BM25Index(path=str(tmp_path))
    idx.add([
        ("c1", "混凝土养护时间不得少于7d", {"doc_id": "d1", "kb_id": "k1", "domain": "standard"}),
        ("c2", "基坑支护变形监测报警值30mm", {"doc_id": "d2", "kb_id": "k1", "domain": "case"}),
    ])
    assert idx.count() == 2
    res = idx.search("混凝土养护", top_k=2)
    assert res and res[0][0] == "c1"
    assert idx.search("混凝土养护", top_k=2, domains=["case"]) == []
    assert idx.delete_by_doc("d1") == 1
