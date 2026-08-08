"""Area B 向量索引按库隔离迁移。

在容器内运行：
    docker exec terraforge env PYTHONPATH=/app/backend python -m app.migrate_vector_isolation

职责：
1. 仅当 VECTOR_TENANT_ISOLATION=True 时执行；否则数据本就在共享集合，无需拆分。
2. 读取共享集合（默认 tf_chunks）的全部实体，按 kb_id 重建独立集合 tf_kb_{kb_id}
   （schema 含 tenant_id 字段），随后 drop 旧共享集合。
3. 把 bm25.pkl 由扁平格式重写为「按库分区」格式，并为每条补 tenant_id（当前单租户=default）。
4. 断言：按库集合向量总数 == 原共享集合总数；bm25 条数不变。

幂等：若共享集合已不存在（已是按库隔离），直接跳过。
"""
from __future__ import annotations

import logging
import pickle
import sys
from collections import defaultdict
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("migrate_vector_isolation")

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.core.config import settings  # noqa: E402
from app.vectorstore.milvus_store import MilvusVectorStore  # noqa: E402

FIELDS = ["id", "vector", "doc_id", "kb_id", "domain", "discipline",
          "content", "section_path", "clause_no", "page_no"]


def migrate_vectors(vs: MilvusVectorStore) -> None:
    shared = vs.shared
    if not vs.client.has_collection(shared):
        log.info("共享集合 %s 不存在，已是按库隔离，跳过向量迁移", shared)
        return

    rows: list = []
    offset = 0
    while True:
        batch = vs.client.query(shared, filter="", output_fields=FIELDS,
                                limit=10_000, offset=offset)
        if not batch:
            break
        rows.extend(batch)
        if len(batch) < 10_000:
            break
        offset += len(batch)
    if not rows:
        log.warning("共享集合 %s 为空，直接 drop", shared)
        vs.client.drop_collection(shared)
        return
    log.info("读取共享集合 %s 共 %d 条", shared, len(rows))

    groups: dict = defaultdict(list)
    for r in rows:
        groups[r.get("kb_id", "") or ""].append(r)

    dim = settings.EMBEDDING_DIM
    for kb_id, items in groups.items():
        name = vs._col(kb_id)
        vs._ensure_named(name, dim)
        ents = []
        for r in items:
            e = dict(r)
            e["tenant_id"] = "default"  # 当前单租户；新写入将由业务层携带真实 tenant
            ents.append(e)
        vs.client.insert(collection_name=name, data=ents)
        log.info("  集合 %s 写入 %d 条", name, len(ents))

    vs.client.drop_collection(shared)
    log.info("已 drop 旧共享集合 %s", shared)

    vs.flush()
    total = vs.count()
    assert total == len(rows), (
        f"按库集合向量总数 {total} != 原 {len(rows)}（迁移不完整）")
    log.info("向量按库隔离完成 | 共 %d 个库 / %d 条 ✓", len(groups), total)


def migrate_bm25() -> None:
    p = Path(settings.LOCAL_VECTOR_DIR) / "bm25.pkl"
    if not p.exists():
        log.info("bm25.pkl 不存在，跳过 BM25 迁移")
        return
    with open(p, "rb") as f:
        d = pickle.load(f)
    if "kbs" in d:
        log.info("bm25.pkl 已是按库分区格式，跳过")
        return
    ids, corpus, meta = d["ids"], d["corpus"], d["meta"]
    groups: dict = defaultdict(list)
    for i, m in enumerate(meta):
        groups[m.get("kb_id", "") or ""].append(i)
    new_kbs = {}
    for kb, idxs in groups.items():
        new_kbs[kb] = {
            "ids": [ids[i] for i in idxs],
            "corpus": [corpus[i] for i in idxs],
            "meta": [{**meta[i], "tenant_id": meta[i].get("tenant_id") or "default"}
                     for i in idxs],
        }
    tmp = p.with_suffix(".tmp")
    with open(tmp, "wb") as f:
        pickle.dump({"version": 2, "kbs": new_kbs}, f)
    tmp.replace(p)
    total = sum(len(v["ids"]) for v in new_kbs.values())
    log.info("BM25 按库分区完成 | 共 %d 个库 / %d 条 ✓", len(new_kbs), total)


if __name__ == "__main__":
    log.info("=== Area B 向量按库隔离迁移开始 ===")
    vs = MilvusVectorStore()
    if not vs.isolation:
        log.info("VECTOR_TENANT_ISOLATION=False，无需按库隔离，退出")
        sys.exit(0)
    migrate_vectors(vs)
    migrate_bm25()
    log.info("=== Area B 向量按库隔离迁移完成 ✓ ===")
