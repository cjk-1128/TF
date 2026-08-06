"""
本地轻量向量库（numpy 内存索引 + 磁盘持久化）
=========================================
用于零依赖开发/测试环境；生产切换 VECTOR_BACKEND=milvus 即可，无需改动业务代码。
"""
from __future__ import annotations

import pickle
import threading
from pathlib import Path
from typing import List, Optional

import numpy as np

from app.core.config import settings
from app.core.logging import get_logger
from app.vectorstore.base import BaseVectorStore, VectorHit, VectorRecord

logger = get_logger(__name__)


class LocalVectorStore(BaseVectorStore):
    def __init__(self, path: str | None = None):
        self.path = Path(path or settings.LOCAL_VECTOR_DIR) / "vectors.pkl"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._ids: List[str] = []
        self._meta: List[dict] = []
        self._matrix: Optional[np.ndarray] = None
        self._dim = settings.EMBEDDING_DIM
        self._load()

    # ---------------- 持久化 ----------------
    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            with open(self.path, "rb") as f:
                data = pickle.load(f)
            self._ids = data["ids"]
            self._meta = data["meta"]
            self._matrix = data["matrix"]
            self._dim = data.get("dim", self._dim)
            logger.info("本地向量库加载完成 | %d 条", len(self._ids))
        except Exception as e:  # noqa: BLE001
            logger.warning("向量库加载失败，重建: %s", e)
            self._ids, self._meta, self._matrix = [], [], None

    def _persist(self) -> None:
        tmp = self.path.with_suffix(".tmp")
        with open(tmp, "wb") as f:
            pickle.dump({"ids": self._ids, "meta": self._meta,
                         "matrix": self._matrix, "dim": self._dim}, f)
        tmp.replace(self.path)

    # ---------------- 接口 ----------------
    def ensure_collection(self, dim: int) -> None:
        self._dim = dim

    def upsert(self, records: List[VectorRecord]) -> int:
        if not records:
            return 0
        with self._lock:
            id2pos = {rid: i for i, rid in enumerate(self._ids)}
            new_vecs, new_ids, new_meta = [], [], []
            for r in records:
                vec = np.asarray(r.vector, dtype=np.float32)
                n = np.linalg.norm(vec) or 1.0
                vec = vec / n
                meta = {"doc_id": r.doc_id, "kb_id": r.kb_id, "domain": r.domain,
                        "discipline": r.discipline, "content": r.content, **r.meta}
                if r.id in id2pos and self._matrix is not None:
                    self._matrix[id2pos[r.id]] = vec
                    self._meta[id2pos[r.id]] = meta
                else:
                    new_ids.append(r.id)
                    new_meta.append(meta)
                    new_vecs.append(vec)
            if new_vecs:
                block = np.vstack(new_vecs)
                self._matrix = block if self._matrix is None else np.vstack([self._matrix, block])
                self._ids.extend(new_ids)
                self._meta.extend(new_meta)
                self._dim = block.shape[1]
            self._persist()
        return len(records)

    def search(self, vector: List[float], top_k: int,
               kb_ids: Optional[List[str]] = None,
               domains: Optional[List[str]] = None) -> List[VectorHit]:
        with self._lock:
            if self._matrix is None or not len(self._ids):
                return []
            q = np.asarray(vector, dtype=np.float32)
            if q.shape[0] != self._matrix.shape[1]:
                logger.warning("查询向量维度不匹配 %d vs %d", q.shape[0], self._matrix.shape[1])
                return []
            q = q / (np.linalg.norm(q) or 1.0)
            sims = self._matrix @ q

            mask = np.ones(len(self._ids), dtype=bool)
            if kb_ids:
                kbs = set(kb_ids)
                mask &= np.array([m.get("kb_id") in kbs for m in self._meta])
            if domains:
                ds = set(domains)
                mask &= np.array([m.get("domain") in ds for m in self._meta])
            idxs = np.where(mask)[0]
            if idxs.size == 0:
                return []
            sub = sims[idxs]
            k = min(top_k, sub.size)
            top = idxs[np.argpartition(-sub, k - 1)[:k]]
            top = top[np.argsort(-sims[top])]

            hits = []
            for i in top:
                m = self._meta[i]
                hits.append(VectorHit(
                    id=self._ids[i], score=float(sims[i]),
                    doc_id=m.get("doc_id", ""), kb_id=m.get("kb_id", ""),
                    domain=m.get("domain", ""), content=m.get("content", ""), meta=m,
                ))
            return hits

    def delete_by_doc(self, doc_id: str) -> int:
        with self._lock:
            if self._matrix is None:
                return 0
            keep = [i for i, m in enumerate(self._meta) if m.get("doc_id") != doc_id]
            removed = len(self._ids) - len(keep)
            if removed:
                self._ids = [self._ids[i] for i in keep]
                self._meta = [self._meta[i] for i in keep]
                self._matrix = self._matrix[keep] if keep else None
                self._persist()
            return removed

    def count(self) -> int:
        return len(self._ids)
