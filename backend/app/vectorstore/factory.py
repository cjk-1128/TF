"""向量库工厂：milvus / local 自动切换，Milvus 不可用时降级本地。"""
from __future__ import annotations

from functools import lru_cache

from app.core.config import settings
from app.core.logging import get_logger
from app.vectorstore.base import BaseVectorStore

logger = get_logger(__name__)


@lru_cache
def get_vector_store() -> BaseVectorStore:
    if settings.VECTOR_BACKEND == "milvus":
        try:
            from app.vectorstore.milvus_store import MilvusVectorStore
            return MilvusVectorStore()
        except Exception as e:  # noqa: BLE001
            logger.error("Milvus 初始化失败，降级为本地向量库: %s", e)
    from app.vectorstore.local_store import LocalVectorStore
    return LocalVectorStore()
