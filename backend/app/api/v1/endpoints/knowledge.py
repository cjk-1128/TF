"""知识库与文档管理 API。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy.orm import Session

from app.core.constants import KnowledgeDomain
from app.core.logging import get_trace_id
from app.db.session import get_db
from app.schemas.common import ApiResponse, PageData
from app.schemas.knowledge import (ChunkOut, DocumentMeta, DocumentOut,
                                   DocumentUpdate, KnowledgeBaseCreate,
                                   KnowledgeBaseOut, KnowledgeBaseUpdate,
                                   TextIngestRequest)
from app.services.knowledge_service import KnowledgeService

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
def create_kb(payload: KnowledgeBaseCreate, db: Session = Depends(get_db)):
    kb = KnowledgeService(db).create_kb(payload)
    return ApiResponse.ok(_kb_out(kb), "知识库创建成功", get_trace_id())


@router.get("/kb", response_model=ApiResponse[List[KnowledgeBaseOut]], summary="知识库列表")
def list_kb(domain: Optional[KnowledgeDomain] = None, keyword: str = "",
            db: Session = Depends(get_db)):
    items = KnowledgeService(db).list_kb(domain.value if domain else None, keyword)
    return ApiResponse.ok([_kb_out(k) for k in items], trace_id=get_trace_id())


@router.get("/kb/{kb_id}", response_model=ApiResponse[KnowledgeBaseOut], summary="知识库详情")
def get_kb(kb_id: str, db: Session = Depends(get_db)):
    return ApiResponse.ok(_kb_out(KnowledgeService(db).get_kb(kb_id)), trace_id=get_trace_id())


@router.put("/kb/{kb_id}", response_model=ApiResponse[KnowledgeBaseOut], summary="更新知识库")
def update_kb(kb_id: str, payload: KnowledgeBaseUpdate, db: Session = Depends(get_db)):
    svc = KnowledgeService(db)
    kb = svc.get_kb(kb_id)
    for k, v in payload.model_dump(exclude_none=True).items():
        setattr(kb, k, v)
    db.flush()
    return ApiResponse.ok(_kb_out(kb), "更新成功", get_trace_id())


@router.delete("/kb/{kb_id}", response_model=ApiResponse[dict], summary="删除知识库")
def delete_kb(kb_id: str, db: Session = Depends(get_db)):
    KnowledgeService(db).delete_kb(kb_id)
    return ApiResponse.ok({"deleted": kb_id}, "删除成功", get_trace_id())


# ==================== 文档 ====================
@router.post("/documents/upload", response_model=ApiResponse[List[DocumentOut]],
             summary="上传工程资料（支持多文件）")
async def upload_documents(
    kb_id: str = Form(...),
    files: List[UploadFile] = File(...),
    meta: str = Form("{}", description="DocumentMeta 的 JSON 字符串"),
    db: Session = Depends(get_db),
):
    svc = KnowledgeService(db)
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
            per.title = None  # 多文件时用各自文件名
        doc = await svc.ingest_file(kb_id, Path(path), per, original_name=f.filename or "")
        out.append(DocumentOut.model_validate(doc))
    return ApiResponse.ok(out, f"已处理 {len(out)} 个文件", get_trace_id())


@router.post("/documents/text", response_model=ApiResponse[DocumentOut],
             summary="文本直接入库（会议纪要/FAQ/复盘）")
async def ingest_text(payload: TextIngestRequest, db: Session = Depends(get_db)):
    doc = await KnowledgeService(db).ingest_text(
        payload.kb_id, payload.title, payload.content, payload.meta)
    return ApiResponse.ok(DocumentOut.model_validate(doc), "入库完成", get_trace_id())


@router.get("/documents", response_model=ApiResponse[PageData[DocumentOut]],
            summary="文档列表")
def list_documents(kb_id: Optional[str] = None, status: Optional[str] = None,
                   governance_status: Optional[str] = None, keyword: str = "",
                   page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=200),
                   db: Session = Depends(get_db)):
    items, total = KnowledgeService(db).list_documents(
        kb_id, status, governance_status, keyword, (page - 1) * page_size, page_size)
    return ApiResponse.ok(PageData[DocumentOut](
        items=[DocumentOut.model_validate(i) for i in items],
        total=total, page=page, page_size=page_size), trace_id=get_trace_id())


@router.get("/documents/{doc_id}", response_model=ApiResponse[DocumentOut], summary="文档详情")
def get_document(doc_id: str, db: Session = Depends(get_db)):
    d = KnowledgeService(db).get_document(doc_id)
    return ApiResponse.ok(DocumentOut.model_validate(d), trace_id=get_trace_id())


@router.put("/documents/{doc_id}", response_model=ApiResponse[DocumentOut],
            summary="更新文档元数据/治理状态")
def update_document(doc_id: str, payload: DocumentUpdate, db: Session = Depends(get_db)):
    d = KnowledgeService(db).update_document(doc_id, **payload.model_dump(exclude_none=True))
    return ApiResponse.ok(DocumentOut.model_validate(d), "更新成功", get_trace_id())


@router.delete("/documents/{doc_id}", response_model=ApiResponse[dict], summary="删除文档")
def delete_document(doc_id: str, db: Session = Depends(get_db)):
    KnowledgeService(db).delete_document(doc_id)
    return ApiResponse.ok({"deleted": doc_id}, "删除成功", get_trace_id())


@router.post("/documents/{doc_id}/reindex", response_model=ApiResponse[DocumentOut],
             summary="重建文档索引")
async def reindex_document(doc_id: str, db: Session = Depends(get_db)):
    d = await KnowledgeService(db).reindex_document(doc_id)
    return ApiResponse.ok(DocumentOut.model_validate(d), "重建完成", get_trace_id())


@router.get("/documents/{doc_id}/chunks", response_model=ApiResponse[PageData[ChunkOut]],
            summary="查看文档切片")
def list_chunks(doc_id: str, keyword: str = "", page: int = Query(1, ge=1),
                page_size: int = Query(50, ge=1, le=200), db: Session = Depends(get_db)):
    items, total = KnowledgeService(db).list_chunks(
        doc_id, (page - 1) * page_size, page_size, keyword)
    return ApiResponse.ok(PageData[ChunkOut](
        items=[ChunkOut.model_validate(i) for i in items],
        total=total, page=page, page_size=page_size), trace_id=get_trace_id())


@router.get("/stats", response_model=ApiResponse[dict], summary="知识库总览统计")
def stats(db: Session = Depends(get_db)):
    return ApiResponse.ok(KnowledgeService(db).stats(), trace_id=get_trace_id())
