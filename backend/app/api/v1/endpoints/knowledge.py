"""知识库与文档管理 API（Sprint4：多租户隔离 + 版本管理 + RBAC）。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from sqlalchemy.orm import Session

from app.core.constants import KnowledgeDomain
from app.core.logging import get_trace_id
from app.core.security import (can_access_kb, can_write_kb, get_current_user,
                               get_tenant_id)
from app.db.session import get_db
from app.models.identity import ROLE_ADMIN, User
from app.schemas.common import ApiResponse, PageData
from app.schemas.knowledge import (ChunkOut, DocumentMeta, DocumentOut,
                                   DocumentUpdate, KBVersionCreate, KBVersionDiff,
                                   KBVersionOut, KnowledgeBaseCreate,
                                   KnowledgeBaseOut, KnowledgeBaseUpdate,
                                   TextIngestRequest, UserOut)
from app.services import knowledge_service as ks_mod
from app.services.kb_version_service import KBVersionService

router = APIRouter()


def _kb_out(kb) -> KnowledgeBaseOut:
    o = KnowledgeBaseOut.model_validate(kb)
    try:
        o.domain_label = KnowledgeDomain(kb.domain).label
    except ValueError:
        o.domain_label = kb.domain
    return o


# ==================== 知识库 ====================
@router.post("/kb", response_model=ApiResponse[KnowledgeBaseOut], summary="创建知识库")
async def create_kb(payload: KnowledgeBaseCreate,
                    request: Request,
                    db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    tenant_id = payload.tenant_id or user.tenant_id
    if user.role != ROLE_ADMIN and tenant_id != user.tenant_id:
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="仅管理员可跨租户创建知识库")
    kb = ks_mod.KnowledgeService(db).create_kb(payload, tenant_id=tenant_id)
    return ApiResponse.ok(_kb_out(kb), "知识库创建成功", get_trace_id())


@router.get("/kb", response_model=ApiResponse[List[KnowledgeBaseOut]], summary="知识库列表")
def list_kb(domain: Optional[KnowledgeDomain] = None, keyword: str = "",
            request: Request = None,
            db: Session = Depends(get_db)):
    tenant_id = get_tenant_id(request) if request else None
    items = ks_mod.KnowledgeService(db).list_kb(
        domain.value if domain else None, keyword, tenant_id)
    return ApiResponse.ok([_kb_out(k) for k in items], trace_id=get_trace_id())


@router.get("/kb/{kb_id}", response_model=ApiResponse[KnowledgeBaseOut], summary="知识库详情")
def get_kb(kb_id: str, request: Request = None,
           db: Session = Depends(get_db)):
    tenant_id = get_tenant_id(request) if request else None
    kb = ks_mod.KnowledgeService(db).get_kb(kb_id)
    # 租户/可见性隔离：非 public 且非本租户不可见
    if kb.visibility != "public" and kb.tenant_id != tenant_id:
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="知识库不存在或不可访问")
    return ApiResponse.ok(_kb_out(kb), trace_id=get_trace_id())


@router.put("/kb/{kb_id}", response_model=ApiResponse[KnowledgeBaseOut], summary="更新知识库")
def update_kb(kb_id: str, payload: KnowledgeBaseUpdate,
              db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    svc = ks_mod.KnowledgeService(db)
    kb = svc.get_kb(kb_id)
    if not can_write_kb(user, kb):
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权修改该知识库")
    for k, v in payload.model_dump(exclude_none=True).items():
        setattr(kb, k, v)
    db.flush()
    return ApiResponse.ok(_kb_out(kb), "更新成功", get_trace_id())


@router.delete("/kb/{kb_id}", response_model=ApiResponse[dict], summary="删除知识库")
def delete_kb(kb_id: str, db: Session = Depends(get_db),
              user: User = Depends(get_current_user)):
    svc = ks_mod.KnowledgeService(db)
    kb = svc.get_kb(kb_id)
    if not can_write_kb(user, kb):
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权删除该知识库")
    svc.delete_kb(kb_id)
    return ApiResponse.ok({"deleted": kb_id}, "删除成功", get_trace_id())


# ==================== 版本管理（Sprint4）================
@router.post("/kb/{kb_id}/versions", response_model=ApiResponse[KBVersionOut],
             summary="为知识库创建版本检查点")
async def create_version(kb_id: str, payload: KBVersionCreate,
                        db: Session = Depends(get_db),
                        user: User = Depends(get_current_user)):
    svc = ks_mod.KnowledgeService(db)
    kb = svc.get_kb(kb_id)
    if not can_write_kb(user, kb):
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权操作该知识库")
    ver = KBVersionService(db).create_version(
        kb_id, label=payload.label, note=payload.note, created_by=user.api_key)
    return ApiResponse.ok(KBVersionOut.model_validate(ver), "版本已创建", get_trace_id())


@router.get("/kb/{kb_id}/versions", response_model=ApiResponse[List[KBVersionOut]],
            summary="知识库版本列表")
def list_versions(kb_id: str, request: Request = None,
                 db: Session = Depends(get_db)):
    tenant_id = get_tenant_id(request) if request else None
    kb = ks_mod.KnowledgeService(db).get_kb(kb_id)
    if kb.visibility != "public" and kb.tenant_id != tenant_id:
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="知识库不存在或不可访问")
    vers = KBVersionService(db).list_versions(kb_id)
    return ApiResponse.ok([KBVersionOut.model_validate(v) for v in vers], trace_id=get_trace_id())


@router.get("/kb/{kb_id}/versions/{vid}", response_model=ApiResponse[KBVersionOut],
            summary="知识库版本详情")
def get_version(kb_id: str, vid: str, request: Request = None,
                db: Session = Depends(get_db)):
    tenant_id = get_tenant_id(request) if request else None
    kb = ks_mod.KnowledgeService(db).get_kb(kb_id)
    if kb.visibility != "public" and kb.tenant_id != tenant_id:
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="知识库不存在或不可访问")
    ver = KBVersionService(db).get_version(vid)
    return ApiResponse.ok(KBVersionOut.model_validate(ver), trace_id=get_trace_id())


@router.post("/kb/{kb_id}/versions/{vid}/rollback",
             response_model=ApiResponse[KBVersionOut], summary="回滚到指定版本")
async def rollback_version(kb_id: str, vid: str,
                          db: Session = Depends(get_db),
                          user: User = Depends(get_current_user)):
    svc = ks_mod.KnowledgeService(db)
    kb = svc.get_kb(kb_id)
    if not can_write_kb(user, kb):
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权操作该知识库")
    ver = await KBVersionService(db).rollback(vid)
    return ApiResponse.ok(KBVersionOut.model_validate(ver), "已回滚", get_trace_id())


@router.get("/kb/{kb_id}/versions/{vid}/diff",
            response_model=ApiResponse[KBVersionDiff], summary="版本差异")
def version_diff(kb_id: str, vid: str, request: Request = None,
                 db: Session = Depends(get_db)):
    tenant_id = get_tenant_id(request) if request else None
    kb = ks_mod.KnowledgeService(db).get_kb(kb_id)
    if kb.visibility != "public" and kb.tenant_id != tenant_id:
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="知识库不存在或不可访问")
    diff = KBVersionService(db).version_diff(vid)
    return ApiResponse.ok(KBVersionDiff(**diff), trace_id=get_trace_id())


# ==================== 文档 ====================
@router.post("/documents/upload", response_model=ApiResponse[List[DocumentOut]],
             summary="上传工程资料（支持多文件）")
async def upload_documents(
    kb_id: str = Form(...),
    files: List[UploadFile] = File(...),
    meta: str = Form("{}", description="DocumentMeta 的 JSON 字符串"),
    request: Request = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    svc = ks_mod.KnowledgeService(db)
    kb = svc.get_kb(kb_id)
    if not can_write_kb(user, kb):
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权向该知识库上传")
    try:
        meta_obj = DocumentMeta(**json.loads(meta or "{}"))
    except Exception:  # noqa: BLE001
        meta_obj = DocumentMeta()

    out: List[DocumentOut] = []
    for f in files:
        data = await f.read()
        path = svc.save_upload(kb_id, f.filename or "unnamed", data)
        per = meta_obj.model_copy(deep=True)
        if len(files) > 1:
            per.title = None
        doc = await svc.ingest_file(kb_id, Path(path), per, original_name=f.filename or "")
        out.append(DocumentOut.model_validate(doc))
    return ApiResponse.ok(out, f"已处理 {len(out)} 个文件", get_trace_id())


@router.post("/documents/text", response_model=ApiResponse[DocumentOut],
             summary="文本直接入库（会议纪要/FAQ/复盘）")
async def ingest_text(payload: TextIngestRequest,
                     request: Request = None,
                     db: Session = Depends(get_db),
                     user: User = Depends(get_current_user)):
    svc = ks_mod.KnowledgeService(db)
    kb = svc.get_kb(payload.kb_id)
    if not can_write_kb(user, kb):
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权向该知识库上传")
    doc = await svc.ingest_text(payload.kb_id, payload.title, payload.content, payload.meta)
    return ApiResponse.ok(DocumentOut.model_validate(doc), "入库完成", get_trace_id())


@router.get("/documents", response_model=ApiResponse[PageData[DocumentOut]],
            summary="文档列表")
def list_documents(kb_id: Optional[str] = None, status: Optional[str] = None,
                   governance_status: Optional[str] = None, keyword: str = "",
                   page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=200),
                   request: Request = None,
                   db: Session = Depends(get_db)):
    tenant_id = get_tenant_id(request) if request else None
    items, total = ks_mod.KnowledgeService(db).list_documents(
        kb_id, status, governance_status, keyword, tenant_id,
        (page - 1) * page_size, page_size)
    return ApiResponse.ok(PageData[DocumentOut](
        items=[DocumentOut.model_validate(i) for i in items],
        total=total, page=page, page_size=page_size), trace_id=get_trace_id())


@router.get("/documents/{doc_id}", response_model=ApiResponse[DocumentOut], summary="文档详情")
def get_document(doc_id: str, request: Request = None,
                db: Session = Depends(get_db)):
    d = ks_mod.KnowledgeService(db).get_document(doc_id)
    if d.is_deleted:
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文档不存在")
    return ApiResponse.ok(DocumentOut.model_validate(d), trace_id=get_trace_id())


@router.put("/documents/{doc_id}", response_model=ApiResponse[DocumentOut],
            summary="更新文档元数据/治理状态")
def update_document(doc_id: str, payload: DocumentUpdate,
                   db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    svc = ks_mod.KnowledgeService(db)
    d = svc.get_document(doc_id)
    kb = svc.get_kb(d.kb_id)
    if not can_write_kb(user, kb):
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权修改该文档")
    d = svc.update_document(doc_id, **payload.model_dump(exclude_none=True))
    return ApiResponse.ok(DocumentOut.model_validate(d), "更新成功", get_trace_id())


@router.delete("/documents/{doc_id}", response_model=ApiResponse[dict], summary="删除文档")
def delete_document(doc_id: str, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    svc = ks_mod.KnowledgeService(db)
    d = svc.get_document(doc_id)
    kb = svc.get_kb(d.kb_id)
    if not can_write_kb(user, kb):
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权删除该文档")
    svc.delete_document(doc_id)
    return ApiResponse.ok({"deleted": doc_id}, "删除成功", get_trace_id())


@router.post("/documents/{doc_id}/reindex", response_model=ApiResponse[DocumentOut],
             summary="重建文档索引")
async def reindex_document(doc_id: str, db: Session = Depends(get_db),
                          user: User = Depends(get_current_user)):
    svc = ks_mod.KnowledgeService(db)
    d = svc.get_document(doc_id)
    kb = svc.get_kb(d.kb_id)
    if not can_write_kb(user, kb):
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权操作该文档")
    d = await svc.reindex_document(doc_id)
    return ApiResponse.ok(DocumentOut.model_validate(d), "重建完成", get_trace_id())


@router.get("/documents/{doc_id}/chunks", response_model=ApiResponse[PageData[ChunkOut]],
            summary="查看文档切片")
def list_chunks(doc_id: str, keyword: str = "", page: int = Query(1, ge=1),
                page_size: int = Query(50, ge=1, le=200),
                request: Request = None,
                db: Session = Depends(get_db)):
    items, total = ks_mod.KnowledgeService(db).list_chunks(
        doc_id, (page - 1) * page_size, page_size, keyword)
    return ApiResponse.ok(PageData[ChunkOut](
        items=[ChunkOut.model_validate(i) for i in items],
        total=total, page=page, page_size=page_size), trace_id=get_trace_id())


@router.get("/stats", response_model=ApiResponse[dict], summary="知识库总览统计")
def stats(request: Request = None,
          db: Session = Depends(get_db)):
    tenant_id = get_tenant_id(request) if request else None
    data = ks_mod.KnowledgeService(db).stats(tenant_id)
    return ApiResponse.ok(data, trace_id=get_trace_id())


# ==================== 当前用户 ====================
@router.get("/users/me", response_model=ApiResponse[UserOut], summary="当前用户信息")
def users_me(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return ApiResponse.ok(UserOut.model_validate(user), trace_id=get_trace_id())
