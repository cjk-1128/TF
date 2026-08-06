"""LLM / Embedding / Reranker 工厂：按配置切换实现，单例缓存。"""
from __future__ import annotations

from functools import lru_cache

from app.core.config import settings
from app.core.logging import get_logger
from app.llm.base import BaseEmbedding, BaseLLM, BaseReranker

logger = get_logger(__name__)


@lru_cache
def get_llm() -> BaseLLM:
    if settings.LLM_PROVIDER == "openai_compatible" and settings.LLM_API_KEY:
        from app.llm.openai_client import OpenAICompatibleLLM
        logger.info("LLM 使用 OpenAI 兼容接口 | model=%s", settings.LLM_MODEL)
        return OpenAICompatibleLLM()
    from app.llm.local_impl import MockLLM
    logger.warning("LLM 使用内置抽取式实现（未配置 LLM_API_KEY）")
    return MockLLM()


@lru_cache
def get_embedding() -> BaseEmbedding:
    if settings.EMBEDDING_PROVIDER == "openai_compatible" and settings.EMBEDDING_API_KEY:
        from app.llm.openai_client import OpenAICompatibleEmbedding
        logger.info("Embedding 使用 OpenAI 兼容接口 | model=%s", settings.EMBEDDING_MODEL)
        return OpenAICompatibleEmbedding()
    from app.llm.local_impl import HashEmbedding
    logger.warning("Embedding 使用内置 Hash 实现（未配置 EMBEDDING_API_KEY）")
    return HashEmbedding()


@lru_cache
def get_reranker() -> BaseReranker:
    if settings.RERANK_PROVIDER == "cross_encoder_api" and settings.RERANK_BASE_URL:
        from app.llm.openai_client import CrossEncoderAPIReranker
        logger.info("Rerank 使用远程 CrossEncoder | model=%s", settings.RERANK_MODEL)
        return CrossEncoderAPIReranker()
    from app.llm.local_impl import RuleReranker
    logger.info("Rerank 使用内置规则重排器")
    return RuleReranker()
