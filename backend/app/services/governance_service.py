"""
Stage7 知识治理服务
==================
- 知识库体检：过期/临期、无负责人、重复、失败、缺摘要
- 治理任务 CRUD
- 知识缺口发现（零召回/低置信查询聚类）
- 运营报告生成（周报/月报）
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.constants import DocumentStatus, GovernanceStatus, QueryIntent
from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.models.governance import (FeedbackRecord, GovernanceTask, KnowledgeGap,
                                    QueryLog)
from app.models.knowledge import Chunk, Document, KnowledgeBase
from app.schemas.governance import (GovernanceTaskCreate, HealthIssue,
                                    KBHealthReport, KnowledgeGap as KnowledgeGapSchema,
                                    OperationReport)
from app.utils.text import tokenize

logger = get_logger(__name__)

STALE_DAYS = 365          # 超过一年未更新视为陈旧
EXPIRING_SOON_DAYS = 90   # 90 天内到期视为临期


class GovernanceService:
    def __init__(self, db: Session):
        self.db = db

    # ==================== 体检 ====================
    def health_report(self, kb_id: Optional[str] = None) -> KBHealthReport:
        q = self.db.query(Document)
        if kb_id:
            q = q.filter(Document.kb_id == kb_id)
        docs = q.all()
        now = datetime.utcnow()
        issues: List[HealthIssue] = []

        # 重复检测：同 kb 下标题高度相似或 hash 相同
        by_hash: dict[str, list[Document]] = defaultdict(list)
        by_title: dict[str, list[Document]] = defaultdict(list)
        for d in docs:
            if d.file_hash:
                by_hash[d.file_hash].append(d)
            by_title[(d.kb_id, d.title.strip().lower())].append(d)

        for group in list(by_hash.values()) + list(by_title.values()):
            if len(group) > 1:
                issues.append(HealthIssue(
                    issue_type="duplicate", severity="medium",
                    doc_id=group[0].id, doc_title=group[0].title, kb_id=group[0].kb_id,
                    detail=f"检测到 {len(group)} 份内容或标题重复的文档",
                    suggestion="保留最新版本，其余标记为已废弃或合并后删除",
                ))

        for d in docs:
            if d.expire_date and d.expire_date <= now and \
                    d.governance_status != GovernanceStatus.DEPRECATED.value:
                issues.append(HealthIssue(
                    issue_type="expired", severity="high", doc_id=d.id,
                    doc_title=d.title, kb_id=d.kb_id,
                    detail=f"废止日期 {d.expire_date:%Y-%m-%d} 已过，当前状态仍为 {d.governance_status}",
                    suggestion="标记为已废弃，并确认是否有替代新版规范需要入库",
                ))
            elif d.expire_date and 0 < (d.expire_date - now).days <= EXPIRING_SOON_DAYS:
                issues.append(HealthIssue(
                    issue_type="expiring_soon", severity="medium", doc_id=d.id,
                    doc_title=d.title, kb_id=d.kb_id,
                    detail=f"将于 {d.expire_date:%Y-%m-%d} 废止（剩余 {(d.expire_date - now).days} 天）",
                    suggestion="提前准备替代版本，安排负责人跟进",
                ))

            if not (d.owner or "").strip():
                issues.append(HealthIssue(
                    issue_type="no_owner", severity="medium", doc_id=d.id,
                    doc_title=d.title, kb_id=d.kb_id,
                    detail="文档未指定负责人",
                    suggestion="指派内容负责人，明确更新与答疑责任",
                ))

            last = d.updated_at or d.created_at
            if last and (now - last).days > STALE_DAYS and \
                    d.governance_status == GovernanceStatus.VALID.value:
                issues.append(HealthIssue(
                    issue_type="stale", severity="low", doc_id=d.id,
                    doc_title=d.title, kb_id=d.kb_id,
                    detail=f"已 {(now - last).days} 天未更新",
                    suggestion="复核内容有效性，确认后更新版本号与更新时间",
                ))

            if d.status == DocumentStatus.FAILED.value:
                issues.append(HealthIssue(
                    issue_type="parse_failed", severity="high", doc_id=d.id,
                    doc_title=d.title, kb_id=d.kb_id,
                    detail=f"入库失败：{(d.error_msg or '')[:120]}",
                    suggestion="检查文件格式（扫描件需 OCR），修复后重新上传",
                ))

            if not (d.summary or "").strip():
                issues.append(HealthIssue(
                    issue_type="empty_summary", severity="low", doc_id=d.id,
                    doc_title=d.title, kb_id=d.kb_id,
                    detail="缺少文档摘要", suggestion="补充摘要与关键词，提升检索命中率",
                ))

        total_docs = len(docs)
        counts = Counter(d.governance_status for d in docs)
        chunk_q = self.db.query(func.count(Chunk.id))
        if kb_id:
            chunk_q = chunk_q.filter(Chunk.kb_id == kb_id)

        sev_w = {"high": 6.0, "medium": 3.0, "low": 1.0}
        penalty = sum(sev_w.get(i.severity, 1.0) for i in issues)
        score = max(0.0, 100.0 - (penalty / max(total_docs, 1)) * 12.0)

        suggestions = []
        it = Counter(i.issue_type for i in issues)
        if it.get("expired"):
            suggestions.append(f"存在 {it['expired']} 份已过期文档，建议立即标记废弃并补充新版规范")
        if it.get("no_owner"):
            suggestions.append(f"{it['no_owner']} 份文档无负责人，建议按专业分部批量指派")
        if it.get("duplicate"):
            suggestions.append(f"发现 {it['duplicate']} 组重复文档，建议合并去重以避免检索冲突")
        if it.get("parse_failed"):
            suggestions.append(f"{it['parse_failed']} 份文档入库失败，需优先修复（扫描件建议接入 OCR）")
        if not suggestions:
            suggestions.append("知识库整体健康，建议保持季度复核节奏")

        return KBHealthReport(
            generated_at=datetime.utcnow(),
            total_kb=self.db.query(func.count(KnowledgeBase.id)).scalar() or 0,
            total_docs=total_docs,
            total_chunks=chunk_q.scalar() or 0,
            valid_docs=counts.get(GovernanceStatus.VALID.value, 0),
            need_update_docs=counts.get(GovernanceStatus.NEED_UPDATE.value, 0),
            deprecated_docs=counts.get(GovernanceStatus.DEPRECATED.value, 0),
            failed_docs=sum(1 for d in docs if d.status == DocumentStatus.FAILED.value),
            issues=sorted(issues, key=lambda x: {"high": 0, "medium": 1, "low": 2}[x.severity]),
            score=round(score, 1),
            suggestions=suggestions,
        )

    # ==================== 治理任务 ====================
    def create_task(self, payload: GovernanceTaskCreate) -> GovernanceTask:
        t = GovernanceTask(**payload.model_dump())
        self.db.add(t)
        self.db.flush()
        logger.info("创建治理任务 | %s | %s", t.task_type, t.title)
        return t

    def list_tasks(self, status: str = "", assignee: str = "", kb_id: str = "",
                   offset: int = 0, limit: int = 50,
                   task_type: str = "") -> Tuple[List[GovernanceTask], int]:
        q = self.db.query(GovernanceTask)
        if status:
            q = q.filter(GovernanceTask.status == status)
        if assignee:
            q = q.filter(GovernanceTask.assignee == assignee)
        if kb_id:
            q = q.filter(GovernanceTask.kb_id == kb_id)
        if task_type:
            q = q.filter(GovernanceTask.task_type == task_type)
        total = q.count()
        items = (q.order_by(GovernanceTask.created_at.desc())
                 .offset(offset).limit(limit).all())
        return items, total

    def update_task(self, task_id: str, **fields) -> GovernanceTask:
        t = self.db.query(GovernanceTask).filter(GovernanceTask.id == task_id).first()
        if not t:
            raise NotFoundError(f"治理任务不存在: {task_id}")
        for k, v in fields.items():
            if v is not None:
                setattr(t, k, v)
        t.updated_at = datetime.utcnow()
        self.db.flush()
        return t

    def generate_tasks_from_health(self, kb_id: Optional[str] = None,
                                   default_assignee: str = "") -> List[GovernanceTask]:
        """把体检问题自动转成治理事项（避免重复创建）。"""
        report = self.health_report(kb_id)
        type_map = {
            "expired": ("expire_check", "high"),
            "expiring_soon": ("expire_check", "medium"),
            "duplicate": ("duplicate_merge", "medium"),
            "no_owner": ("gap_fill", "medium"),
            "parse_failed": ("gap_fill", "high"),
            "stale": ("expire_check", "low"),
            "empty_summary": ("gap_fill", "low"),
        }
        existing = {(t.task_type, tuple(t.target_doc_ids or []))
                    for t in self.db.query(GovernanceTask)
                    .filter(GovernanceTask.status.in_(["open", "processing"])).all()}
        created: List[GovernanceTask] = []
        for issue in report.issues:
            tt, prio = type_map.get(issue.issue_type, ("gap_fill", "low"))
            key = (tt, (issue.doc_id,))
            if key in existing:
                continue
            existing.add(key)
            t = GovernanceTask(
                task_type=tt,
                title=f"[{issue.issue_type}] {issue.doc_title or issue.doc_id}",
                description=f"{issue.detail}\n建议：{issue.suggestion}",
                target_doc_ids=[issue.doc_id] if issue.doc_id else [],
                kb_id=issue.kb_id or (kb_id or ""),
                priority=prio,
                assignee=default_assignee or self._doc_owner(issue.doc_id),
                due_date=datetime.utcnow() + timedelta(days=14 if prio == "high" else 30),
            )
            self.db.add(t)
            created.append(t)
        self.db.flush()
        logger.info("自动生成治理任务 %d 条", len(created))
        return created

    def _doc_owner(self, doc_id: str) -> str:
        if not doc_id:
            return ""
        d = self.db.query(Document).filter(Document.id == doc_id).first()
        return (d.owner if d else "") or ""

    # ==================== 知识缺口 ====================
    def knowledge_gaps(self, days: int = 30, limit: int = 20) -> List[KnowledgeGap]:
        since = datetime.utcnow() - timedelta(days=days)
        logs = (self.db.query(QueryLog)
                .filter(QueryLog.created_at >= since)
                # 闲聊类问题不需要检索，不构成知识缺口
                .filter(QueryLog.intent != QueryIntent.CHITCHAT.value)
                # 缺口判据：零召回，或虽有召回但可信度偏低（证据不足）
                .filter((QueryLog.hit_count == 0) | (QueryLog.confidence < 0.45))
                .all())
        buckets: dict[str, list[QueryLog]] = defaultdict(list)
        for lg in logs:
            key = " ".join(sorted(set(tokenize(lg.query)))[:5]) or lg.query[:20]
            buckets[key].append(lg)

        gaps = []
        for key, items in buckets.items():
            avg = sum(i.confidence for i in items) / len(items)
            gaps.append(KnowledgeGapSchema(
                query=items[0].query, count=len(items), avg_confidence=round(avg, 3),
                suggestion=("零召回，建议补充相关规范或案例文档"
                            if all(i.hit_count == 0 for i in items)
                            else "召回质量低，建议补充更精准的资料或优化文档切分"),
            ))
        gaps.sort(key=lambda g: (g.count, -g.avg_confidence), reverse=True)
        return gaps[:limit]

    # ==================== 知识缺口（持久化闭环） ====================
    @staticmethod
    def _gap_key(query: str) -> str:
        """归一化键：把相似问题聚合到同一条缺口（取前 6 个关键词的并集排序）。"""
        from app.utils.text import sha256_text, tokenize
        toks = sorted(set(tokenize(query)))[:6]
        if not toks:
            return sha256_text(query.strip().lower())[:32]
        return " ".join(toks)

    def capture_gap(self, query: str, intent: str, domains: List[str],
                    user_id: str, confidence: float) -> Optional[KnowledgeGap]:
        """自动捕获一条知识缺口（治理 Agent 在每次答不好时调用）。

        对相似问题按 query_key 去重聚合，累加 occurrence_count；已采纳/驳回的缺口
        不再重复计数（避免覆盖人工决策）。返回落库/更新的缺口对象。
        """
        key = self._gap_key(query)
        existing = (self.db.query(KnowledgeGap)
                    .filter(KnowledgeGap.query_key == key).first())
        if existing and existing.status in ("accepted", "rejected", "resolved"):
            # 人工已决策，保留决策，仅若有新信息可忽略
            return existing
        if existing:
            existing.occurrence_count = (existing.occurrence_count or 1) + 1
            existing.last_asked_at = datetime.utcnow()
            existing.query = query  # 用最新问法展示
            existing.intent = intent or existing.intent
            if domains:
                existing.domains = domains
            existing.updated_at = datetime.utcnow()
            self.db.flush()
            logger.info("知识缺口聚合 | key=%s | count=%d", key, existing.occurrence_count)
            return existing

        gap = KnowledgeGap(
            query=query, query_key=key, intent=intent, domains=domains or [],
            user_id=user_id or "anonymous",
            occurrence_count=1, last_asked_at=datetime.utcnow(),
            status="open", suggested_kb_id="", suggested_title="",
            linked_task_id="",
        )
        self.db.add(gap)
        self.db.flush()
        logger.info("知识缺口捕获 | %s | intent=%s | conf=%.3f", query[:40], intent, confidence)
        return gap

    def list_knowledge_gaps(self, status: str = "", intent: str = "",
                            limit: int = 50, offset: int = 0) -> Tuple[List[KnowledgeGap], int]:
        q = self.db.query(KnowledgeGap)
        if status:
            q = q.filter(KnowledgeGap.status == status)
        if intent:
            q = q.filter(KnowledgeGap.intent == intent)
        total = q.count()
        items = (q.order_by(KnowledgeGap.occurrence_count.desc(),
                            KnowledgeGap.last_asked_at.desc())
                 .offset(offset).limit(limit).all())
        return items, total

    def accept_gap(self, gap_id: str, assignee: str = "", kb_id: str = "",
                   priority: str = "", due_days: int = 14) -> GovernanceTask:
        """把一条缺口采纳为"补充资料"治理任务，形成闭环。"""
        gap = self.db.query(KnowledgeGap).filter(KnowledgeGap.id == gap_id).first()
        if not gap:
            raise NotFoundError(f"知识缺口不存在: {gap_id}")
        if gap.status == "accepted" and gap.linked_task_id:
            # 已采纳过，返回已关联任务
            t = self.db.query(GovernanceTask).filter(
                GovernanceTask.id == gap.linked_task_id).first()
            if t:
                return t

        title = gap.suggested_title or f"补充知识：{gap.query[:30]}"
        task = GovernanceTask(
            task_type="gap_fill",
            title=title,
            description=(f"知识缺口自动生成：用户多次问到「{gap.query}」（{gap.occurrence_count} 次，"
                         f"意图 {gap.intent}），当前知识库零召回/低置信，需补充相关资料。\n"
                         f"建议补充到知识域：{', '.join(gap.domains) or '未指定'}。"),
            target_doc_ids=[],
            kb_id=kb_id or (gap.suggested_kb_id or ""),
            priority=priority or ("high" if gap.occurrence_count >= 3 else "medium"),
            assignee=assignee or "",
            due_date=datetime.utcnow() + timedelta(days=due_days),
        )
        self.db.add(task)
        self.db.flush()
        gap.status = "accepted"
        gap.linked_task_id = task.id
        gap.suggested_kb_id = task.kb_id
        gap.updated_at = datetime.utcnow()
        self.db.flush()
        logger.info("缺口采纳为治理任务 | gap=%s | task=%s", gap_id, task.id)
        return task

    def reject_gap(self, gap_id: str, reason: str = "") -> KnowledgeGap:
        gap = self.db.query(KnowledgeGap).filter(KnowledgeGap.id == gap_id).first()
        if not gap:
            raise NotFoundError(f"知识缺口不存在: {gap_id}")
        gap.status = "rejected"
        if reason:
            gap.suggested_title = (gap.suggested_title or "").strip() or ""
            # 把驳回理由塞进 linked_task_id 不合适，这里仅改状态
        gap.updated_at = datetime.utcnow()
        self.db.flush()
        logger.info("缺口驳回 | gap=%s", gap_id)
        return gap

    def resolve_gap(self, gap_id: str, task_id: str = "") -> KnowledgeGap:
        gap = self.db.query(KnowledgeGap).filter(KnowledgeGap.id == gap_id).first()
        if not gap:
            raise NotFoundError(f"知识缺口不存在: {gap_id}")
        gap.status = "resolved"
        if task_id:
            gap.linked_task_id = task_id
        gap.updated_at = datetime.utcnow()
        self.db.flush()
        return gap

    def governance_dashboard(self, days: int = 30) -> dict:
        """治理总览：缺口分布、任务进度、知识覆盖、高频缺口。"""
        since = datetime.utcnow() - timedelta(days=days)
        gap_q = self.db.query(KnowledgeGap)
        gaps = gap_q.all()
        gap_by_status = defaultdict(int)
        gap_by_intent: Counter = Counter()
        for g in gaps:
            gap_by_status[g.status] += 1
            gap_by_intent[g.intent] += 1

        open_gaps = gap_by_status.get("open", 0)
        top_gaps = sorted(
            [g for g in gaps if g.status == "open"],
            key=lambda x: (x.occurrence_count or 0), reverse=True)[:10]
        top_gaps_out = [{
            "id": g.id, "query": g.query, "intent": g.intent,
            "occurrence_count": g.occurrence_count or 0,
            "domains": g.domains or [], "last_asked_at": g.last_asked_at,
        } for g in top_gaps]

        task_total = self.db.query(func.count(GovernanceTask.id)).scalar() or 0
        task_by_status = dict(
            (s, self.db.query(func.count(GovernanceTask.id))
             .filter(GovernanceTask.status == s).scalar() or 0)
            for s in ("open", "processing", "done", "closed"))
        pending_tasks = task_by_status.get("open", 0) + task_by_status.get("processing", 0)

        # 知识覆盖：近 N 天查询的应答率
        logs = (self.db.query(QueryLog)
                .filter(QueryLog.created_at >= since).all())
        total_q = len(logs)
        unanswered = sum(1 for l in logs if not l.answered or l.hit_count == 0)
        answer_rate = round((total_q - unanswered) / total_q, 3) if total_q else 0.0

        # 各知识域文档/切片量（覆盖率概览）
        domain_docs = (self.db.query(KnowledgeBase.domain, func.count(Document.id))
                       .join(Document, Document.kb_id == KnowledgeBase.id)
                       .group_by(KnowledgeBase.domain).all())
        coverage = {d: c for d, c in domain_docs}

        return {
            "period_days": days,
            "gap_total": len(gaps),
            "gap_by_status": dict(gap_by_status),
            "gap_by_intent": dict(gap_by_intent),
            "open_gaps": open_gaps,
            "task_total": task_total,
            "task_by_status": task_by_status,
            "pending_tasks": pending_tasks,
            "answer_rate": answer_rate,
            "total_queries": total_q,
            "domain_doc_count": coverage,
            "top_gaps": top_gaps_out,
        }

    # ==================== 运营报告 ====================
    def operation_report(self, days: int = 7) -> OperationReport:
        end = datetime.utcnow()
        start = end - timedelta(days=days)

        new_docs = self.db.query(func.count(Document.id)).filter(
            Document.created_at >= start).scalar() or 0
        new_chunks = self.db.query(func.count(Chunk.id)).filter(
            Chunk.created_at >= start).scalar() or 0

        logs = self.db.query(QueryLog).filter(QueryLog.created_at >= start).all()
        total_q = len(logs)
        unanswered = sum(1 for l in logs if not l.answered or l.hit_count == 0)
        avg_conf = round(sum(l.confidence for l in logs) / total_q, 3) if total_q else 0.0
        avg_lat = int(sum(l.latency_ms for l in logs) / total_q) if total_q else 0

        topic = Counter()
        for l in logs:
            for t in tokenize(l.query):
                if len(t) >= 2:
                    topic[t] += 1
        hot = [{"topic": k, "count": v} for k, v in topic.most_common(10)]

        pending = self.db.query(func.count(GovernanceTask.id)).filter(
            GovernanceTask.status.in_(["open", "processing"])).scalar() or 0

        neg_fb = self.db.query(func.count(FeedbackRecord.id)).filter(
            FeedbackRecord.created_at >= start, FeedbackRecord.rating < 0).scalar() or 0

        answer_rate = round((total_q - unanswered) / total_q, 3) if total_q else 0.0
        suggestions = []
        if answer_rate < 0.8 and total_q:
            suggestions.append(f"应答率 {answer_rate:.0%} 偏低，建议按知识缺口清单优先补齐文档")
        if avg_conf < 0.5 and total_q:
            suggestions.append("平均可信度偏低，建议检查文档切分粒度与摘要质量，或接入更强的向量模型")
        if pending > 10:
            suggestions.append(f"待处理治理事项 {pending} 条，建议分配到人并设置截止时间")
        if neg_fb:
            suggestions.append(f"本期收到 {neg_fb} 条负向反馈，建议逐条复盘并沉淀为 FAQ")
        if new_docs == 0:
            suggestions.append("本期无新增文档，建议推动各专业按月提交规范更新与项目复盘")
        if not suggestions:
            suggestions.append("知识库运行平稳，建议保持当前更新节奏并持续沉淀 FAQ")

        return OperationReport(
            period=f"近 {days} 天", start=start, end=end,
            new_docs=new_docs, new_chunks=new_chunks,
            total_queries=total_q, unanswered_queries=unanswered,
            answer_rate=answer_rate, avg_confidence=avg_conf, avg_latency_ms=avg_lat,
            hot_topics=hot, knowledge_gaps=self.knowledge_gaps(days=days, limit=10),
            pending_tasks=pending, suggestions=suggestions,
        )
