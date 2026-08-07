"""身份与权限模型（Sprint4 RBAC）。

- User: 平台用户，持有 api_key，归属租户，拥有角色(admin/editor/viewer)。
- 鉴权通过 X-API-Key 头完成；角色决定对知识库/文档的读写权限。
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Index, String

from app.db.session import Base

ROLE_ADMIN = "admin"
ROLE_EDITOR = "editor"
ROLE_VIEWER = "viewer"
VALID_ROLES = (ROLE_ADMIN, ROLE_EDITOR, ROLE_VIEWER)


def _uid() -> str:
    return uuid.uuid4().hex


class User(Base):
    """平台用户（RBAC 主体）。"""
    __tablename__ = "tf_user"

    id = Column(String(32), primary_key=True, default=_uid)
    username = Column(String(64), nullable=False, unique=True, comment="登录名")
    display_name = Column(String(64), default="", comment="展示名")
    api_key = Column(String(64), nullable=False, unique=True, index=True,
                     comment="API 访问密钥（X-API-Key 头携带）")
    role = Column(String(16), nullable=False, default=ROLE_VIEWER,
                  comment="admin / editor / viewer")
    tenant_id = Column(String(32), nullable=False, default="default", index=True,
                       comment="所属租户")
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (Index("ix_user_tenant", "tenant_id"),)
