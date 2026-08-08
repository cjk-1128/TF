"""Phase 1 数据迁移：SQLite(评测库) → MySQL(terraforge) + 向量重建进 Milvus。

在容器内运行：
    docker exec terraforge env PYTHONPATH=/app/backend python -m app.migrate_phase1

职责：
1. 关系数据：从 /app/data/terraforge.db 读取全部 tf_* 表，写入 MySQL（由 settings.DATABASE_URL 指定）。
   排除 tf_user（init_db 已 seed 管理员）与 alembic_version（init_db 已置位），避免主键/版本冲突。
   目标表非空则跳过（幂等，可重复执行）。
2. 向量：复用 /app/vectorstore/vectors.pkl（含 77 条完整 meta），灌入 Milvus 集合（默认 tf_chunks）。
   断言：向量后端确为 Milvus 且 count == pkl 条数，防止 Milvus 不可达时工厂静默降级 local 的假阳性。
"""
from __future__ import annotations

import logging
import pickle
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("migrate_phase1")

import numpy as np
from sqlalchemy import MetaData, create_engine, text

from app.core.config import settings
from app.vectorstore.base import VectorRecord
from app.vectorstore.factory import get_vector_store
from app.vectorstore.milvus_store import MilvusVectorStore

SRC_DB = "/app/data/terraforge.db"
PKL = "/app/vectorstore/vectors.pkl"
EXCLUDE = {"alembic_version", "tf_user"}


def migrate_relational() -> None:
    src = create_engine(f"sqlite:///{SRC_DB}")
    mysql = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
    src_meta = MetaData()
    src_meta.reflect(bind=src)
    tables = [t for t in src_meta.tables if t not in EXCLUDE]
    log.info("源库表(%d): %s", len(tables), tables)

    total = 0
    with src.connect() as s, mysql.begin() as d:  # begin() 退出自动提交，避免 connect() 的 with 块回滚导致数据丢失
        d.execute(text("SET FOREIGN_KEY_CHECKS=0"))
        for name in tables:
            tbl = src_meta.tables[name]
            cnt = d.execute(text(f"SELECT COUNT(*) FROM `{name}`")).scalar() or 0
            if cnt > 0:
                log.info("  [skip] %s 已存在 %d 行", name, cnt)
                continue
            rows = s.execute(tbl.select()).mappings().all()
            if rows:
                d.execute(tbl.insert(), [dict(r) for r in rows])
                total += len(rows)
                log.info("  [copy] %s %d 行", name, len(rows))
        d.execute(text("SET FOREIGN_KEY_CHECKS=1"))
    log.info("关系数据拷贝完成，共 %d 行", total)


def migrate_vectors() -> None:
    if not Path(PKL).exists():
        raise SystemExit(f"向量源文件缺失: {PKL}（请确认 docker_vector 卷已挂载）")
    with open(PKL, "rb") as f:
        data = pickle.load(f)
    ids = data["ids"]
    meta = data["meta"]
    matrix = np.asarray(data["matrix"], dtype=float)
    log.info("pkl 向量: %d 条, dim=%d", len(ids), matrix.shape[1])

    vs = get_vector_store()
    assert isinstance(vs, MilvusVectorStore), (
        f"向量后端不是 Milvus（实际 {type(vs).__name__}）——Milvus 可能不可达已静默降级 local，"
        "终止迁移以免假阳性。请检查 MILVUS_HOST/PORT 与 host.docker.internal 连通性。"
    )

    # 干净迁移：先删旧集合再重建，避免历史未 flush / 重复 upsert 导致 count 异常（如 154）
    if vs.client.has_collection(vs.collection):
        vs.client.drop_collection(vs.collection)
        log.info("已删除旧 Milvus 集合 %s（重建以保证向量数干净）", vs.collection)

    records = []
    for i, rid in enumerate(ids):
        m = meta[i]
        records.append(VectorRecord(
            id=rid,
            vector=[float(x) for x in matrix[i]],
            doc_id=m.get("doc_id", ""),
            kb_id=m.get("kb_id", ""),
            domain=m.get("domain", ""),
            discipline=m.get("discipline", ""),
            content=m.get("content", ""),
            meta={
                "section_path": m.get("section_path", ""),
                "clause_no": m.get("clause_no", ""),
                "page_no": int(m.get("page_no", 0) or 0),
            },
        ))
    n = vs.upsert(records)
    log.info("Milvus 写入 %d 条", n)

    vs.flush()  # 强制落盘，避免 row_count 读到未落盘的 0
    cnt = vs.count()
    assert cnt == len(ids), f"Milvus 向量数 {cnt} != 期望 {len(ids)}（可能部分写入失败）"
    log.info("Milvus 集合 %s 当前 %d 条 ✓", settings.MILVUS_COLLECTION, cnt)


if __name__ == "__main__":
    log.info("=== Phase 1 迁移开始 ===")
    log.info("MySQL 目标: ...@%s", settings.DATABASE_URL.split("@")[-1])
    log.info("VECTOR_BACKEND=%s | Milvus=%s:%s/%s",
             settings.VECTOR_BACKEND, settings.MILVUS_HOST, settings.MILVUS_PORT,
             settings.MILVUS_COLLECTION)
    migrate_relational()
    migrate_vectors()
    log.info("=== Phase 1 迁移完成 ✓ ===")
