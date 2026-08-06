"""OpenAI Compatible API 客户端（可对接 DeepSeek / 通义 / vLLM / Ollama 等）。"""
from __future__ import annotations

import asyncio
import json
from typing import AsyncIterator, List

import httpx

from app.core.config import settings
from app.core.exceptions import EmbeddingError, LLMError
from app.core.logging import get_logger
from app.llm.base import (BaseEmbedding, BaseLLM, BaseReranker, ChatMessage,
                          LLMResult)

logger = get_logger(__name__)


class OpenAICompatibleLLM(BaseLLM):
    def __init__(self, base_url: str | None = None, api_key: str | None = None,
                 model: str | None = None):
        self.base_url = (base_url or settings.LLM_BASE_URL).rstrip("/")
        self.api_key = api_key or settings.LLM_API_KEY
        self.model = model or settings.LLM_MODEL

    @property
    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    async def chat(self, messages: List[ChatMessage], *, temperature=None,
                   max_tokens=None) -> LLMResult:
        payload = {
            "model": self.model,
            "messages": [m.to_dict() for m in messages],
            "temperature": settings.LLM_TEMPERATURE if temperature is None else temperature,
            "max_tokens": max_tokens or settings.LLM_MAX_TOKENS,
        }
        last_err = None
        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=settings.LLM_TIMEOUT) as cli:
                    r = await cli.post(f"{self.base_url}/chat/completions",
                                       headers=self._headers, json=payload)
                    r.raise_for_status()
                    data = r.json()
                choice = data["choices"][0]
                return LLMResult(
                    content=choice["message"]["content"],
                    usage=data.get("usage", {}) or {},
                    model=data.get("model", self.model),
                    finish_reason=choice.get("finish_reason", "stop"),
                )
            except Exception as e:  # noqa: BLE001
                last_err = e
                logger.warning("LLM 调用失败(第%d次): %s", attempt + 1, e)
                await asyncio.sleep(1.5 * (attempt + 1))
        raise LLMError(f"大模型调用失败: {last_err}")

    async def stream(self, messages: List[ChatMessage], *, temperature=None) -> AsyncIterator[str]:
        payload = {
            "model": self.model,
            "messages": [m.to_dict() for m in messages],
            "temperature": settings.LLM_TEMPERATURE if temperature is None else temperature,
            "max_tokens": settings.LLM_MAX_TOKENS,
            "stream": True,
        }
        try:
            async with httpx.AsyncClient(timeout=settings.LLM_TIMEOUT) as cli:
                async with cli.stream("POST", f"{self.base_url}/chat/completions",
                                      headers=self._headers, json=payload) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if not line or not line.startswith("data: "):
                            continue
                        chunk = line[6:].strip()
                        if chunk == "[DONE]":
                            break
                        try:
                            delta = json.loads(chunk)["choices"][0].get("delta", {})
                            if delta.get("content"):
                                yield delta["content"]
                        except Exception:  # noqa: BLE001
                            continue
        except Exception as e:  # noqa: BLE001
            raise LLMError(f"流式调用失败: {e}")


class OpenAICompatibleEmbedding(BaseEmbedding):
    def __init__(self):
        self.base_url = settings.EMBEDDING_BASE_URL.rstrip("/")
        self.api_key = settings.EMBEDDING_API_KEY
        self.model = settings.EMBEDDING_MODEL
        self.dim = settings.EMBEDDING_DIM

    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        from app.core.cache import default_cache, embedding_cache_key
        provider = self.__class__.__name__

        # 1) 逐条走缓存（L1/L2），命中直接返回
        out: List[Optional[List[float]]] = [None] * len(texts)
        miss_idx: List[int] = []
        for i, t in enumerate(texts):
            cached = default_cache.get(embedding_cache_key(provider, self.model, t))
            if cached is not None:
                out[i] = cached
            else:
                miss_idx.append(i)
        if not miss_idx:
            return [o for o in out if o is not None]

        # 2) 仅对未命中的文本调用 API（保持原有分批逻辑）
        miss_texts = [texts[i] for i in miss_idx]
        miss_vecs = await self._embed_batch(miss_texts)
        for j, i in enumerate(miss_idx):
            vec = miss_vecs[j]
            default_cache.set(embedding_cache_key(provider, self.model, texts[i]), vec)
            out[i] = vec
        return [o for o in out if o is not None]

    async def _embed_batch(self, texts: List[str]) -> List[List[float]]:
        """实际的批量向量化（被 embed_texts 的缓存层调用）。"""
        out: List[List[float]] = []
        bs = settings.EMBEDDING_BATCH_SIZE
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        async with httpx.AsyncClient(timeout=settings.LLM_TIMEOUT) as cli:
            for i in range(0, len(texts), bs):
                batch = texts[i:i + bs]
                try:
                    r = await cli.post(f"{self.base_url}/embeddings", headers=headers,
                                       json={"model": self.model, "input": batch})
                    r.raise_for_status()
                    data = r.json()["data"]
                    out.extend(item["embedding"] for item in sorted(data, key=lambda x: x["index"]))
                except Exception as e:  # noqa: BLE001
                    raise EmbeddingError(f"向量化失败: {e}")
        if out:
            self.dim = len(out[0])
        return out


class CrossEncoderAPIReranker(BaseReranker):
    """对接 bge-reranker 类 HTTP 服务。"""

    async def rerank(self, query: str, docs: List[str], top_n: int) -> List[tuple[int, float]]:
        if not docs:
            return []
        url = settings.RERANK_BASE_URL.rstrip("/") + "/rerank"
        headers = {"Authorization": f"Bearer {settings.RERANK_API_KEY}"}
        try:
            async with httpx.AsyncClient(timeout=60) as cli:
                r = await cli.post(url, headers=headers, json={
                    "model": settings.RERANK_MODEL, "query": query,
                    "documents": docs, "top_n": top_n,
                })
                r.raise_for_status()
                results = r.json().get("results", [])
            return [(it["index"], float(it["relevance_score"])) for it in results]
        except Exception as e:  # noqa: BLE001
            logger.warning("Rerank 服务失败，降级为原序: %s", e)
            return [(i, 1.0 - i * 0.01) for i in range(min(top_n, len(docs)))]
