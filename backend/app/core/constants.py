"""领域常量：知识域、意图、文档状态、可信度等级。"""
from __future__ import annotations

from enum import Enum


class KnowledgeDomain(str, Enum):
    """三大工程知识域（规格说明书 §7）"""
    STANDARD = "standard"      # 建设规范库：国标/行标/地标/图集
    CASE = "case"              # 项目案例库：工程案例、质量事故、经验教训
    ENTERPRISE = "enterprise"  # 企业知识库：企业标准、SOP、内部方案

    @property
    def label(self) -> str:
        return {
            "standard": "建设规范库",
            "case": "项目案例库",
            "enterprise": "企业知识库",
        }[self.value]


class QueryIntent(str, Enum):
    """Stage1 智能路由识别的意图（规格说明书 §5 四大业务场景 + 通用）"""
    SPEC_LOOKUP = "spec_lookup"        # 工程规范智能查询
    QUALITY_DIAGNOSIS = "quality_diagnosis"  # 施工质量问题分析
    SCHEME_GENERATION = "scheme_generation"  # 施工方案智能生成
    CASE_RETRIEVAL = "case_retrieval"  # 工程案例经验检索
    CHITCHAT = "chitchat"              # 闲聊/无需检索
    UNKNOWN = "unknown"

    @property
    def label(self) -> str:
        return {
            "spec_lookup": "规范条文查询",
            "quality_diagnosis": "质量问题分析",
            "scheme_generation": "施工方案生成",
            "case_retrieval": "工程案例检索",
            "chitchat": "日常对话",
            "unknown": "通用问答",
        }[self.value]


class DocumentStatus(str, Enum):
    PENDING = "pending"
    PARSING = "parsing"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    READY = "ready"
    FAILED = "failed"


class GovernanceStatus(str, Enum):
    """Stage7 知识治理：文档有效性标注"""
    VALID = "valid"            # 有效
    NEED_UPDATE = "need_update"  # 待更新
    DEPRECATED = "deprecated"  # 已废弃
    REFERENCE_ONLY = "reference_only"  # 仅供参考


class ConfidenceLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

    @property
    def label(self) -> str:
        return {"high": "高可信", "medium": "中等可信", "low": "低可信-建议人工复核"}[self.value]


class DisciplineTag(str, Enum):
    """土木工程专业分部"""
    FOUNDATION = "foundation"    # 地基基础
    CONCRETE = "concrete"        # 混凝土结构
    STEEL = "steel"              # 钢结构
    MASONRY = "masonry"          # 砌体结构
    WATERPROOF = "waterproof"    # 防水工程
    MEP = "mep"                  # 机电安装
    ROAD_BRIDGE = "road_bridge"  # 道路桥梁
    TUNNEL = "tunnel"            # 隧道地下
    SAFETY = "safety"            # 施工安全
    GENERAL = "general"          # 通用


# 意图 -> 优先检索的知识域
INTENT_DOMAIN_ROUTING: dict[QueryIntent, list[KnowledgeDomain]] = {
    QueryIntent.SPEC_LOOKUP: [KnowledgeDomain.STANDARD, KnowledgeDomain.ENTERPRISE],
    QueryIntent.QUALITY_DIAGNOSIS: [KnowledgeDomain.CASE, KnowledgeDomain.STANDARD],
    QueryIntent.SCHEME_GENERATION: [KnowledgeDomain.ENTERPRISE, KnowledgeDomain.STANDARD, KnowledgeDomain.CASE],
    QueryIntent.CASE_RETRIEVAL: [KnowledgeDomain.CASE, KnowledgeDomain.ENTERPRISE],
    QueryIntent.UNKNOWN: [KnowledgeDomain.STANDARD, KnowledgeDomain.CASE, KnowledgeDomain.ENTERPRISE],
    QueryIntent.CHITCHAT: [],
}

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".doc", ".xlsx", ".xls", ".txt", ".md", ".csv"}
