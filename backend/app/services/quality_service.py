"""Sprint6 知识库质量巡检 Agent
================================
定位：在治理服务的"文档级体检"之上，补齐"切片级 + 检索级"的质量巡检，
产出可随时间对比的质量快照，并可把问题一键采纳为治理任务，形成闭环。

巡检维度
- 静态（无需检索）：
  · oversized_chunk   切片过大（稀释相关性，重排/生成成本高）
  · tiny_chunk        切片过碎（语义不完整，易产生噪声命中）
  · missing_standard_code  规范域文档缺规范编号（无法精确溯源）
  · missing_location  切片缺章节/条文定位（引用无法定位到条款）
- 语义（Embedding）：
  · duplicate_chunk   近重复切片（冗余、检索互相挤占、答案重复）
  · orphan_chunk      孤立切片（与全库其他切片相似度极低，疑似跑题/噪声）
- 检索（黄金集探针，可选）：
  · low_recall_intent 某意图下黄金集平均 Recall@5 偏低（覆盖薄弱）
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import numpy as np
from sqlalchemy.orm import Session

from app.core.constants import KnowledgeDomain
from app.core.logging import get_logger
from app.llm.factory import get_embedding
from app.models.governance import GovernanceTask
from app.models.knowledge import Chunk, Document, KnowledgeBase
from app.models.quality import QualityReport
from app.schemas.quality import QualityIssue

logger = get_logger(__name__)

SEV_WEIGHT = {"high": 6.0, "medium": 3.0, "low": 1.0}
# 语义相似度巡检的规模上限（超过则跳过 O(n^2) 计算，避免拖垮请求）
MAX_SEMANTIC_CHUNKS = 2500


class QualityInspector:
    def __init__(self, db: Session):
        self.db = db

    # ---------------------------------------------------------------- 主流程
    async def inspect(self, tenant_id: str = "default", kb_id: Optional[str] = None,
                      dup_threshold: float = 0.92, orphan_threshold: float = 0.12,
                      max_chunk_chars: int = 1200, min_chunk_chars: int = 40,
                      run_recall_probe: bool = True,
                      persist: bool = True, max_issue_detail: int = 200) -> dict:
        # 1) 取切片（软删的不参与）
        cq = (self.db.query(Chunk)
              .filter(Chunk.tenant_id == tenant_id, Chunk.is_deleted.is_(False)))
        if kb_id:
            cq = cq.filter(Chunk.kb_id == kb_id)
        chunks: List[Chunk] = cq.all()

        # 文档标题映射（明细展示用）
        doc_ids = {c.doc_id for c in chunks}
        docs: Dict[str, Document] = {}
        if doc_ids:
            for d in (self.db.query(Document)
                      .filter(Document.id.in_(doc_ids)).all()):
                docs[d.id] = d

        issues: List[QualityIssue] = []
        issues += self._static_checks(chunks, docs, max_chunk_chars, min_chunk_chars)
        issues += self._missing_standard_checks(chunks, docs)

        # 2) 语义巡检（近重复 + 孤立）
        semantic_note = ""
        if 2 <= len(chunks) <= MAX_SEMANTIC_CHUNKS:
            issues += await self._semantic_checks(
                chunks, docs, dup_threshold, orphan_threshold)
        elif len(chunks) > MAX_SEMANTIC_CHUNKS:
            semantic_note = f"切片数 {len(chunks)} 超过 {MAX_SEMANTIC_CHUNKS}，本次跳过语义近重复/孤立巡检"

        # 3) 检索覆盖探针（低召回意图）
        intent_probe: Dict[str, float] = {}
        if run_recall_probe:
            probe_issues, intent_probe = await self._recall_probe(tenant_id, kb_id)
            issues += probe_issues

        # 4) 评分 + 建议
        total_docs = len(docs) if docs else self._count_docs(tenant_id, kb_id)
        total_chunks = len(chunks)
        score = self._score(issues, total_chunks)
        counts = Counter(i.issue_type for i in issues)
        suggestions = self._suggestions(counts, intent_probe, semantic_note)

        # 明细截断（按严重度排序后保存）
        sev_rank = {"high": 0, "medium": 1, "low": 2}
        issues_sorted = sorted(issues, key=lambda x: sev_rank.get(x.severity, 3))
        issues_kept = issues_sorted[:max_issue_detail]

        result = {
            "kb_id": kb_id or "",
            "tenant_id": tenant_id,
            "scope": "kb" if kb_id else "all",
            "score": round(score, 1),
            "total_docs": total_docs,
            "total_chunks": total_chunks,
            "issue_count": len(issues),
            "issue_counts": dict(counts),
            "issues": [i.model_dump() for i in issues_kept],
            "suggestions": suggestions,
            "created_at": datetime.utcnow(),
        }

        if persist:
            rep = QualityReport(
                kb_id=kb_id or "", tenant_id=tenant_id,
                scope=result["scope"], score=result["score"],
                total_docs=total_docs, total_chunks=total_chunks,
                issue_count=len(issues), issue_counts=dict(counts),
                issues=result["issues"], suggestions=suggestions,
            )
            self.db.add(rep)
            self.db.flush()
            result["id"] = rep.id
            logger.info("质量巡检落库 | report=%s | score=%.1f | issues=%d",
                        rep.id, score, len(issues))
        return result

    # ---------------------------------------------------------------- 静态检查
    def _static_checks(self, chunks: List[Chunk], docs: Dict[str, Document],
                       max_chars: int, min_chars: int) -> List[QualityIssue]:
        out: List[QualityIssue] = []
        for c in chunks:
            n = c.char_count or len(c.content or "")
            title = docs.get(c.doc_id).title if docs.get(c.doc_id) else ""
            if n > max_chars:
                out.append(QualityIssue(
                    issue_type="oversized_chunk", severity="low",
                    chunk_id=c.id, doc_id=c.doc_id, doc_title=title, kb_id=c.kb_id,
                    detail=f"切片长度 {n} 字，超过阈值 {max_chars}，可能稀释相关性",
                    suggestion="按语义/条款重新切分为更小片段，提升重排精度",
                    extra={"char_count": n},
                ))
            elif n < min_chars:
                out.append(QualityIssue(
                    issue_type="tiny_chunk", severity="low",
                    chunk_id=c.id, doc_id=c.doc_id, doc_title=title, kb_id=c.kb_id,
                    detail=f"切片长度仅 {n} 字，语义不完整，易产生噪声命中",
                    suggestion="与相邻切片合并，或清理为无效碎片",
                    extra={"char_count": n},
                ))
            # 缺定位：既无章节路径也无条文号
            if not (c.section_path or "").strip() and not (c.clause_no or "").strip():
                out.append(QualityIssue(
                    issue_type="missing_location", severity="low",
                    chunk_id=c.id, doc_id=c.doc_id, doc_title=title, kb_id=c.kb_id,
                    detail="切片缺少章节路径与条文号，引用无法精确定位到条款",
                    suggestion="解析时补齐 section_path/clause_no，或按标题层级重切",
                ))
        return out

    def _missing_standard_checks(self, chunks: List[Chunk],
                                 docs: Dict[str, Document]) -> List[QualityIssue]:
        """规范域文档缺规范编号（每个文档只报一次）。"""
        out: List[QualityIssue] = []
        seen: set[str] = set()
        for c in chunks:
            if c.domain != KnowledgeDomain.STANDARD.value:
                continue
            d = docs.get(c.doc_id)
            if not d or d.id in seen:
                continue
            if not (d.standard_code or "").strip():
                seen.add(d.id)
                out.append(QualityIssue(
                    issue_type="missing_standard_code", severity="medium",
                    chunk_id="", doc_id=d.id, doc_title=d.title, kb_id=d.kb_id,
                    detail="规范类文档缺少规范编号（standard_code），无法精确溯源与去重",
                    suggestion="补录规范编号（如 GB50204-2015）与实施/废止日期",
                ))
        return out

    # ---------------------------------------------------------------- 语义检查
    async def _semantic_checks(self, chunks: List[Chunk], docs: Dict[str, Document],
                               dup_threshold: float,
                               orphan_threshold: float) -> List[QualityIssue]:
        embed = get_embedding()
        texts = [(c.content or "")[:1000] for c in chunks]
        vectors = await embed.embed_texts(texts)
        mat = np.asarray(vectors, dtype=np.float32)
        # L2 归一化 → 点积即余弦
        norms = np.linalg.norm(mat, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        mat = mat / norms
        sim = mat @ mat.T
        np.fill_diagonal(sim, -1.0)  # 排除自身

        out: List[QualityIssue] = []
        n = len(chunks)
        # 近重复：仅取上三角，避免重复报对
        dup_reported: set[str] = set()
        for i in range(n):
            row = sim[i]
            j = int(np.argmax(row))
            max_sim = float(row[j])
            ci = chunks[i]
            title_i = docs.get(ci.doc_id).title if docs.get(ci.doc_id) else ""
            # 孤立切片：与全库最相似者都很低
            if max_sim < orphan_threshold:
                out.append(QualityIssue(
                    issue_type="orphan_chunk", severity="medium",
                    chunk_id=ci.id, doc_id=ci.doc_id, doc_title=title_i, kb_id=ci.kb_id,
                    detail=f"与全库其他切片最大相似度仅 {max_sim:.3f}，疑似跑题/噪声内容",
                    suggestion="人工确认是否属于本库主题，非主题内容建议移除或转移知识库",
                    extra={"max_sim": round(max_sim, 4)},
                ))
            # 近重复：i<j 只报一次
            if max_sim >= dup_threshold and j > i:
                pair_key = f"{min(i, j)}-{max(i, j)}"
                if pair_key in dup_reported:
                    continue
                dup_reported.add(pair_key)
                cj = chunks[j]
                title_j = docs.get(cj.doc_id).title if docs.get(cj.doc_id) else ""
                out.append(QualityIssue(
                    issue_type="duplicate_chunk", severity="medium",
                    chunk_id=ci.id, doc_id=ci.doc_id, doc_title=title_i, kb_id=ci.kb_id,
                    detail=(f"与切片 {cj.id[:8]}（{title_j}）相似度 {max_sim:.3f}，"
                            f"内容近重复，检索时互相挤占且答案重复"),
                    suggestion="合并或删除其一，保留信息更完整的版本",
                    extra={"related_chunk_id": cj.id, "related_doc_title": title_j,
                           "similarity": round(max_sim, 4)},
                ))
        return out

    # ---------------------------------------------------------------- 检索探针
    async def _recall_probe(self, tenant_id: str,
                            kb_id: Optional[str]) -> Tuple[List[QualityIssue], Dict[str, float]]:
        """跑黄金集，按意图聚合 Recall@5，标记覆盖薄弱的意图。"""
        out: List[QualityIssue] = []
        intent_recall: Dict[str, float] = {}
        try:
            from app.services.eval_service import run_evaluation
            kb_ids = [kb_id] if kb_id else None
            res = await run_evaluation(self.db, tenant_id=tenant_id, kb_ids=kb_ids)
        except Exception as ex:  # 黄金集缺失或范围为空时不阻断巡检
            logger.warning("召回探针跳过：%s", ex)
            return out, intent_recall

        by_intent: Dict[str, List[float]] = defaultdict(list)
        for p in res.get("per_query", []):
            if p.get("negative"):
                continue
            intent = p.get("expected_intent") or p.get("intent") or "unknown"
            recall5 = p.get("delivered_metrics", {}).get("recall", {}).get(5)
            if recall5 is not None:
                by_intent[intent].append(float(recall5))

        for intent, vals in by_intent.items():
            if not vals:
                continue
            avg = sum(vals) / len(vals)
            intent_recall[intent] = round(avg, 4)
            if avg < 0.7:
                out.append(QualityIssue(
                    issue_type="low_recall_intent", severity="high",
                    chunk_id="", doc_id="", doc_title="", kb_id=kb_id or "",
                    detail=(f"意图「{intent}」黄金集平均 Recall@5={avg:.2f}（{len(vals)} 题），"
                            f"该场景知识覆盖薄弱"),
                    suggestion="针对该意图补充规范/案例文档，或优化切分与术语扩展",
                    extra={"intent": intent, "avg_recall@5": round(avg, 4),
                           "n_queries": len(vals)},
                ))
        return out, intent_recall

    # ---------------------------------------------------------------- 评分/建议
    def _count_docs(self, tenant_id: str, kb_id: Optional[str]) -> int:
        q = (self.db.query(Document)
             .filter(Document.tenant_id == tenant_id, Document.is_deleted.is_(False)))
        if kb_id:
            q = q.filter(Document.kb_id == kb_id)
        return q.count()

    def _score(self, issues: List[QualityIssue], total_chunks: int) -> float:
        penalty = sum(SEV_WEIGHT.get(i.severity, 1.0) for i in issues)
        base = max(total_chunks, 1)
        return max(0.0, 100.0 - (penalty / base) * 20.0)

    def _suggestions(self, counts: Counter, intent_recall: Dict[str, float],
                     semantic_note: str) -> List[str]:
        s: List[str] = []
        if counts.get("duplicate_chunk"):
            s.append(f"发现 {counts['duplicate_chunk']} 组近重复切片，建议合并去重以减少检索冲突与冗余答案")
        if counts.get("orphan_chunk"):
            s.append(f"{counts['orphan_chunk']} 个孤立切片疑似跑题，建议人工复核后清理或转移知识库")
        if counts.get("missing_standard_code"):
            s.append(f"{counts['missing_standard_code']} 份规范文档缺规范编号，建议批量补录以支撑精确溯源")
        if counts.get("missing_location"):
            s.append(f"{counts['missing_location']} 个切片缺章节/条文定位，建议优化解析或按标题层级重切")
        if counts.get("oversized_chunk") or counts.get("tiny_chunk"):
            s.append("存在过大/过碎切片，建议统一切分策略（按条款/语义边界），平衡片段粒度")
        low = [k for k, v in intent_recall.items() if v < 0.7]
        if low:
            s.append(f"意图 {', '.join(low)} 召回偏低，建议优先补充对应场景资料")
        if semantic_note:
            s.append(semantic_note)
        if not s:
            s.append("知识库切片与检索质量良好，建议保持定期巡检节奏")
        return s

    # ---------------------------------------------------------------- 报告历史
    def list_reports(self, tenant_id: str = "default", kb_id: Optional[str] = None,
                     limit: int = 20, offset: int = 0) -> Tuple[List[QualityReport], int]:
        q = self.db.query(QualityReport).filter(QualityReport.tenant_id == tenant_id)
        if kb_id is not None:
            q = q.filter(QualityReport.kb_id == kb_id)
        total = q.count()
        items = (q.order_by(QualityReport.created_at.desc())
                 .offset(offset).limit(limit).all())
        return items, total

    def get_report(self, report_id: str) -> Optional[QualityReport]:
        return (self.db.query(QualityReport)
                .filter(QualityReport.id == report_id).first())

    # ---------------------------------------------------------------- 采纳为治理任务
    def convert_to_task(self, issue_type: str, doc_id: str = "", kb_id: str = "",
                        title: str = "", detail: str = "", suggestion: str = "",
                        assignee: str = "", priority: str = "medium",
                        due_days: int = 14) -> GovernanceTask:
        from datetime import timedelta
        type_map = {
            "duplicate_chunk": "duplicate_merge",
            "orphan_chunk": "gap_fill",
            "missing_standard_code": "gap_fill",
            "missing_location": "gap_fill",
            "oversized_chunk": "gap_fill",
            "tiny_chunk": "gap_fill",
            "low_recall_intent": "gap_fill",
        }
        task = GovernanceTask(
            task_type=type_map.get(issue_type, "gap_fill"),
            title=title or f"[质量巡检] {issue_type}",
            description=(f"来源：知识库质量巡检 Agent\n问题：{detail}\n建议：{suggestion}"),
            target_doc_ids=[doc_id] if doc_id else [],
            kb_id=kb_id or "",
            priority=priority or "medium",
            assignee=assignee or "",
            due_date=datetime.utcnow() + timedelta(days=due_days),
        )
        self.db.add(task)
        self.db.flush()
        logger.info("质量问题采纳为治理任务 | %s | task=%s", issue_type, task.id)
        return task
