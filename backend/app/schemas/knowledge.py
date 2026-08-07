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
    # Sprint4：多租户 / 可见性（创建时可省略，由服务端按当前租户填充）
    tenant_id: Optional[str] = None
    visibility: str = "tenant"          # public | tenant | private
    allowed_roles: Optional[List[str]] = None


class KnowledgeBaseUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    owner: Optional[str] = None
    tags: Optional[List[str]] = None
    is_active: Optional[bool] = None
    visibility: Optional[str] = None
    allowed_roles: Optional[List[str]] = None


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
    tenant_id: str = "default"
    visibility: str = "tenant"
    allowed_roles: Optional[List[str]] = None
    active_version_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ---------------- 版本管理（Sprint4）----------------
class KBVersionCreate(BaseModel):
    label: str = ""
    note: str = ""


class KBVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    kb_id: str
    version_no: int = 1
    label: str = ""
    note: str = ""
    doc_count: int = 0
    chunk_count: int = 0
    doc_ids: Optional[List[str]] = None
    chunk_ids: Optional[List[str]] = None
    created_by: str = "system"
    created_at: Optional[datetime] = None


class KBVersionDiff(BaseModel):
    version_id: str
    version_no: int
    removed_since_version: List[str] = []
    added_since_version: List[str] = []
    current_doc_count: int = 0
    version_doc_count: int = 0


# ---------------- 用户（Sprint4 RBAC）----------------
class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    username: str
    display_name: str = ""
    role: str = "viewer"
    tenant_id: str = "default"
    is_active: bool = True
    api_key: str = ""
    created_at: Optional[datetime] = None


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
