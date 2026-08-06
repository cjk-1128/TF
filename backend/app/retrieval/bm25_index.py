"""
BM25 关键词索引（进程内，可持久化）
================================
工程规范检索里关键词通道极其重要——"GB50204""坍落度""C30"这类
术语靠稠密向量常常召不回来，必须有精确词面通道兜底。
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
        self._ids: List[str] = []
        self._corpus: List[List[str]] = []
        self._meta: List[dict] = []
        self._bm25 = None
        self._dirty = False
        self._load()

    # ---------------- 持久化 ----------------
    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            with open(self.path, "rb") as f:
                d = pickle.load(f)
            self._ids, self._corpus, self._meta = d["ids"], d["corpus"], d["meta"]
            self._rebuild()
            logger.info("BM25 索引加载完成 | %d 条", len(self._ids))
        except Exception as e:  # noqa: BLE001
            logger.warning("BM25 索引加载失败，重建: %s", e)

    def _persist(self) -> None:
        tmp = self.path.with_suffix(".tmp")
        with open(tmp, "wb") as f:
            pickle.dump({"ids": self._ids, "corpus": self._corpus, "meta": self._meta}, f)
        tmp.replace(self.path)

    def _rebuild(self) -> None:
        if not self._corpus:
            self._bm25 = None
            return
        try:
            from rank_bm25 import BM25Okapi
            self._bm25 = BM25Okapi(self._corpus, k1=1.5, b=0.75)
        except ImportError:  # pragma: no cover
            logger.warning("未安装 rank_bm25，关键词通道退化为词面覆盖打分")
            self._bm25 = None
        self._dirty = False

    # ---------------- 接口 ----------------
    def add(self, items: List[Tuple[str, str, dict]]) -> int:
        """items: [(chunk_id, content, meta)]"""
        if not items:
            return 0
        with self._lock:
            pos = {cid: i for i, cid in enumerate(self._ids)}
            for cid, content, meta in items:
                toks = tokenize(content)
                if cid in pos:
                    self._corpus[pos[cid]] = toks
                    self._meta[pos[cid]] = meta
                else:
                    self._ids.append(cid)
                    self._corpus.append(toks)
                    self._meta.append(meta)
            self._rebuild()
            self._persist()
        return len(items)

    def delete_by_doc(self, doc_id: str) -> int:
        with self._lock:
            keep = [i for i, m in enumerate(self._meta) if m.get("doc_id") != doc_id]
            removed = len(self._ids) - len(keep)
            if removed:
                self._ids = [self._ids[i] for i in keep]
                self._corpus = [self._corpus[i] for i in keep]
                self._meta = [self._meta[i] for i in keep]
                self._rebuild()
                self._persist()
            return removed

    def search(self, query: str, top_k: int,
               kb_ids: Optional[List[str]] = None,
               domains: Optional[List[str]] = None) -> List[Tuple[str, float, dict]]:
        with self._lock:
            if not self._ids:
                return []
            q = tokenize(query)
            if not q:
                return []

            qs = set(q)
            overlap = [len(qs & set(c)) / (len(qs) or 1) for c in self._corpus]

            if self._bm25 is not None:
                scores = list(self._bm25.get_scores(q))
                # 小语料时 BM25 的 IDF 可能整体为负（词出现在过半文档中），
                # 此时全部被过滤掉，需退回词面覆盖率兜底。
                if max(scores, default=0.0) <= 0:
                    scores = overlap
                else:
                    # 融合一点覆盖率信号，避免长文档被过度惩罚
                    scores = [s + 0.01 * o for s, o in zip(scores, overlap)]
            else:
                scores = overlap

            kbs = set(kb_ids) if kb_ids else None
            ds = set(domains) if domains else None
            cand: List[Tuple[str, float, dict]] = []
            for i, s in enumerate(scores):
                if s <= 0:
                    continue
                m = self._meta[i]
                if kbs and m.get("kb_id") not in kbs:
                    continue
                if ds and m.get("domain") not in ds:
                    continue
                cand.append((self._ids[i], float(s), m))
            cand.sort(key=lambda x: x[1], reverse=True)
            top = cand[:top_k]
            # 归一化到 0-1，便于与向量分数融合展示
            if top:
                mx = top[0][1] or 1.0
                top = [(i, round(s / mx, 6), m) for i, s, m in top]
            return top

    def count(self) -> int:
        return len(self._ids)


_index: BM25Index | None = None
_index_lock = threading.Lock()


def get_bm25_index() -> BM25Index:
    global _index
    if _index is None:
        with _index_lock:
            if _index is None:
                _index = BM25Index()
    return _index
