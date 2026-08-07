"""CI / 测试环境隔离配置。

在导入任何 app 模块之前设置环境变量，确保测试使用独立的临时
SQLite 数据库与向量/BM25 索引目录（不污染开发库），并以 mock 模式
（无需任何 API Key）跑通全链路。

注意：本文件必须在其他 app 导入之前被导入；pytest 会优先加载 conftest。
"""
from __future__ import annotations

import os
import tempfile

_TMP = tempfile.mkdtemp(prefix="tf_eval_ci_")
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_TMP}/terraforge_ci.db")
os.environ.setdefault("LOCAL_VECTOR_DIR", f"{_TMP}/vectorstore")
os.environ.setdefault("UPLOAD_DIR", f"{_TMP}/uploads")
os.environ.setdefault("LOG_DIR", f"{_TMP}/logs")
os.environ.setdefault("REDIS_ENABLED", "0")
os.environ.setdefault("LLM_PROVIDER", "mock")
os.environ.setdefault("EMBEDDING_PROVIDER", "hash")
os.environ.setdefault("RERANK_PROVIDER", "cross_encoder_local")
os.environ.setdefault("INTENT_AGENT_ENABLED", "1")
os.environ.setdefault("INTENT_OUT_OF_SCOPE", "1")
os.environ.setdefault("RBAC_ENABLED", "1")
os.environ.setdefault("BOOTSTRAP_API_KEY", "tf-ci-test-key")
