"""Milvus 向量库实现（生产环境，按知识库隔离）。

企业级生产改造（Area B）：
- 开启 VECTOR_TENANT_ISOLATION 时，每个知识库独立集合 `tf_kb_{kb_id}`，
  删除知识库即 drop 整个集合，根除「共享向量索引污染」隐患。
- schema 增加 `tenant_id` 字段，检索可按租户二次过滤，强化多租户隔离。
- 关闭隔离时回退到单一共享集合（VECTOR_BACKEND=milvus 的兼容模式）。
"""
from __future__ import annotations

from typing import List, Optional

from app.core.config import settings
from app.core.exceptions import VectorStoreError
from app.core.logging import get_logger
from app.vectorstore.base import BaseVectorStore, VectorHit, VectorRecord

logger = get_logger(__name__)

_OUTPUT_FIELDS = ["doc_id", "kb_id", "domain", "discipline", "content",
                  "section_path", "clause_no", "page_no", "tenant_id"]


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
        # 隔离相关配置
        self.isolation = bool(settings.VECTOR_TENANT_ISOLATION)
        self.shared = settings.MILVUS_COLLECTION
        self.prefix = settings.MILVUS_COLLECTION_PREFIX
        self._dim = settings.EMBEDDING_DIM
        logger.info("Milvus 已连接 | %s | 按库隔离=%s 前缀=%s",
                    uri, self.isolation, self.prefix)

    # ---------------- 集合命名 ----------------
    def _col(self, kb_id: str) -> str:
        """返回给定知识库对应的集合名。"""
        if self.isolation:
            return f"{self.prefix}{kb_id}"
        return self.shared

    def _kb_collections(self) -> List[str]:
        """列出当前所有按库隔离集合（仅隔离模式有意义）。"""
        if not self.isolation:
            return [self.shared]
        try:
            all_cols = self.client.list_collections()
        except Exception:  # noqa: BLE001
            return []
        return [c for c in all_cols if c.startswith(self.prefix)]

    # ---------------- schema / 建集合 ----------------
    def ensure_collection(self, dim: int) -> None:
        # 按库隔离下集合按 kb_id 懒创建（见 upsert）；此处仅记录维度，保持接口兼容。
        self._dim = dim

    def _ensure_named(self, name: str, dim: int) -> None:
        from pymilvus import DataType

        self._dim = dim
        if self.client.has_collection(name):
            return
        schema = self.client.create_schema(auto_id=False, enable_dynamic_field=True)
        schema.add_field("id", DataType.VARCHAR, is_primary=True, max_length=64)
        schema.add_field("vector", DataType.FLOAT_VECTOR, dim=dim)
        schema.add_field("doc_id", DataType.VARCHAR, max_length=64)
        schema.add_field("kb_id", DataType.VARCHAR, max_length=64)
        schema.add_field("tenant_id", DataType.VARCHAR, max_length=32)
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
        self.client.create_collection(name, schema=schema, index_params=index_params)
        logger.info("Milvus 集合已创建 | %s dim=%d", name, dim)

    # ---------------- 写入 ----------------
    def upsert(self, records: List[VectorRecord]) -> int:
        if not records:
            return 0
        dim = len(records[0].vector)
        kb_id = records[0].kb_id or ""
        name = self._col(kb_id)
        self._ensure_named(name, dim)
        rows = []
        for r in records:
            rows.append({
                "id": r.id, "vector": r.vector, "doc_id": r.doc_id,
                "kb_id": r.kb_id, "tenant_id": r.tenant_id or "",
                "domain": r.domain, "discipline": r.discipline,
                "content": r.content[:8000],
                "section_path": str(r.meta.get("section_path", ""))[:500],
                "clause_no": str(r.meta.get("clause_no", ""))[:60],
                "page_no": int(r.meta.get("page_no", 0) or 0),
            })
        try:
            self.client.upsert(collection_name=name, data=rows)
        except Exception as e:  # noqa: BLE001
            raise VectorStoreError(f"Milvus 写入失败({name}): {e}")
        return len(rows)

    # ---------------- 检索 ----------------
    def search(self, vector: List[float], top_k: int,
               kb_ids: Optional[List[str]] = None,
               domains: Optional[List[str]] = None,
               tenant_id: Optional[str] = None) -> List[VectorHit]:
        if self.isolation and kb_ids:
            names = [self._col(k) for k in kb_ids]
        else:
            names = self._kb_collections()

        exprs = []
        if domains:
            exprs.append("domain in [%s]" % ",".join(f'"{d}"' for d in domains))
        if tenant_id:
            exprs.append("tenant_id == \"%s\"" % tenant_id)
        expr = " and ".join(exprs) if exprs else ""

        hits: List[VectorHit] = []
        for name in names:
            if not self.client.has_collection(name):
                continue
            try:
                res = self.client.search(
                    collection_name=name, data=[vector], limit=top_k,
                    filter=expr or "", output_fields=_OUTPUT_FIELDS,
                    search_params={"metric_type": settings.MILVUS_METRIC_TYPE,
                                   "params": {"ef": max(64, top_k * 4)}},
                )
            except Exception as e:  # noqa: BLE001
                logger.warning("Milvus 检索失败(%s): %s", name, e)
                continue

            for group in res:
                for h in group:
                    ent = h.get("entity", {}) or {}
                    hits.append(VectorHit(
                        id=str(h.get("id")), score=float(h.get("distance", 0.0)),
                        doc_id=ent.get("doc_id", ""), kb_id=ent.get("kb_id", ""),
                        domain=ent.get("domain", ""), content=ent.get("content", ""),
                        meta=ent,
                    ))
        # 跨集合合并：cosine 距离越低越相似，取全局 top_k
        hits.sort(key=lambda x: x.score)
        return hits[:top_k]

    # ---------------- 删除 ----------------
    def delete_by_doc(self, doc_id: str, kb_id: Optional[str] = None) -> int:
        if self.isolation and kb_id:
            names = [self._col(kb_id)]
        else:
            names = self._kb_collections()
        removed = 0
        for name in names:
            if not self.client.has_collection(name):
                continue
            try:
                self.client.delete(collection_name=name, filter=f'doc_id == "{doc_id}"')
                removed += 1
            except Exception as e:  # noqa: BLE001
                logger.warning("Milvus 删除失败(%s): %s", name, e)
        return removed

    def delete_by_kb(self, kb_id: str, tenant_id: Optional[str] = None) -> int:
        """按知识库干净擦除：隔离模式直接 drop 整个集合，根除索引污染。"""
        if self.isolation:
            name = self._col(kb_id)
            if self.client.has_collection(name):
                try:
                    self.client.drop_collection(name)
                    logger.info("Milvus 按库擦除集合 | %s", name)
                    return 1
                except Exception as e:  # noqa: BLE001
                    logger.warning("Milvus drop 集合失败(%s): %s", name, e)
                    return 0
            return 0
        # 非隔离模式：仅删除该 kb 的实体
        if not self.client.has_collection(self.shared):
            return 0
        try:
            self.client.delete(collection_name=self.shared, filter=f'kb_id == "{kb_id}"')
            return 1
        except Exception as e:  # noqa: BLE001
            logger.warning("Milvus 按库删除失败(%s): %s", self.shared, e)
            return 0

    # ---------------- 统计 ----------------
    def flush(self) -> None:
        """强制落盘，确保 count 反映最新写入。"""
        for name in self._kb_collections():
            try:
                self.client.flush(name)
            except Exception as e:  # noqa: BLE001
                logger.warning("Milvus flush 失败(忽略): %s", e)

    def count(self) -> int:
        total = 0
        for name in self._kb_collections():
            try:
                self.client.flush(name)
                stats = self.client.get_collection_stats(name)
                total += int(stats.get("row_count", 0))
            except Exception:  # noqa: BLE001
                continue
        return total
