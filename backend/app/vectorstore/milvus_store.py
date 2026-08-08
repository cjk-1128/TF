"""Milvus 向量库实现（生产环境）。"""
from __future__ import annotations

from typing import List, Optional

from app.core.config import settings
from app.core.exceptions import VectorStoreError
from app.core.logging import get_logger
from app.vectorstore.base import BaseVectorStore, VectorHit, VectorRecord

logger = get_logger(__name__)

_OUTPUT_FIELDS = ["doc_id", "kb_id", "domain", "discipline", "content",
                  "section_path", "clause_no", "page_no"]


class MilvusVectorStore(BaseVectorStore):
    def __init__(self):
        try:
            from pymilvus import MilvusClient
        except ImportError as e:  # pragma: no cover
            raise VectorStoreError("未安装 pymilvus，请先 pip install pymilvus") from e

        uri = f"http://{settings.MILVUS_HOST}:{settings.MILVUS_PORT}"
        token = (f"{settings.MILVUS_USER}:{settings.MILVUS_PASSWORD}"
                 if settings.MILVUS_USER else "")
        try:
            self.client = MilvusClient(uri=uri, token=token)
        except Exception as e:  # noqa: BLE001
            raise VectorStoreError(f"Milvus 连接失败: {e}")
        self.collection = settings.MILVUS_COLLECTION
        self._dim = settings.EMBEDDING_DIM
        logger.info("Milvus 已连接 | %s", uri)

    def ensure_collection(self, dim: int) -> None:
        from pymilvus import DataType

        self._dim = dim
        if self.client.has_collection(self.collection):
            return
        schema = self.client.create_schema(auto_id=False, enable_dynamic_field=True)
        schema.add_field("id", DataType.VARCHAR, is_primary=True, max_length=64)
        schema.add_field("vector", DataType.FLOAT_VECTOR, dim=dim)
        schema.add_field("doc_id", DataType.VARCHAR, max_length=64)
        schema.add_field("kb_id", DataType.VARCHAR, max_length=64)
        schema.add_field("domain", DataType.VARCHAR, max_length=32)
        schema.add_field("discipline", DataType.VARCHAR, max_length=32)
        schema.add_field("content", DataType.VARCHAR, max_length=8192)
        schema.add_field("section_path", DataType.VARCHAR, max_length=512)
        schema.add_field("clause_no", DataType.VARCHAR, max_length=64)
        schema.add_field("page_no", DataType.INT64)

        index_params = self.client.prepare_index_params()
        index_params.add_index(
            field_name="vector",
            index_type=settings.MILVUS_INDEX_TYPE,
            metric_type=settings.MILVUS_METRIC_TYPE,
            params={"M": 16, "efConstruction": 200},
        )
        self.client.create_collection(self.collection, schema=schema,
                                      index_params=index_params)
        logger.info("Milvus 集合已创建 | %s dim=%d", self.collection, dim)

    def upsert(self, records: List[VectorRecord]) -> int:
        if not records:
            return 0
        self.ensure_collection(len(records[0].vector))
        rows = []
        for r in records:
            rows.append({
                "id": r.id, "vector": r.vector, "doc_id": r.doc_id, "kb_id": r.kb_id,
                "domain": r.domain, "discipline": r.discipline,
                "content": r.content[:8000],
                "section_path": str(r.meta.get("section_path", ""))[:500],
                "clause_no": str(r.meta.get("clause_no", ""))[:60],
                "page_no": int(r.meta.get("page_no", 0) or 0),
            })
        try:
            self.client.upsert(collection_name=self.collection, data=rows)
        except Exception as e:  # noqa: BLE001
            raise VectorStoreError(f"Milvus 写入失败: {e}")
        return len(rows)

    def search(self, vector: List[float], top_k: int,
               kb_ids: Optional[List[str]] = None,
               domains: Optional[List[str]] = None) -> List[VectorHit]:
        exprs = []
        if kb_ids:
            exprs.append("kb_id in [%s]" % ",".join(f'"{i}"' for i in kb_ids))
        if domains:
            exprs.append("domain in [%s]" % ",".join(f'"{d}"' for d in domains))
        expr = " and ".join(exprs) if exprs else None
        try:
            res = self.client.search(
                collection_name=self.collection, data=[vector], limit=top_k,
                filter=expr or "", output_fields=_OUTPUT_FIELDS,
                search_params={"metric_type": settings.MILVUS_METRIC_TYPE,
                               "params": {"ef": max(64, top_k * 4)}},
            )
        except Exception as e:  # noqa: BLE001
            raise VectorStoreError(f"Milvus 检索失败: {e}")

        hits: List[VectorHit] = []
        for group in res:
            for h in group:
                ent = h.get("entity", {}) or {}
                hits.append(VectorHit(
                    id=str(h.get("id")), score=float(h.get("distance", 0.0)),
                    doc_id=ent.get("doc_id", ""), kb_id=ent.get("kb_id", ""),
                    domain=ent.get("domain", ""), content=ent.get("content", ""),
                    meta=ent,
                ))
        return hits

    def delete_by_doc(self, doc_id: str) -> int:
        try:
            self.client.delete(collection_name=self.collection, filter=f'doc_id == "{doc_id}"')
            return 1
        except Exception as e:  # noqa: BLE001
            logger.warning("Milvus 删除失败: %s", e)
            return 0

    def flush(self) -> None:
        """强制落盘，确保 get_collection_stats / 检索统计反映最新写入。"""
        try:
            self.client.flush(self.collection)
        except Exception as e:  # noqa: BLE001
            logger.warning("Milvus flush 失败(忽略): %s", e)

    def count(self) -> int:
        # upsert 后数据未落盘时 row_count 会读到旧值(0)，先 flush 保证统计准确
        self.flush()
        try:
            stats = self.client.get_collection_stats(self.collection)
            return int(stats.get("row_count", 0))
        except Exception:  # noqa: BLE001
            return 0
