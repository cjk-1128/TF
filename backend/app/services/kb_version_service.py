"""知识库版本管理（Sprint4）。

把「建版本」做成检查点快照，把「回滚」做成基于快照的文档/切片软删隔离与恢复：
- 建版本：记录当前（未软删）文档/切片计数与 id 列表，并把 KB.active_version_id 指向它。
- 回滚：把当前活跃但不在版本中的文档软删（并移出索引），把版本中但当前已软删的文档恢复
  （重建索引），最后把 active_version_id 指回该版本。
"""
from __future__ import annotations

from typing import List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.models.knowledge import Chunk, Document, KnowledgeBase
from app.models.version import KBVersion
from app.services.knowledge_service import KnowledgeService

logger = get_logger(__name__)


class KBVersionService:
    def __init__(self, db: Session):
        self.db = db

    def create_version(self, kb_id: str, label: str = "", note: str = "",
                       created_by: str = "system") -> KBVersion:
        kb = self.db.query(KnowledgeBase).filter(
            KnowledgeBase.id == kb_id, KnowledgeBase.is_active.is_(True)).first()
        if not kb:
            raise NotFoundError(f"知识库不存在: {kb_id}")

        docs = self.db.query(Document).filter(
            Document.kb_id == kb_id, Document.is_deleted.is_(False)).all()
        chunks = self.db.query(Chunk).filter(
            Chunk.kb_id == kb_id, Chunk.is_deleted.is_(False)).all()
        doc_ids = [d.id for d in docs]
        chunk_ids = [c.id for c in chunks]

        last_no = self.db.query(func.max(KBVersion.version_no)).filter(
            KBVersion.kb_id == kb_id).scalar() or 0
        ver = KBVersion(
            kb_id=kb_id, version_no=last_no + 1, label=label or f"v{last_no + 1}",
            note=note, doc_count=len(doc_ids), chunk_count=len(chunk_ids),
            doc_ids=doc_ids, chunk_ids=chunk_ids, created_by=created_by,
        )
        self.db.add(ver)
        self.db.flush()
        kb.active_version_id = ver.id
        logger.info("知识库建版本 | kb=%s v%d | docs=%d chunks=%d",
                    kb_id, ver.version_no, len(doc_ids), len(chunk_ids))
        return ver

    def list_versions(self, kb_id: str) -> List[KBVersion]:
        return self.db.query(KBVersion).filter(KBVersion.kb_id == kb_id).order_by(
            KBVersion.version_no.desc()).all()

    def get_version(self, version_id: str) -> KBVersion:
        ver = self.db.query(KBVersion).filter(KBVersion.id == version_id).first()
        if not ver:
            raise NotFoundError(f"版本不存在: {version_id}")
        return ver

    async def rollback(self, version_id: str) -> KBVersion:
        ver = self.get_version(version_id)
        kb = self.db.query(KnowledgeBase).filter(
            KnowledgeBase.id == ver.kb_id, KnowledgeBase.is_active.is_(True)).first()
        if not kb:
            raise NotFoundError(f"知识库不存在: {ver.kb_id}")

        current_doc_ids = set(d.id for d in self.db.query(Document).filter(
            Document.kb_id == ver.kb_id, Document.is_deleted.is_(False)).all())
        version_doc_ids = set(ver.doc_ids or [])

        # 当前有、版本没有 -> 软删
        to_delete = current_doc_ids - version_doc_ids
        ks = KnowledgeService(self.db)
        for doc_id in to_delete:
            ks.delete_document(doc_id)

        # 版本有、当前已软删 -> 恢复并重建索引
        to_restore = version_doc_ids - current_doc_ids
        for doc_id in to_restore:
            await ks.restore_document(doc_id)

        kb.active_version_id = ver.id
        self.db.flush()
        logger.info("知识库回滚 | kb=%s -> v%d | 软删%d 恢复%d",
                    kb.id, ver.version_no, len(to_delete), len(to_restore))
        return ver

    def version_diff(self, version_id: str) -> dict:
        """对比指定版本与「当前活跃状态」的文档差异。"""
        ver = self.get_version(version_id)
        current_doc_ids = set(d.id for d in self.db.query(Document).filter(
            Document.kb_id == ver.kb_id).all())
        version_doc_ids = set(ver.doc_ids or [])
        return {
            "version_id": ver.id,
            "version_no": ver.version_no,
            "removed_since_version": sorted(version_doc_ids - current_doc_ids),
            "added_since_version": sorted(current_doc_ids - version_doc_ids),
            "current_doc_count": len(current_doc_ids),
            "version_doc_count": len(version_doc_ids),
        }
