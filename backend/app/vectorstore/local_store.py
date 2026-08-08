"""
本地轻量向量库（numpy 内存索引 + 磁盘持久化）
=========================================
用于零依赖开发/测试环境；生产切换 VECTOR_BACKEND=milvus 即可，无需改动业务代码。

Area B：按知识库隔离。内部结构按 kb_id 分区（`self._kbs[kb_id]`），
删除知识库即移除对应分区，根除「共享向量索引污染」。兼容旧版扁平 pkl 格式
（加载时按 meta.kb_id 自动重分区）。
"""
from __future__ import annotations

import pickle
import threading
from pathlib import Path
from typing import Dict, List, Optional

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
        # 按知识库分区的内部索引：{ kb_id: {"ids","meta","matrix"} }
        self._kbs: Dict[str, dict] = {}
        self._dim = settings.EMBEDDING_DIM
        self._load()

    # ---------------- 持久化 ----------------
    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            with open(self.path, "rb") as f:
                data = pickle.load(f)
            if "kbs" in data:  # 新格式：按库分区
                self._kbs = {
                    kb: {"ids": v["ids"], "meta": v["meta"], "matrix": v["matrix"]}
                    for kb, v in data["kbs"].items()
                }
                self._dim = data.get("dim", self._dim)
            else:  # 旧版扁平格式：按 meta.kb_id 重分区
                ids = data["ids"]
                meta = data["meta"]
                matrix = data["matrix"]
                self._dim = data.get("dim", self._dim)
                groups: Dict[str, List[int]] = {}
                for i, m in enumerate(meta):
                    kb = m.get("kb_id", "") or ""
                    groups.setdefault(kb, []).append(i)
                for kb, idxs in groups.items():
                    self._kbs[kb] = {
                        "ids": [ids[i] for i in idxs],
                        "meta": [meta[i] for i in idxs],
                        "matrix": matrix[idxs] if len(idxs) else None,
                    }
                logger.info("本地向量库(旧格式)已按库重分区 | %d 个库",
                            len(self._kbs))
            total = sum(len(v["ids"]) for v in self._kbs.values())
            logger.info("本地向量库加载完成 | %d 条 / %d 库", total, len(self._kbs))
        except Exception as e:  # noqa: BLE001
            logger.warning("向量库加载失败，重建: %s", e)
            self._kbs = {}

    def _persist(self) -> None:
        tmp = self.path.with_suffix(".tmp")
        with open(tmp, "wb") as f:
            pickle.dump({"version": 2, "kbs": self._kbs, "dim": self._dim}, f)
        tmp.replace(self.path)

    # ---------------- 接口 ----------------
    def ensure_collection(self, dim: int) -> None:
        self._dim = dim

    def upsert(self, records: List[VectorRecord]) -> int:
        if not records:
            return 0
        with self._lock:
            for r in records:
                kb = r.kb_id or ""
                bucket = self._kbs.setdefault(
                    kb, {"ids": [], "meta": [], "matrix": None})
                vec = np.asarray(r.vector, dtype=np.float32)
                n = np.linalg.norm(vec) or 1.0
                vec = vec / n
                meta = {"doc_id": r.doc_id, "kb_id": r.kb_id,
                        "tenant_id": r.tenant_id, "domain": r.domain,
                        "discipline": r.discipline, "content": r.content, **r.meta}
                if r.id in bucket["ids"] and bucket["matrix"] is not None:
                    pos = bucket["ids"].index(r.id)
                    bucket["matrix"][pos] = vec
                    bucket["meta"][pos] = meta
                else:
                    bucket["ids"].append(r.id)
                    bucket["meta"].append(meta)
                    bucket["matrix"] = (vec if bucket["matrix"] is None
                                        else np.vstack([bucket["matrix"], vec]))
                    if bucket["matrix"] is not None and bucket["matrix"].ndim == 1:
                        bucket["matrix"] = bucket["matrix"].reshape(1, -1)
                self._dim = bucket["matrix"].shape[1]
            self._persist()
        return len(records)

    def search(self, vector: List[float], top_k: int,
               kb_ids: Optional[List[str]] = None,
               domains: Optional[List[str]] = None,
               tenant_id: Optional[str] = None) -> List[VectorHit]:
        with self._lock:
            q = np.asarray(vector, dtype=np.float32)
            if q.shape[0] == 0:
                return []
            hits: List[VectorHit] = []
            kbs = set(kb_ids) if kb_ids else None
            ds = set(domains) if domains else None
            for kb, bucket in self._kbs.items():
                if kbs is not None and kb not in kbs:
                    continue
                matrix = bucket["matrix"]
                if matrix is None or not len(bucket["ids"]):
                    continue
                if q.shape[0] != matrix.shape[1]:
                    logger.warning("查询向量维度不匹配 %d vs %d", q.shape[0], matrix.shape[1])
                    continue
                qn = q / (np.linalg.norm(q) or 1.0)
                sims = matrix @ qn
                for i in range(len(bucket["ids"])):
                    m = bucket["meta"][i]
                    if ds and m.get("domain") not in ds:
                        continue
                    if tenant_id and m.get("tenant_id") != tenant_id:
                        continue
                    hits.append(VectorHit(
                        id=bucket["ids"][i], score=float(sims[i]),
                        doc_id=m.get("doc_id", ""), kb_id=m.get("kb_id", ""),
                        domain=m.get("domain", ""), content=m.get("content", ""),
                        meta=m))
            if not hits:
                return []
            hits.sort(key=lambda x: x.score, reverse=True)
            return hits[:top_k]

    def delete_by_doc(self, doc_id: str, kb_id: Optional[str] = None) -> int:
        with self._lock:
            removed = 0
            for bucket in (list(self._kbs.values()) if not kb_id else [self._kbs.get(kb_id)]):
                if not bucket:
                    continue
                keep = [i for i, m in enumerate(bucket["meta"])
                        if m.get("doc_id") != doc_id]
                removed += len(bucket["ids"]) - len(keep)
                if removed:
                    bucket["ids"] = [bucket["ids"][i] for i in keep]
                    bucket["meta"] = [bucket["meta"][i] for i in keep]
                    bucket["matrix"] = bucket["matrix"][keep] if keep else None
            if removed:
                self._persist()
            return removed

    def delete_by_kb(self, kb_id: str, tenant_id: Optional[str] = None) -> int:
        with self._lock:
            bucket = self._kbs.get(kb_id)
            if not bucket:
                return 0
            removed = len(bucket["ids"])
            del self._kbs[kb_id]
            self._persist()
            return removed

    def count(self) -> int:
        return sum(len(v["ids"]) for v in self._kbs.values())

    def get_vector_norms(self, ids: List[str]) -> Dict[str, float]:
        """返回给定向量 id 的 L2 范数（用于质量巡检的「向量质量」维度）。

        本地向量在写入时已 L2 归一化，故正常向量范数 ≈ 1.0；零向量范数 = 0.0；
        id 不在库中返回 -1.0（缺失）。跨所有知识库分区查找。
        """
        with self._lock:
            id2pos: Dict[str, tuple] = {}
            for kb, bucket in self._kbs.items():
                if bucket["matrix"] is None:
                    continue
                for i, rid in enumerate(bucket["ids"]):
                    id2pos[rid] = (bucket["matrix"], i)
            out: Dict[str, float] = {}
            for rid in ids:
                loc = id2pos.get(rid)
                out[rid] = -1.0 if loc is None else float(np.linalg.norm(loc[0][loc[1]]))
            return out
