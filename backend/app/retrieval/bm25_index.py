"""
BM25 关键词索引（进程内，可持久化，按知识库隔离）
==============================================
工程规范检索里关键词通道极其重要——"GB50204""坍落度""C30"这类
术语靠稠密向量常常召不回来，必须有精确词面通道兜底。

Area B：按知识库分区（`self._kbs[kb_id]`），删除知识库即移除对应分区，
根除「共享 BM25 索引污染」。兼容旧版扁平 pkl 格式（加载时自动重分区）。
"""
from __future__ import annotations

import pickle
import threading
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from app.core.config import settings
from app.core.logging import get_logger
from app.utils.text import tokenize

logger = get_logger(__name__)


class BM25Index:
    def __init__(self, path: str | None = None):
        self.path = Path(path or settings.LOCAL_VECTOR_DIR) / "bm25.pkl"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        # 按知识库分区：{ kb_id: {"ids","corpus","meta","bm25"} }
        self._kbs: Dict[str, dict] = {}
        self._load()

    # ---------------- 持久化 ----------------
    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            with open(self.path, "rb") as f:
                d = pickle.load(f)
            if "kbs" in d:  # 新格式：按库分区
                self._kbs = {}
                for kb, v in d["kbs"].items():
                    self._kbs[kb] = {
                        "ids": v["ids"], "corpus": v["corpus"],
                        "meta": v["meta"], "bm25": None,
                    }
                for bucket in self._kbs.values():
                    self._rebuild_bucket(bucket)
            else:  # 旧版扁平格式：按 meta.kb_id 重分区
                ids, corpus, meta = d["ids"], d["corpus"], d["meta"]
                groups: Dict[str, List[int]] = {}
                for i, m in enumerate(meta):
                    kb = m.get("kb_id", "") or ""
                    groups.setdefault(kb, []).append(i)
                for kb, idxs in groups.items():
                    bucket = {
                        "ids": [ids[i] for i in idxs],
                        "corpus": [corpus[i] for i in idxs],
                        "meta": [meta[i] for i in idxs],
                        "bm25": None,
                    }
                    self._rebuild_bucket(bucket)
                    self._kbs[kb] = bucket
                logger.info("BM25 索引(旧格式)已按库重分区 | %d 个库",
                            len(self._kbs))
            total = sum(len(v["ids"]) for v in self._kbs.values())
            logger.info("BM25 索引加载完成 | %d 条 / %d 库", total, len(self._kbs))
        except Exception as e:  # noqa: BLE001
            logger.warning("BM25 索引加载失败，重建: %s", e)
            self._kbs = {}

    def _persist(self) -> None:
        tmp = self.path.with_suffix(".tmp")
        with open(tmp, "wb") as f:
            pickle.dump({
                "version": 2,
                "kbs": {kb: {"ids": v["ids"], "corpus": v["corpus"], "meta": v["meta"]}
                        for kb, v in self._kbs.items()},
            }, f)
        tmp.replace(self.path)

    def _rebuild_bucket(self, bucket: dict) -> None:
        if not bucket["corpus"]:
            bucket["bm25"] = None
            return
        try:
            from rank_bm25 import BM25Okapi
            bucket["bm25"] = BM25Okapi(bucket["corpus"], k1=1.5, b=0.75)
        except ImportError:  # pragma: no cover
            bucket["bm25"] = None
        bucket["dirty"] = False

    # ---------------- 接口 ----------------
    def add(self, items: List[Tuple[str, str, dict]]) -> int:
        """items: [(chunk_id, content, meta)]；meta 含 kb_id（用于分区）。"""
        if not items:
            return 0
        with self._lock:
            for cid, content, meta in items:
                kb = meta.get("kb_id", "") or ""
                bucket = self._kbs.setdefault(
                    kb, {"ids": [], "corpus": [], "meta": [], "bm25": None})
                toks = tokenize(content)
                if cid in bucket["ids"]:
                    pos = bucket["ids"].index(cid)
                    bucket["corpus"][pos] = toks
                    bucket["meta"][pos] = meta
                else:
                    bucket["ids"].append(cid)
                    bucket["corpus"].append(toks)
                    bucket["meta"].append(meta)
                self._rebuild_bucket(bucket)
            self._persist()
        return len(items)

    def delete_by_doc(self, doc_id: str) -> int:
        with self._lock:
            removed = 0
            for bucket in self._kbs.values():
                keep = [i for i, m in enumerate(bucket["meta"])
                        if m.get("doc_id") != doc_id]
                removed += len(bucket["ids"]) - len(keep)
                if removed:
                    bucket["ids"] = [bucket["ids"][i] for i in keep]
                    bucket["corpus"] = [bucket["corpus"][i] for i in keep]
                    bucket["meta"] = [bucket["meta"][i] for i in keep]
                    self._rebuild_bucket(bucket)
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

    def search(self, query: str, top_k: int,
               kb_ids: Optional[List[str]] = None,
               domains: Optional[List[str]] = None,
               tenant_id: Optional[str] = None) -> List[Tuple[str, float, dict]]:
        with self._lock:
            if not self._kbs:
                return []
            q = tokenize(query)
            if not q:
                return []
            qs = set(q)
            kbs = set(kb_ids) if kb_ids else None
            ds = set(domains) if domains else None

            cand: List[Tuple[str, float, dict]] = []
            for kb, bucket in self._kbs.items():
                if kbs is not None and kb not in kbs:
                    continue
                if not bucket["ids"]:
                    continue
                corpus = bucket["corpus"]
                overlap = [len(qs & set(c)) / (len(qs) or 1) for c in corpus]
                if bucket["bm25"] is not None:
                    scores = list(bucket["bm25"].get_scores(q))
                    if max(scores, default=0.0) <= 0:
                        scores = overlap
                    else:
                        scores = [s + 0.01 * o for s, o in zip(scores, overlap)]
                else:
                    scores = overlap
                for i, s in enumerate(scores):
                    if s <= 0:
                        continue
                    m = bucket["meta"][i]
                    if ds and m.get("domain") not in ds:
                        continue
                    if tenant_id and m.get("tenant_id") != tenant_id:
                        continue
                    cand.append((bucket["ids"][i], float(s), m))
            cand.sort(key=lambda x: x[1], reverse=True)
            top = cand[:top_k]
            if top:
                mx = top[0][1] or 1.0
                top = [(i, round(s / mx, 6), m) for i, s, m in top]
            return top

    def count(self) -> int:
        return sum(len(v["ids"]) for v in self._kbs.values())


_index: BM25Index | None = None
_index_lock = threading.Lock()


def get_bm25_index() -> BM25Index:
    global _index
    if _index is None:
        with _index_lock:
            if _index is None:
                _index = BM25Index()
    return _index
