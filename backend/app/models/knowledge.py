"""知识库领域模型：知识库 -> 文档 -> 切片。"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (JSON, Boolean, Column, DateTime, Float, ForeignKey,
                        Index, Integer, String, Text)
from sqlalchemy.orm import relationship

from app.core.constants import (DocumentStatus, GovernanceStatus,
                                KnowledgeDomain)
from app.db.session import Base


def _uid() -> str:
    return uuid.uuid4().hex


class KnowledgeBase(Base):
    """知识库（对应三大知识域下的具体库）"""
    __tablename__ = "tf_knowledge_base"

    id = Column(String(32), primary_key=True, default=_uid)
    name = Column(String(128), nullable=False, comment="知识库名称")
    domain = Column(String(32), nullable=False, default=KnowledgeDomain.STANDARD.value,
                    comment="知识域: standard/case/enterprise")
    description = Column(Text, default="")
    owner = Column(String(64), default="", comment="维护负责人")
    tags = Column(JSON, default=list)
    doc_count = Column(Integer, default=0)
    chunk_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    documents = relationship("Document", back_populates="kb", cascade="all, delete-orphan")

    __table_args__ = (Index("idx_kb_domain", "domain"),)


class Document(Base):
    """工程资料文档"""
    __tablename__ = "tf_document"

    id = Column(String(32), primary_key=True, default=_uid)
    kb_id = Column(String(32), ForeignKey("tf_knowledge_base.id", ondelete="CASCADE"),
                   nullable=False)
    title = Column(String(256), nullable=False)
    file_name = Column(String(256), default="")
    file_path = Column(String(512), default="")
    file_type = Column(String(16), default="")
    file_size = Column(Integer, default=0)
    file_hash = Column(String(64), default="", comment="内容SHA256，用于去重")

    # ---- 工程元数据（土木行业特有）----
    standard_code = Column(String(64), default="", comment="规范编号 如 GB50204-2015")
    standard_name = Column(String(256), default="", comment="规范名称")
    discipline = Column(String(32), default="general", comment="专业分部")
    project_name = Column(String(256), default="", comment="所属项目")
    effective_date = Column(DateTime, nullable=True, comment="实施日期")
    expire_date = Column(DateTime, nullable=True, comment="废止日期")

    # ---- 治理字段（Stage7）----
    governance_status = Column(String(32), default=GovernanceStatus.VALID.value)
    owner = Column(String(64), default="", comment="文档负责人")
    version = Column(String(32), default="1.0")
    summary = Column(Text, default="")
    keywords = Column(JSON, default=list)
    tags = Column(JSON, default=list)

    status = Column(String(16), default=DocumentStatus.PENDING.value)
    error_msg = Column(Text, default="")
    chunk_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    kb = relationship("KnowledgeBase", back_populates="documents")
    chunks = relationship("Chunk", back_populates="document", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_doc_kb", "kb_id"),
        Index("idx_doc_status", "status"),
        Index("idx_doc_std_code", "standard_code"),
        Index("idx_doc_hash", "file_hash"),
    )


class Chunk(Base):
    """文档切片（检索最小单元）"""
    __tablename__ = "tf_chunk"

    id = Column(String(32), primary_key=True, default=_uid)
    doc_id = Column(String(32), ForeignKey("tf_document.id", ondelete="CASCADE"), nullable=False)
    kb_id = Column(String(32), nullable=False, index=True)
    domain = Column(String(32), nullable=False, default=KnowledgeDomain.STANDARD.value)

    seq = Column(Integer, default=0, comment="文档内顺序")
    content = Column(Text, nullable=False)
    char_count = Column(Integer, default=0)

    # ---- 定位信息（用于引用增强 Stage6）----
    section_path = Column(String(512), default="", comment="章节路径 如 5.2.1 混凝土养护")
    clause_no = Column(String(64), default="", comment="条文号")
    page_no = Column(Integer, default=0)
    discipline = Column(String(32), default="general")

    is_mandatory = Column(Boolean, default=False, comment="是否强制性条文")
    vector_id = Column(String(64), default="", comment="向量库主键")
    extra = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)

    document = relationship("Document", back_populates="chunks")

    __table_args__ = (
        Index("idx_chunk_doc", "doc_id"),
        Index("idx_chunk_domain", "domain"),
    )
