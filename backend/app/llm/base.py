"""LLM / Embedding / Rerank 抽象接口。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncIterator, Dict, List


@dataclass
class ChatMessage:
    role: str
    content: str

    def to_dict(self) -> dict:
        return {"role": self.role, "content": self.content}


@dataclass
class LLMResult:
    content: str
    usage: Dict[str, int] = field(default_factory=dict)
    model: str = ""
    finish_reason: str = "stop"


class BaseLLM(ABC):
    @abstractmethod
    async def chat(self, messages: List[ChatMessage], *, temperature: float | None = None,
                   max_tokens: int | None = None) -> LLMResult: ...

    @abstractmethod
    async def stream(self, messages: List[ChatMessage], *,
                     temperature: float | None = None) -> AsyncIterator[str]: ...


class BaseEmbedding(ABC):
    dim: int

    @abstractmethod
    async def embed_texts(self, texts: List[str]) -> List[List[float]]: ...

    async def embed_query(self, text: str) -> List[float]:
        return (await self.embed_texts([text]))[0]


class BaseReranker(ABC):
    @abstractmethod
    async def rerank(self, query: str, docs: List[str], top_n: int) -> List[tuple[int, float]]:
        """返回 [(原始下标, 分数)]，按分数降序。"""
