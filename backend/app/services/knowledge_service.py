"""知识库与文档服务：入库全流程（解析 -> 切片 -> 向量化 -> 双索引写入）。"""
from __future__ import annotations

import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.constants import (SUPPORTED_EXTENSIONS, DocumentStatus,
                                GovernanceStatus, KnowledgeDomain)
from app.core.exceptions import DocumentParseError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.ingestion.chunker import ChunkData, EngineeringChunker
from app.ingestion.parsers import TextParser, parse_file
from app.llm.factory import get_embedding
from app.models.knowledge import Chunk, Document, KnowledgeBase
from app.retrieval.bm25_index import get_bm25_index
from app.schemas.knowledge import DocumentMeta, KnowledgeBaseCreate
from app.utils.text import (extract_keywords, extract_standard_code,
                            make_summary, sha256_bytes, sha256_text)
from app.vectorstore.base import VectorRecord
from app.vectorstore.factory import get_vector_store

logger = get_logger(__name__)


class KnowledgeService:
    def __init__(self, db: Session):
        self.db = db
        self.chunker = EngineeringChunker()

    # ==================== 知识库 ====================
    def create_kb(self, payload: KnowledgeBaseCreate) -> KnowledgeBase:
        exists = self.db.query(KnowledgeBase).filter(
            KnowledgeBase.name == payload.name).first()
        if exists:
            raise ValidationError(f"知识库名称已存在: {payload.name}")
        kb = KnowledgeBase(
            name=payload.name, domain=payload.domain.value,
            description=payload.description, owner=payload.owner,
            tags=payload.tags or [],
        )
        self.db.add(kb)
        self.db.flush()
        logger.info("创建知识库 | %s | %s", kb.name, kb.domain)
        return kb

    def list_kb(self, domain: Optional[str] = None, keyword: str = "") -> List[KnowledgeBase]:
        q = self.db.query(KnowledgeBase)
        if domain:
            q = q.filter(KnowledgeBase.domain == domain)
        if keyword:
            q = q.filter(KnowledgeBase.name.like(f"%{keyword}%"))
        return q.order_by(KnowledgeBase.created_at.desc()).all()

    def get_kb(self, kb_id: str) -> KnowledgeBase:
        kb = self.db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()
        if not kb:
            raise NotFoundError(f"知识库不存在: {kb_id}")
        return kb

    def delete_kb(self, kb_id: str) -> None:
        kb = self.get_kb(kb_id)
        for d in list(kb.documents):
            self._purge_indexes(d.id)
        self.db.delete(kb)
        logger.info("删除知识库 | %s", kb_id)

    def refresh_kb_stats(self, kb_id: str) -> None:
        kb = self.db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()
        if not kb:
            return
        kb.doc_count = self.db.query(func.count(Document.id)).filter(
            Document.kb_id == kb_id).scalar() or 0
        kb.chunk_count = self.db.query(func.count(Chunk.id)).filter(
            Chunk.kb_id == kb_id).scalar() or 0
        kb.updated_at = datetime.utcnow()

    # ==================== 文档 ====================
    def save_upload(self, kb_id: str, filename: str, data: bytes) -> Path:
        suffix = Path(filename).suffix.lower()
        if suffix not in SUPPORTED_EXTENSIONS:
            raise ValidationError(
                f"不支持的文件类型 {suffix}，支持: {', '.join(sorted(SUPPORTED_EXTENSIONS))}")
        if len(data) > settings.MAX_UPLOAD_MB * 1024 * 1024:
            raise ValidationError(f"文件超过 {settings.MAX_UPLOAD_MB}MB 限制")
        target_dir = Path(settings.UPLOAD_DIR) / kb_id
        target_dir.mkdir(parents=True, exist_ok=True)
        path = target_dir / f"{uuid.uuid4().hex[:8]}_{Path(filename).name}"
        path.write_bytes(data)
        return path

    async def ingest_file(self, kb_id: str, path: Path, meta: DocumentMeta,
                          original_name: str = "") -> Document:
        kb = self.get_kb(kb_id)
        data = path.read_bytes()
        file_hash = sha256_bytes(data)

        dup = self.db.query(Document).filter(
            Document.kb_id == kb_id, Document.file_hash == file_hash).first()
        if dup:
            logger.info("文档已存在，跳过入库 | %s", dup.title)
            return dup

        doc = Document(
            kb_id=kb_id,
            title=meta.title or Path(original_name or path.name).stem,
            file_name=original_name or path.name,
            file_path=str(path),
            file_type=path.suffix.lower().lstrip("."),
            file_size=len(data),
            file_hash=file_hash,
            standard_code=meta.standard_code,
            standard_name=meta.standard_name,
            discipline=meta.discipline.value if hasattr(meta.discipline, "value") else str(meta.discipline),
            project_name=meta.project_name,
            owner=meta.owner,
            version=meta.version,
            effective_date=meta.effective_date,
            expire_date=meta.expire_date,
            tags=meta.tags or [],
            status=DocumentStatus.PARSING.value,
        )
        self.db.add(doc)
        self.db.flush()

        try:
            parsed = parse_file(path)
            full_text = parsed.full_text
            if not meta.standard_code:
                doc.standard_code = extract_standard_code(full_text[:3000]) or ""
            doc.summary = make_summary(full_text, 220)
            doc.keywords = extract_keywords(full_text[:8000], 15)

            doc.status = DocumentStatus.CHUNKING.value
            chunks = self.chunker.split(parsed)
            if not chunks:
                raise DocumentParseError("未切分出任何有效内容")

            doc.status = DocumentStatus.EMBEDDING.value
            await self._persist_chunks(kb, doc, chunks)

            doc.status = DocumentStatus.READY.value
            doc.chunk_count = len(chunks)
            doc.error_msg = ""
            logger.info("文档入库完成 | %s | %d 切片", doc.title, len(chunks))
        except Exception as e:  # noqa: BLE001
            doc.status = DocumentStatus.FAILED.value
            doc.error_msg = str(e)[:900]
            logger.exception("文档入库失败 | %s", doc.title)
        finally:
            self.db.flush()
            self.refresh_kb_stats(kb_id)
        return doc

    async def ingest_text(self, kb_id: str, title: str, content: str,
                          meta: DocumentMeta) -> Document:
        kb = self.get_kb(kb_id)
        file_hash = sha256_text(content)
        dup = self.db.query(Document).filter(
            Document.kb_id == kb_id, Document.file_hash == file_hash).first()
        if dup:
            return dup

        doc = Document(
            kb_id=kb_id, title=title, file_name=f"{title}.md", file_type="md",
            file_size=len(content.encode()), file_hash=file_hash,
            standard_code=meta.standard_code or extract_standard_code(content[:2000]),
            standard_name=meta.standard_name,
            discipline=meta.discipline.value if hasattr(meta.discipline, "value") else str(meta.discipline),
            project_name=meta.project_name, owner=meta.owner, version=meta.version,
            effective_date=meta.effective_date, expire_date=meta.expire_date,
            tags=meta.tags or [], status=DocumentStatus.CHUNKING.value,
            summary=make_summary(content, 220),
            keywords=extract_keywords(content[:8000], 15),
        )
        self.db.add(doc)
        self.db.flush()

        try:
            parsed = TextParser.parse_text(content, source=title)
            chunks = self.chunker.split(parsed)
            if not chunks:
                raise DocumentParseError("内容过短，未切分出有效内容")
            await self._persist_chunks(kb, doc, chunks)
            doc.status = DocumentStatus.READY.value
            doc.chunk_count = len(chunks)
        except Exception as e:  # noqa: BLE001
            doc.status = DocumentStatus.FAILED.value
            doc.error_msg = str(e)[:900]
            logger.exception("文本入库失败 | %s", title)
        finally:
            self.db.flush()
            self.refresh_kb_stats(kb_id)
        return doc

    async def _persist_chunks(self, kb: KnowledgeBase, doc: Document,
                              chunks: List[ChunkData]) -> None:
        """落库 + 向量化 + 写双索引。"""
        rows: List[Chunk] = []
        for cd in chunks:
            rows.append(Chunk(
                doc_id=doc.id, kb_id=kb.id, domain=kb.domain, seq=cd.seq,
                content=cd.content, char_count=cd.char_count,
                section_path=cd.section_path, clause_no=cd.clause_no,
                page_no=cd.page_no, discipline=doc.discipline,
                is_mandatory=cd.is_mandatory, extra=cd.extra or {},
            ))
        self.db.add_all(rows)
        self.db.flush()

        embed = get_embedding()
        vectors = await embed.embed_texts([r.content for r in rows])

        vs = get_vector_store()
        vs.ensure_collection(len(vectors[0]) if vectors else settings.EMBEDDING_DIM)

        records, bm_items = [], []
        for r, v in zip(rows, vectors):
            meta = {
                "doc_id": doc.id, "kb_id": kb.id, "domain": kb.domain,
                "discipline": doc.discipline, "content": r.content,
                "doc_title": doc.title, "standard_code": doc.standard_code or "",
                "section_path": r.section_path, "clause_no": r.clause_no,
                "page_no": r.page_no, "is_mandatory": r.is_mandatory,
                "governance_status": doc.governance_status,
            }
            records.append(VectorRecord(
                id=r.id, vector=v, doc_id=doc.id, kb_id=kb.id, domain=kb.domain,
                discipline=doc.discipline, content=r.content, meta=meta))
            bm_items.append((r.id, r.content, meta))
            r.vector_id = r.id

        vs.upsert(records)
        get_bm25_index().add(bm_items)

    def list_documents(self, kb_id: Optional[str] = None, status: Optional[str] = None,
                       governance_status: Optional[str] = None, keyword: str = "",
                       offset: int = 0, limit: int = 20) -> Tuple[List[Document], int]:
        q = self.db.query(Document)
        if kb_id:
            q = q.filter(Document.kb_id == kb_id)
        if status:
            q = q.filter(Document.status == status)
        if governance_status:
            q = q.filter(Document.governance_status == governance_status)
        if keyword:
            like = f"%{keyword}%"
            q = q.filter((Document.title.like(like)) | (Document.standard_code.like(like)))
        total = q.count()
        items = q.order_by(Document.created_at.desc()).offset(offset).limit(limit).all()
        return items, total

    def get_document(self, doc_id: str) -> Document:
        d = self.db.query(Document).filter(Document.id == doc_id).first()
        if not d:
            raise NotFoundError(f"文档不存在: {doc_id}")
        return d

    def delete_document(self, doc_id: str) -> None:
        d = self.get_document(doc_id)
        kb_id = d.kb_id
        self._purge_indexes(doc_id)
        if d.file_path:
            Path(d.file_path).unlink(missing_ok=True)
        self.db.delete(d)
        self.db.flush()
        self.refresh_kb_stats(kb_id)
        logger.info("删除文档 | %s", doc_id)

    def update_document(self, doc_id: str, **fields) -> Document:
        d = self.get_document(doc_id)
        for k, v in fields.items():
            if v is None:
                continue
            setattr(d, k, v.value if hasattr(v, "value") else v)
        d.updated_at = datetime.utcnow()
        self.db.flush()
        # 治理状态变更需同步到索引元数据（影响重排降权）
        if "governance_status" in fields and fields["governance_status"] is not None:
            self._sync_governance_meta(d)
        return d

    def _sync_governance_meta(self, doc: Document) -> None:
        gov = doc.governance_status
        bm = get_bm25_index()
        for i, m in enumerate(bm._meta):  # noqa: SLF001
            if m.get("doc_id") == doc.id:
                m["governance_status"] = gov
        vs = get_vector_store()
        metas = getattr(vs, "_meta", None)
        if isinstance(metas, list):
            for m in metas:
                if m.get("doc_id") == doc.id:
                    m["governance_status"] = gov

    def _purge_indexes(self, doc_id: str) -> None:
        try:
            get_vector_store().delete_by_doc(doc_id)
        except Exception as e:  # noqa: BLE001
            logger.warning("向量库清理失败: %s", e)
        try:
            get_bm25_index().delete_by_doc(doc_id)
        except Exception as e:  # noqa: BLE001
            logger.warning("BM25 清理失败: %s", e)

    def list_chunks(self, doc_id: str, offset: int = 0, limit: int = 50,
                    keyword: str = ""):
        q = self.db.query(Chunk).filter(Chunk.doc_id == doc_id)
        if keyword:
            like = f"%{keyword}%"
            q = q.filter(or_(Chunk.content.like(like),
                             Chunk.section_path.like(like),
                             Chunk.clause_no.like(like)))
        total = q.count()
        items = q.order_by(Chunk.seq).offset(offset).limit(limit).all()
        return items, total

    async def reindex_document(self, doc_id: str) -> Document:
        """重建单文档索引（切分策略或 Embedding 模型变更后使用）。"""
        doc = self.get_document(doc_id)
        kb = self.get_kb(doc.kb_id)
        self._purge_indexes(doc_id)
        self.db.query(Chunk).filter(Chunk.doc_id == doc_id).delete()
        self.db.flush()

        if doc.file_path and Path(doc.file_path).exists():
            parsed = parse_file(Path(doc.file_path))
        else:
            raise DocumentParseError("原始文件缺失，无法重建索引")
        chunks = self.chunker.split(parsed)
        await self._persist_chunks(kb, doc, chunks)
        doc.chunk_count = len(chunks)
        doc.status = DocumentStatus.READY.value
        self.db.flush()
        self.refresh_kb_stats(kb.id)
        return doc

    def stats(self) -> dict:
        def _domain_docs(domain: str) -> int:
            return (self.db.query(func.count(Document.id))
                    .join(KnowledgeBase, KnowledgeBase.id == Document.kb_id)
                    .filter(KnowledgeBase.domain == domain).scalar() or 0)

        return {
            "kb_count": self.db.query(func.count(KnowledgeBase.id)).scalar() or 0,
            "doc_count": self.db.query(func.count(Document.id)).scalar() or 0,
            "chunk_count": self.db.query(func.count(Chunk.id)).scalar() or 0,
            "vector_count": get_vector_store().count(),
            "bm25_count": get_bm25_index().count(),
            "ready_docs": self.db.query(func.count(Document.id)).filter(
                Document.status == DocumentStatus.READY.value).scalar() or 0,
            "failed_docs": self.db.query(func.count(Document.id)).filter(
                Document.status == DocumentStatus.FAILED.value).scalar() or 0,
            "mandatory_chunks": self.db.query(func.count(Chunk.id)).filter(
                Chunk.is_mandatory.is_(True)).scalar() or 0,
            "standard_docs": _domain_docs(KnowledgeDomain.STANDARD.value),
            "case_docs": _domain_docs(KnowledgeDomain.CASE.value),
            "enterprise_docs": _domain_docs(KnowledgeDomain.ENTERPRISE.value),
        }
