"""测试夹具：独立临时数据库与索引目录，互不污染。"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

_TMP = tempfile.mkdtemp(prefix="terraforge_test_")
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP}/test.db"
os.environ["LOCAL_VECTOR_DIR"] = f"{_TMP}/vs"
os.environ["UPLOAD_DIR"] = f"{_TMP}/uploads"
os.environ["LOG_DIR"] = f"{_TMP}/logs"
os.environ["VECTOR_BACKEND"] = "local"
os.environ["LLM_PROVIDER"] = "mock"
os.environ["EMBEDDING_PROVIDER"] = "hash"
os.environ["RERANK_PROVIDER"] = "rule"


@pytest.fixture(scope="session", autouse=True)
def _init():
    from app.db.session import init_db
    init_db()
    yield


@pytest.fixture
def db():
    from app.db.session import SessionLocal
    s = SessionLocal()
    try:
        yield s
        s.commit()
    finally:
        s.close()


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as c:
        yield c


@pytest.fixture
def sample_kb(db):
    from app.core.constants import KnowledgeDomain
    from app.schemas.knowledge import KnowledgeBaseCreate
    from app.services.knowledge_service import KnowledgeService
    import uuid
    svc = KnowledgeService(db)
    kb = svc.create_kb(KnowledgeBaseCreate(
        name=f"测试规范库-{uuid.uuid4().hex[:6]}",
        domain=KnowledgeDomain.STANDARD, owner="测试负责人"))
    db.commit()
    return kb


SAMPLE_TEXT = """# 混凝土结构工程施工质量验收规范 GB 50204-2015

## 7.4 混凝土养护

7.4.2 采用覆盖浇水养护的混凝土，其养护时间应符合下列规定：
采用硅酸盐水泥、普通硅酸盐水泥拌制的混凝土，养护时间不得少于7d；
抗渗混凝土、强度等级C60及以上的混凝土，养护时间不应少于14d；
后浇带混凝土的养护时间不应少于14d。

7.4.4 混凝土强度达到1.2N/mm²前，不得在其上踩踏、堆放物料或安装模板及支架。

## 8.2 位置和尺寸偏差

8.2.1 现浇结构位置和尺寸允许偏差：墙、柱、梁轴线位置允许偏差8mm；
表面平整度2m靠尺允许偏差8mm；层高标高允许偏差±10mm。
"""
