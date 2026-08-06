"""Stage7 知识治理闭环模型：治理任务、用户反馈、查询日志。"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (JSON, Boolean, Column, DateTime, Float, Index, Integer,
                        String, Text)

from app.db.session import Base


def _uid() -> str:
    return uuid.uuid4().hex


class GovernanceTask(Base):
    """知识治理事项：过期治理、文档补齐、重复合并"""
    __tablename__ = "tf_governance_task"

    id = Column(String(32), primary_key=True, default=_uid)
    task_type = Column(String(32), nullable=False,
                       comment="expire_check/duplicate_merge/gap_fill/conflict_resolve")
    title = Column(String(256), nullable=False)
    description = Column(Text, default="")
    target_doc_ids = Column(JSON, default=list)
    kb_id = Column(String(32), default="", index=True)
    priority = Column(String(16), default="medium", comment="high/medium/low")
    status = Column(String(16), default="open", comment="open/processing/done/closed")
    assignee = Column(String(64), default="", comment="维护负责人")
    watchers = Column(JSON, default=list, comment="关注人")
    due_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (Index("idx_gov_status", "status"),)


class KnowledgeGap(Base):
    """知识缺口：自动捕获的"答不上来/答不准"问题沉淀为可持续治理的待办。

    与 QueryLog 的区别：QueryLog 是每条查询的流水；KnowledgeGap 是把相似问题
    聚合后的持久化待办，可被采纳(转治理任务)、驳回、标记已解决，形成闭环。
    """
    __tablename__ = "tf_knowledge_gap"

    id = Column(String(32), primary_key=True, default=_uid)
    query = Column(Text, nullable=False, comment="最近一次询问原文（展示用）")
    query_key = Column(String(64), nullable=False, index=True,
                       comment="归一化键：用于把相似问题聚合到同一条缺口")
    intent = Column(String(32), default="", comment="QueryIntent 值")
    domains = Column(JSON, default=list, comment="路由到的知识域")
    user_id = Column(String(64), default="anonymous")
    occurrence_count = Column(Integer, default=1, comment="被问到的次数（相似问题累加）")
    last_asked_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String(16), default="open", index=True,
                    comment="open/accepted/rejected/resolved")
    suggested_kb_id = Column(String(32), default="", comment="建议补充到的知识库")
    suggested_title = Column(String(256), default="", comment="建议资料标题（采纳时生成）")
    linked_task_id = Column(String(32), default="", comment="关联治理任务 id")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (Index("idx_gap_status_intent", "status", "intent"),)


class FeedbackRecord(Base):
    """用户反馈：驱动知识缺口发现"""
    __tablename__ = "tf_feedback"

    id = Column(String(32), primary_key=True, default=_uid)
    message_id = Column(String(32), default="", index=True)
    conversation_id = Column(String(32), default="")
    rating = Column(Integer, default=0, comment="1=有帮助 -1=没帮助")
    reason = Column(String(64), default="", comment="not_found/wrong/outdated/incomplete")
    comment = Column(Text, default="")
    handled = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class QueryLog(Base):
    """查询日志：支撑热门问题/知识缺口统计"""
    __tablename__ = "tf_query_log"

    id = Column(String(32), primary_key=True, default=_uid)
    conversation_id = Column(String(32), default="")
    user_id = Column(String(64), default="anonymous")
    query = Column(Text, nullable=False)
    intent = Column(String(32), default="")
    hit_count = Column(Integer, default=0, comment="召回数量")
    confidence = Column(Float, default=0.0)
    answered = Column(Boolean, default=True, comment="是否给出有依据的答案")
    latency_ms = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
