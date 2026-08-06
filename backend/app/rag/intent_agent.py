"""Intent Agent：查询意图识别 + 检索路由决策（Sprint 2）。

把原 stage1 的"纯规则路由"升级为一个带 LLM 兜底、能输出结构化检索策略的
路由 Agent。核心能力：
  - 意图分类：LLM 结构化分类（含越域检测），无 LLM 时回退规则；
  - 域名路由：根据意图映射到优先检索的知识域；
  - 检索策略：为每种意图给出差异化的 top_k / 分数阈值 / 向量-BM25 权重，
    让"规范查询"走精确路线、"质量分析/案例检索"走高召回路线。

这样 Stage3 的混合检索不再是固定参数，而是随意图自适应 —— 这就是
"Agent 化路由"相对于普通 RAG 的关键差异。
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from app.core.config import settings
from app.core.constants import INTENT_DOMAIN_ROUTING, KnowledgeDomain, QueryIntent
from app.core.logging import get_logger
from app.llm.base import ChatMessage
from app.llm.factory import get_llm

logger = get_logger(__name__)


# ============================================================
# 检索策略（领域经验沉淀）
# ============================================================
@dataclass
class RetrievalPlan:
    """为某次检索给出的自适应参数集合。"""
    strategy: str = "balanced"                 # precision | recall | balanced | none
    top_k: int = 20
    score_threshold: float = 0.12
    vector_weight: float = 0.6
    bm25_weight: float = 0.4
    domain_priority: List[str] = field(default_factory=list)

    def as_ctx(self) -> dict:
        """用于检索缓存键的紧凑上下文（保证不同策略不串缓存）。"""
        return {
            "tk": self.top_k, "th": round(self.score_threshold, 4),
            "vw": self.vector_weight, "bw": self.bm25_weight,
            "dp": tuple(self.domain_priority),
        }


@dataclass
class IntentDecision:
    intent: QueryIntent
    confidence: float
    target_domains: List[str]
    need_retrieval: bool
    out_of_scope: bool = False          # 与工程/资料无关，不应强行作答
    reasoning: str = ""


# 各意图的默认检索策略
_INTENT_PLANS: dict[QueryIntent, RetrievalPlan] = {
    # 规范查询：精确优先，BM25 对规范编号/术语更敏感 -> 提权
    QueryIntent.SPEC_LOOKUP: RetrievalPlan(
        strategy="precision", top_k=14, score_threshold=0.10,
        vector_weight=0.45, bm25_weight=0.55),
    # 质量分析：高召回，案例+规范并重，允许更多候选进入重排
    QueryIntent.QUALITY_DIAGNOSIS: RetrievalPlan(
        strategy="recall", top_k=28, score_threshold=0.08,
        vector_weight=0.6, bm25_weight=0.4),
    # 方案生成：均衡，企业标准优先
    QueryIntent.SCHEME_GENERATION: RetrievalPlan(
        strategy="balanced", top_k=22, score_threshold=0.10,
        vector_weight=0.55, bm25_weight=0.45),
    # 案例检索：高召回，案例库优先
    QueryIntent.CASE_RETRIEVAL: RetrievalPlan(
        strategy="recall", top_k=24, score_threshold=0.09,
        vector_weight=0.6, bm25_weight=0.4),
    QueryIntent.UNKNOWN: RetrievalPlan(
        strategy="balanced", top_k=20, score_threshold=0.12),
    QueryIntent.CHITCHAT: RetrievalPlan(strategy="none", top_k=0),
}


# ============================================================
# 规则意图（LLM 不可用时的兜底，从原 stage1 迁移）
# ============================================================
_INTENT_RULES: list[tuple[QueryIntent, tuple[str, ...], float]] = [
    (QueryIntent.SPEC_LOOKUP,
     ("规范", "标准", "条文", "要求", "限值", "允许偏差", "验收", "国标", "行标",
      "gb", "jgj", "jtg", "cjj", "多少", "不得低于", "不应大于", "规定"), 0.0),
    (QueryIntent.QUALITY_DIAGNOSIS,
     ("质量问题", "缺陷", "裂缝", "渗漏", "空鼓", "蜂窝", "麻面", "露筋", "沉降",
      "变形", "原因", "成因", "为什么会", "事故", "返工", "不合格", "处理办法",
      "怎么处理", "整改", "通病"), 0.05),
    (QueryIntent.SCHEME_GENERATION,
     ("方案", "工艺", "流程", "施工步骤", "怎么施工", "如何施工", "编制", "技术措施",
      "交底", "组织设计", "专项方案"), 0.05),
    (QueryIntent.CASE_RETRIEVAL,
     ("案例", "类似工程", "以前", "历史", "经验", "教训", "先例", "参考项目",
      "别的项目", "踩坑"), 0.05),
    (QueryIntent.CHITCHAT,
     ("你好", "你是谁", "谢谢", "再见", "介绍一下你", "会做什么", "帮我干嘛"), 0.0),
]


def rule_intent(query: str) -> Tuple[QueryIntent, float]:
    """纯规则意图分类（零依赖）。返回 (意图, 置信度)。"""
    q = query.lower()
    scores: dict[QueryIntent, float] = {}
    for intent, kws, bonus in _INTENT_RULES:
        hit = sum(1 for k in kws if k in q)
        if hit:
            scores[intent] = hit * 0.22 + bonus

    if not scores:
        return QueryIntent.UNKNOWN, 0.3
    best = max(scores.items(), key=lambda kv: kv[1])

    # 闲聊需要问题很短才成立，避免"你好，C30混凝土养护要求"被误判
    if best[0] == QueryIntent.CHITCHAT and len(query.strip()) > 14:
        scores.pop(QueryIntent.CHITCHAT, None)
        if not scores:
            return QueryIntent.UNKNOWN, 0.3
        best = max(scores.items(), key=lambda kv: kv[1])

    # 冲突消解：用户显式要"案例/经验/参考"时，优先案例检索
    CASE_PRIORITY_TOKENS = ("参考", "类似", "可以", "有哪些", "举例", "借鉴",
                            "经验", "教训", "之前", "以前", "历史", "先例")
    if (QueryIntent.CASE_RETRIEVAL in scores
            and any(tok in q for tok in CASE_PRIORITY_TOKENS)):
        rival_max = max((s for i, s in scores.items()
                         if i != QueryIntent.CASE_RETRIEVAL), default=0.0)
        if scores[QueryIntent.CASE_RETRIEVAL] <= rival_max:
            scores[QueryIntent.CASE_RETRIEVAL] = rival_max + 0.1
        best = max(scores.items(), key=lambda kv: kv[1])

    return best[0], min(0.95, 0.45 + best[1])


def _parse_llm_intent(text: str) -> Optional[Tuple[QueryIntent, float, bool]]:
    """从 LLM 输出中解析结构化意图。返回 (意图, 置信度, 越域)。"""
    # 抽取第一个 JSON 对象（容忍前后多余文本）
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
    except Exception:
        return None
    label = str(obj.get("intent", "")).strip().lower().split()[0].strip(".,;:\"")
    if label not in QueryIntent._value2member_map_:
        return None
    try:
        conf = float(obj.get("confidence", 0.8))
    except Exception:
        conf = 0.8
    oos = bool(obj.get("out_of_scope", False))
    return QueryIntent(label), max(0.0, min(1.0, conf)), oos


class IntentAgent:
    """查询意图路由 Agent。"""

    def __init__(self) -> None:
        self.use_llm = (settings.INTENT_AGENT_ENABLED
                        and settings.LLM_PROVIDER == "openai_compatible"
                        and bool(settings.LLM_API_KEY))
        if self.use_llm:
            logger.info("Intent Agent 使用 LLM 结构化分类（openai_compatible）")
        else:
            logger.info("Intent Agent 使用规则分类（未配置 LLM 或开关关闭）")

    async def classify(self, query: str,
                       explicit_domains: Optional[List[str]] = None) -> IntentDecision:
        r_intent, r_conf = rule_intent(query)
        intent, conf, oos = r_intent, r_conf, False

        # LLM 兜底：规则置信度偏低时必须用模型确认，否则有模型也用模型提升精度
        if self.use_llm:
            try:
                from app.rag.prompts import INTENT_AGENT_PROMPT
                res = await get_llm().chat(
                    [ChatMessage("user", INTENT_AGENT_PROMPT.format(query=query))],
                    temperature=0.0, max_tokens=80)
                parsed = _parse_llm_intent(res.content)
                if parsed:
                    intent, conf, oos = parsed
            except Exception as e:  # noqa: BLE001
                logger.warning("Intent Agent LLM 分类失败，回退规则: %s", e)

        # 越域开关
        if oos and not settings.INTENT_OUT_OF_SCOPE:
            oos = False

        # 域名路由
        if explicit_domains:
            domains = list(explicit_domains)
        else:
            domains = [d.value for d in INTENT_DOMAIN_ROUTING.get(intent, [])]

        # 是否需要检索：闲聊不需要；越域的未知问题也不强行检索
        need = intent != QueryIntent.CHITCHAT and not (
            oos and intent == QueryIntent.UNKNOWN)

        return IntentDecision(
            intent=intent, confidence=round(conf, 3),
            target_domains=domains, need_retrieval=need,
            out_of_scope=oos,
            reasoning=f"intent={intent.value} llm={self.use_llm} oos={oos}")

    def build_plan(self, decision: IntentDecision,
                   top_k: Optional[int] = None) -> RetrievalPlan:
        """根据意图决策构造检索策略（拷贝避免改到类级单例）。"""
        base = _INTENT_PLANS.get(decision.intent, _INTENT_PLANS[QueryIntent.UNKNOWN])
        plan = RetrievalPlan(
            strategy=base.strategy, top_k=base.top_k,
            score_threshold=base.score_threshold,
            vector_weight=base.vector_weight,
            bm25_weight=base.bm25_weight,
            domain_priority=list(decision.target_domains),
        )
        if top_k:
            plan.top_k = top_k
        return plan
