"""LLM / Embedding / Reranker 工厂：按配置切换实现，单例缓存。"""
from __future__ import annotations

import time
from functools import lru_cache
from typing import List

from app.core import prom_metrics as app_metrics
from app.core.config import settings
from app.core.logging import get_logger
from app.llm.base import BaseEmbedding, BaseLLM, BaseReranker

logger = get_logger(__name__)


@lru_cache
def get_llm() -> BaseLLM:
    if settings.LLM_PROVIDER == "openai_compatible" and settings.LLM_API_KEY:
        from app.llm.openai_client import OpenAICompatibleLLM
        logger.info("LLM 使用 OpenAI 兼容接口 | model=%s", settings.LLM_MODEL)
        inner = OpenAICompatibleLLM()
    else:
        from app.llm.local_impl import MockLLM
        logger.warning("LLM 使用内置抽取式实现（未配置 LLM_API_KEY）")
        inner = MockLLM()
    # 包裹计时：透明采集 LLM 生成(chat)耗时，不改动任何调用方
    return TimedLLM(inner)


class TimedLLM(BaseLLM):
    """LLM 耗时埋点装饰器：包裹 chat()，计时写入 metrics。

    对 stream() 也计时首包；但本期仅 chat 走统一埋点（/chat 走 chat）。
    """

    def __init__(self, inner: BaseLLM) -> None:
        self.inner = inner

    async def chat(self, messages, *, temperature=None, max_tokens=None):
        t0 = time.perf_counter()
        try:
            return await self.inner.chat(
                messages, temperature=temperature, max_tokens=max_tokens)
        finally:
            try:
                app_metrics.observe("terraforge_llm_duration_seconds",
                                    time.perf_counter() - t0)
            except Exception:  # noqa: BLE001
                pass

    async def stream(self, messages, *, temperature=None):
        return await self.inner.stream(messages, temperature=temperature)


class CachedEmbedding(BaseEmbedding):
    """Embedding 缓存装饰器：按文本维度走 L1/L2 多级缓存（app.core.cache），
    减少重复 Embedding 推理——对真实远程 Embedding 尤其关键（避免重复网络请求）。
    透明包裹任意 BaseEmbedding 实现，所有调用方自动受益。"""

    def __init__(self, inner: BaseEmbedding, provider: str, model: str) -> None:
        self.inner = inner
        self.dim = inner.dim
        self._provider = provider
        self._model = model

    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        from app.core.cache import default_cache, embedding_cache_key
        results: List[List[float]] = []
        miss_idx: List[int] = []
        for i, t in enumerate(texts):
            cached = default_cache.get(embedding_cache_key(self._provider, self._model, t))
            if cached is not None:
                results.append(cached)
            else:
                miss_idx.append(i)
        if miss_idx:
            miss_texts = [texts[i] for i in miss_idx]
            t0 = time.perf_counter()
            try:
                got = await self.inner.embed_texts(miss_texts)
            finally:
                try:
                    app_metrics.observe("terraforge_embedding_duration_seconds",
                                        time.perf_counter() - t0)
                except Exception:  # noqa: BLE001
                    pass
            for j, i in enumerate(miss_idx):
                key = embedding_cache_key(self._provider, self._model, texts[i])
                default_cache.set(key, got[j])
                results.append(got[j])
        return results


@lru_cache
def get_embedding() -> BaseEmbedding:
    if settings.EMBEDDING_PROVIDER == "openai_compatible" and settings.EMBEDDING_API_KEY:
        from app.llm.openai_client import OpenAICompatibleEmbedding
        logger.info("Embedding 使用 OpenAI 兼容接口 | model=%s", settings.EMBEDDING_MODEL)
        inner = OpenAICompatibleEmbedding()
    else:
        from app.llm.local_impl import HashEmbedding
        logger.warning("Embedding 使用内置 Hash 实现（未配置 EMBEDDING_API_KEY）")
        inner = HashEmbedding()
    # 包裹多级缓存：检索/重排/入库所有 embedding 调用自动命中 L1/L2
    return CachedEmbedding(inner, settings.EMBEDDING_PROVIDER, settings.EMBEDDING_MODEL)


@lru_cache
def get_reranker() -> BaseReranker:
    if settings.RERANK_PROVIDER == "cross_encoder_api" and settings.RERANK_BASE_URL:
        from app.llm.openai_client import CrossEncoderAPIReranker
        logger.info("Rerank 使用远程 CrossEncoder | model=%s", settings.RERANK_MODEL)
        return CrossEncoderAPIReranker()
    if settings.RERANK_PROVIDER == "cross_encoder_local":
        from app.llm.local_impl import LexicalInteractionReranker
        logger.info("Rerank 使用本地 CrossEncoder 风格重排器（零依赖）")
        return LexicalInteractionReranker()
    from app.llm.local_impl import RuleReranker
    logger.info("Rerank 使用内置规则重排器")
    return RuleReranker()
