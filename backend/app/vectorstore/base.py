"""向量库抽象接口。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class VectorRecord:
    id: str
    vector: List[float]
    doc_id: str = ""
    kb_id: str = ""
    domain: str = ""
    discipline: str = ""
    content: str = ""
    meta: Dict = field(default_factory=dict)


@dataclass
class VectorHit:
    id: str
    score: float
    doc_id: str = ""
    kb_id: str = ""
    domain: str = ""
    content: str = ""
    meta: Dict = field(default_factory=dict)


class BaseVectorStore(ABC):
    @abstractmethod
    def ensure_collection(self, dim: int) -> None: ...

    @abstractmethod
    def upsert(self, records: List[VectorRecord]) -> int: ...

    @abstractmethod
    def search(self, vector: List[float], top_k: int,
               kb_ids: Optional[List[str]] = None,
               domains: Optional[List[str]] = None) -> List[VectorHit]: ...

    @abstractmethod
    def delete_by_doc(self, doc_id: str) -> int: ...

    @abstractmethod
    def count(self) -> int: ...
