"""API 接口测试。"""
from __future__ import annotations

import io
import json

import pytest

from tests.conftest import SAMPLE_TEXT


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert "X-Trace-Id" in r.headers


def test_kb_crud(client):
    r = client.post("/api/v1/knowledge/kb", json={
        "name": "API测试知识库", "domain": "standard",
        "description": "接口测试", "owner": "测试员"})
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == 0
    kb_id = body["data"]["id"]
    assert body["data"]["domain_label"] == "建设规范库"

    # 重名拒绝
    assert client.post("/api/v1/knowledge/kb", json={
        "name": "API测试知识库", "domain": "standard"}).status_code == 422

    assert client.get("/api/v1/knowledge/kb").json()["data"]
    assert client.get(f"/api/v1/knowledge/kb/{kb_id}").json()["data"]["id"] == kb_id

    r = client.put(f"/api/v1/knowledge/kb/{kb_id}", json={"owner": "新负责人"})
    assert r.json()["data"]["owner"] == "新负责人"

    assert client.delete(f"/api/v1/knowledge/kb/{kb_id}").json()["code"] == 0
    assert client.get(f"/api/v1/knowledge/kb/{kb_id}").status_code == 404


def test_document_lifecycle(client):
    kb_id = client.post("/api/v1/knowledge/kb", json={
        "name": "文档生命周期库", "domain": "standard"}).json()["data"]["id"]

    r = client.post("/api/v1/knowledge/documents/text", json={
        "kb_id": kb_id, "title": "验收规范样本", "content": SAMPLE_TEXT,
        "meta": {"standard_code": "GB50204-2015", "owner": "张工",
                 "discipline": "concrete"}})
    assert r.status_code == 200
    doc = r.json()["data"]
    assert doc["status"] == "ready" and doc["chunk_count"] > 0
    doc_id = doc["id"]

    chunks = client.get(f"/api/v1/knowledge/documents/{doc_id}/chunks").json()["data"]
    assert chunks["total"] > 0
    assert any(c["section_path"] for c in chunks["items"])

    r = client.put(f"/api/v1/knowledge/documents/{doc_id}",
                   json={"governance_status": "need_update", "owner": "李工"})
    assert r.json()["data"]["governance_status"] == "need_update"

    lst = client.get("/api/v1/knowledge/documents",
                     params={"kb_id": kb_id, "governance_status": "need_update"}).json()
    assert lst["data"]["total"] == 1

    stats = client.get("/api/v1/knowledge/stats").json()["data"]
    assert stats["chunk_count"] > 0 and stats["vector_count"] > 0

    assert client.delete(f"/api/v1/knowledge/documents/{doc_id}").json()["code"] == 0


def test_upload_file(client):
    kb_id = client.post("/api/v1/knowledge/kb", json={
        "name": "上传测试库", "domain": "enterprise"}).json()["data"]["id"]
    files = {"files": ("test_sop.md", io.BytesIO(SAMPLE_TEXT.encode()), "text/markdown")}
    r = client.post("/api/v1/knowledge/documents/upload",
                    data={"kb_id": kb_id, "meta": json.dumps({"owner": "工程部"})},
                    files=files)
    assert r.status_code == 200
    docs = r.json()["data"]
    assert len(docs) == 1 and docs[0]["status"] == "ready"


def test_unsupported_file_type(client):
    kb_id = client.post("/api/v1/knowledge/kb", json={
        "name": "类型校验库", "domain": "case"}).json()["data"]["id"]
    files = {"files": ("bad.exe", io.BytesIO(b"MZ"), "application/octet-stream")}
    r = client.post("/api/v1/knowledge/documents/upload",
                    data={"kb_id": kb_id, "meta": "{}"}, files=files)
    assert r.status_code == 422


def test_chat_and_search(client):
    kb_id = client.post("/api/v1/knowledge/kb", json={
        "name": "问答测试库", "domain": "standard"}).json()["data"]["id"]
    client.post("/api/v1/knowledge/documents/text", json={
        "kb_id": kb_id, "title": "养护规范", "content": SAMPLE_TEXT,
        "meta": {"standard_code": "GB50204-2015"}})

    r = client.post("/api/v1/rag/chat", json={
        "query": "混凝土养护时间不得少于多少天", "kb_ids": [kb_id]})
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["answer"] and data["citations"]
    assert data["intent"] == "spec_lookup"
    assert len(data["stage_traces"]) >= 8

    # 反馈
    assert client.post("/api/v1/rag/feedback", json={
        "message_id": data["message_id"], "rating": 1}).json()["code"] == 0

    # 会话消息
    msgs = client.get(f"/api/v1/rag/conversations/{data['conversation_id']}/messages").json()
    assert len(msgs["data"]) == 2

    # 纯检索
    s = client.post("/api/v1/rag/search", json={
        "query": "养护时间", "kb_ids": [kb_id], "top_k": 3}).json()
    assert s["data"] and s["data"][0]["final_score"] > 0


def test_chat_stream(client):
    kb_id = client.post("/api/v1/knowledge/kb", json={
        "name": "流式测试库", "domain": "standard"}).json()["data"]["id"]
    client.post("/api/v1/knowledge/documents/text", json={
        "kb_id": kb_id, "title": "流式样本", "content": SAMPLE_TEXT, "meta": {}})
    with client.stream("POST", "/api/v1/rag/chat/stream",
                       json={"query": "养护要求", "kb_ids": [kb_id]}) as r:
        assert r.status_code == 200
        body = "".join(r.iter_text())
    assert "event: meta" in body and "event: delta" in body and "event: done" in body


def test_governance_apis(client):
    kb_id = client.post("/api/v1/knowledge/kb", json={
        "name": "治理测试库", "domain": "standard"}).json()["data"]["id"]
    client.post("/api/v1/knowledge/documents/text", json={
        "kb_id": kb_id, "title": "无负责人文档", "content": SAMPLE_TEXT, "meta": {}})

    report = client.get("/api/v1/governance/health-report",
                        params={"kb_id": kb_id}).json()["data"]
    assert report["total_docs"] >= 1
    assert any(i["issue_type"] == "no_owner" for i in report["issues"])

    gen = client.post("/api/v1/governance/tasks/auto-generate",
                      params={"kb_id": kb_id, "assignee": "维护员"}).json()
    assert gen["data"]

    t = client.post("/api/v1/governance/tasks", json={
        "task_type": "gap_fill", "title": "补充防水规范", "priority": "high",
        "assignee": "赵工", "kb_id": kb_id}).json()["data"]
    upd = client.put(f"/api/v1/governance/tasks/{t['id']}",
                     json={"status": "processing"}).json()["data"]
    assert upd["status"] == "processing"

    assert client.get("/api/v1/governance/tasks",
                      params={"kb_id": kb_id}).json()["data"]["total"] >= 1
    assert client.get("/api/v1/governance/operation-report",
                      params={"days": 7}).status_code == 200
    assert client.get("/api/v1/governance/knowledge-gaps").status_code == 200


def test_404_shape(client):
    r = client.get("/api/v1/knowledge/kb/not-exist-id")
    assert r.status_code == 404
    b = r.json()
    assert b["code"] == 40400 and b["trace_id"]
