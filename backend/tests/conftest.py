"""CI 自包含评测公共夹具。
================================
目标：让 pytest 无需 VM / 生产库即可运行评测回归，且确定性强。

- 在 import app 之前强制使用临时 SQLite（不依赖外部数据库）
- 强制 mock 模式（hash 嵌入 + 本地 CrossEncoder 重排 + mock LLM），无需任何 API Key
- 关闭定时巡检，避免测试期间后台协程干扰
- 会话级 autouse fixture：初始化 schema 并 seed 默认管理员
"""
from __future__ import annotations

import os
import tempfile

# ---- 必须在 import app 之前设置环境变量 ----
if not os.environ.get("DATABASE_URL"):
    _tmp = tempfile.NamedTemporaryFile(
        suffix=".db", delete=False, prefix="tf_ci_eval_")
    os.environ["DATABASE_URL"] = f"sqlite:///{_tmp.name}"

os.environ.setdefault("LLM_PROVIDER", "mock")
os.environ.setdefault("EMBEDDING_PROVIDER", "hash")
os.environ.setdefault("RERANK_PROVIDER", "cross_encoder_local")
os.environ.setdefault("REDIS_ENABLED", "False")
os.environ.setdefault("QUALITY_INSPECT_ENABLED", "False")

import pytest


@pytest.fixture(scope="session", autouse=True)
def _app_db():
    """会话级：初始化数据库 schema（迁移优先，失败回退 create_all）。"""
    from app.db.session import init_db
    init_db()
    yield
