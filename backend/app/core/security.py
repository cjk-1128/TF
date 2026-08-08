"""Sprint4 安全层：多租户上下文 + RBAC 鉴权。

- 租户：请求头 X-Tenant-Id 指定当前租户（默认 default）。所有数据读写按 tenant_id 隔离。
- 鉴权：写操作与问答必须携带 X-API-Key（对应 tf_user.api_key）。无效/缺失返回 401。
- 权限：admin 可访问全部知识库；其余用户按 KB 可见性(public/tenant/private) + 角色判定。
"""
from __future__ import annotations

from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.db.session import get_db
from app.models.identity import ROLE_ADMIN, User
from app.models.knowledge import KnowledgeBase

logger = get_logger(__name__)


def get_tenant_id(request: Request) -> str:
    """从请求头解析当前租户，缺省为默认租户。"""
    tid = (request.headers.get(settings.TENANT_HEADER) or "").strip()
    return tid or settings.DEFAULT_TENANT_ID


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """解析并校验当前用户；RBAC 关闭时返回虚拟 admin。"""
    if not settings.RBAC_ENABLED:
        return _virtual_admin()

    key = (request.headers.get(settings.API_KEY_HEADER) or "").strip()
    if not key:
        raise _unauthorized("缺少 API Key（请在请求头携带 X-API-Key）")

    user = db.query(User).filter(
        User.api_key == key, User.is_active.is_(True)).first()
    if not user:
        raise _unauthorized("API Key 无效或用户已禁用")
    return user


def _virtual_admin() -> User:
    """RBAC 关闭时的占位管理员（不落库）。"""
    u = User(username="__admin__", api_key="", role=ROLE_ADMIN,
             tenant_id=settings.DEFAULT_TENANT_ID)
    u.id = "virtual-admin"
    return u


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "ApiKey realm=\"terraforge\""},
    )


def can_access_kb(user: User, kb: KnowledgeBase) -> bool:
    """判断用户是否可访问某知识库（读/写共用判定）。"""
    if user.role == ROLE_ADMIN:
        return True
    if kb.visibility == "public":
        return True
    if kb.visibility == "tenant" and kb.tenant_id == user.tenant_id:
        return True
    if kb.visibility == "private":
        allowed = kb.allowed_roles or []
        if user.role in allowed:
            return True
    return False


def can_write_kb(user: User, kb: KnowledgeBase) -> bool:
    """写入/删除权限：admin 或 editor（同租户且非 private 受限）。"""
    if user.role == ROLE_ADMIN:
        return True
    if kb.visibility == "public":
        return user.role in (ROLE_ADMIN, "editor")
    if kb.visibility == "tenant" and kb.tenant_id == user.tenant_id:
        return user.role in (ROLE_ADMIN, "editor")
    if kb.visibility == "private":
        return user.role in (list(kb.allowed_roles or []) + [ROLE_ADMIN])
    return False


def get_kb_access(kb_id: str, request: Request,
                  db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)) -> KnowledgeBase:
    """FastAPI 依赖：加载知识库并鉴权（读/写通用）。无权限返回 403。"""
    kb = db.query(KnowledgeBase).filter(
        KnowledgeBase.id == kb_id, KnowledgeBase.is_active.is_(True)).first()
    if not kb:
        raise HTTPException(status_code=404, detail=f"知识库不存在: {kb_id}")
    if not can_access_kb(user, kb):
        raise HTTPException(status_code=403, detail="无权访问该知识库")
    return kb
