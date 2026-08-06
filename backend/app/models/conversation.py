"""会话领域模型：会话 -> 消息 -> 引用。对应 Stage0 工程上下文管理。"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (JSON, Column, DateTime, Float, ForeignKey, Index,
                        Integer, String, Text)
from sqlalchemy.orm import relationship

from app.db.session import Base


def _uid() -> str:
    return uuid.uuid4().hex


class Conversation(Base):
    """工程会话上下文（Stage0）"""
    __tablename__ = "tf_conversation"

    id = Column(String(32), primary_key=True, default=_uid)
    title = Column(String(256), default="新会话")
    user_id = Column(String(64), default="anonymous", index=True)

    # ---- 工程上下文 ----
    project_name = Column(String(256), default="", comment="工程项目名")
    project_type = Column(String(64), default="", comment="工程类型 房建/市政/桥梁")
    discipline = Column(String(32), default="general")
    region = Column(String(64), default="", comment="地区，影响地标适用")

    kb_ids = Column(JSON, default=list, comment="本会话检索范围")
    message_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    messages = relationship("Message", back_populates="conversation",
                            cascade="all, delete-orphan",
                            order_by="Message.created_at")


class Message(Base):
    __tablename__ = "tf_message"

    id = Column(String(32), primary_key=True, default=_uid)
    conversation_id = Column(String(32), ForeignKey("tf_conversation.id", ondelete="CASCADE"),
                             nullable=False)
    role = Column(String(16), nullable=False, comment="user/assistant/system")
    content = Column(Text, nullable=False)

    # ---- RAG 追踪 ----
    intent = Column(String(32), default="")
    rewritten_query = Column(Text, default="")
    confidence = Column(Float, default=0.0)
    confidence_level = Column(String(16), default="")
    need_human_review = Column(Integer, default=0)
    latency_ms = Column(Integer, default=0)
    stage_trace = Column(JSON, default=dict, comment="Stage0-7 各阶段耗时与产出摘要")
    token_usage = Column(JSON, default=dict)

    created_at = Column(DateTime, default=datetime.utcnow)

    conversation = relationship("Conversation", back_populates="messages")
    citations = relationship("Citation", back_populates="message",
                             cascade="all, delete-orphan")

    __table_args__ = (Index("idx_msg_conv", "conversation_id"),)


class Citation(Base):
    """引用增强：答案 -> 来源可追溯"""
    __tablename__ = "tf_citation"

    id = Column(String(32), primary_key=True, default=_uid)
    message_id = Column(String(32), ForeignKey("tf_message.id", ondelete="CASCADE"),
                        nullable=False)
    index_no = Column(Integer, default=1, comment="答案中的角标序号 [1]")
    chunk_id = Column(String(32), default="")
    doc_id = Column(String(32), default="")
    doc_title = Column(String(256), default="")
    standard_code = Column(String(64), default="")
    section_path = Column(String(512), default="")
    clause_no = Column(String(64), default="")
    page_no = Column(Integer, default=0)
    snippet = Column(Text, default="")
    score = Column(Float, default=0.0)
    domain = Column(String(32), default="")

    message = relationship("Message", back_populates="citations")

    __table_args__ = (Index("idx_cite_msg", "message_id"),)
