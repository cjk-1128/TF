"""知识库 / 文档 / 切片 Schema。"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.core.constants import (DisciplineTag, DocumentStatus,
                                GovernanceStatus, KnowledgeDomain)


# ---------------- 知识库 ----------------
class KnowledgeBaseCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    domain: KnowledgeDomain = KnowledgeDomain.STANDARD
    description: str = ""
    owner: str = ""
    tags: List[str] = []


class KnowledgeBaseUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    owner: Optional[str] = None
    tags: Optional[List[str]] = None
    is_active: Optional[bool] = None


class KnowledgeBaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    domain: str
    domain_label: str = ""
    description: str = ""
    owner: str = ""
    tags: List[str] = []
    doc_count: int = 0
    chunk_count: int = 0
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ---------------- 文档 ----------------
class DocumentMeta(BaseModel):
    """上传时可携带的工程元数据"""
    title: Optional[str] = None
    standard_code: str = ""
    standard_name: str = ""
    discipline: DisciplineTag = DisciplineTag.GENERAL
    project_name: str = ""
    owner: str = ""
    version: str = "1.0"
    effective_date: Optional[datetime] = None
    expire_date: Optional[datetime] = None
    tags: List[str] = []


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    kb_id: str
    title: str
    file_name: str = ""
    file_type: str = ""
    file_size: int = 0
    standard_code: str = ""
    standard_name: str = ""
    discipline: str = "general"
    project_name: str = ""
    governance_status: str = GovernanceStatus.VALID.value
    owner: str = ""
    version: str = "1.0"
    summary: str = ""
    keywords: List[str] = []
    tags: List[str] = []
    status: str = DocumentStatus.PENDING.value
    error_msg: str = ""
    chunk_count: int = 0
    effective_date: Optional[datetime] = None
    expire_date: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class DocumentUpdate(BaseModel):
    title: Optional[str] = None
    standard_code: Optional[str] = None
    standard_name: Optional[str] = None
    discipline: Optional[str] = None
    project_name: Optional[str] = None
    owner: Optional[str] = None
    version: Optional[str] = None
    governance_status: Optional[GovernanceStatus] = None
    tags: Optional[List[str]] = None
    summary: Optional[str] = None


class ChunkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    doc_id: str
    seq: int = 0
    content: str
    char_count: int = 0
    section_path: str = ""
    clause_no: str = ""
    page_no: int = 0
    is_mandatory: bool = False
    domain: str = ""


class TextIngestRequest(BaseModel):
    """纯文本入库（无需上传文件）"""
    kb_id: str
    title: str
    content: str = Field(..., min_length=10)
    meta: DocumentMeta = DocumentMeta()
