"""知识库版本模型（Sprint4 版本管理）。

每次「建版本」对当前知识库做一个检查点快照：记录文档数、切片数，以及
当时所有（未软删）文档/切片的 id 集合。回滚(rollback)时把知识库的
active_version_id 指回该版本，并据此恢复/隔离文档与切片（见 KBVersionService）。
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Index, Integer, JSON, String, Text

from app.db.session import Base


def _uid() -> str:
    return uuid.uuid4().hex


class KBVersion(Base):
    """知识库版本检查点。"""
    __tablename__ = "tf_kb_version"

    id = Column(String(32), primary_key=True, default=_uid)
    kb_id = Column(String(32), nullable=False, index=True)
    version_no = Column(Integer, nullable=False, default=1, comment="该知识库内的版本序号")
    label = Column(String(128), default="", comment="版本标签，如 v1 初版/规范更新")
    note = Column(Text, default="", comment="变更说明")

    # ---- 快照 ----
    doc_count = Column(Integer, default=0)
    chunk_count = Column(Integer, default=0)
    doc_ids = Column(JSON, nullable=True, comment="该版本包含的文档 id 列表")
    chunk_ids = Column(JSON, nullable=True, comment="该版本包含的切片 id 列表")

    created_by = Column(String(64), default="system", comment="触发建版本的用户/api_key")
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_kb_version_kb", "kb_id"),
        Index("ix_kb_version_kb_no", "kb_id", "version_no"),
    )
