"""未命中原因归因（Sprint7-T3）
==========================
对「检索失败 / 低置信」的查询做根因归因，复用真实管线信号
（IntentAgent 路由、HybridRetriever 双路打分、CrossEncoder 风格重排），
把「为什么没答好」拆成可归类的根因：

  - missing_doc      知识库缺覆盖该问题的文档（真·知识缺口）
  - intent_misroute  查询意图被误判 / 路由到错误知识域
  - rewrite_drift    查询改写/表述与文档语义漂移（关键词命中但语义弱）
  - chunking_bad     文档切分过碎，相关内容被打散，无单一切片拿到高分

诊断结论可把「确属知识缺口」的归因一键喂给治理 Agent（capture_gap），
形成「答不好 → 归因 → 记缺口 → 补文档」的闭环。
"""
from __future__ import annotations

from collections import Counter
from typing import List, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.constants import QueryIntent
from app.core.logging import get_logger
from app.llm.factory import get_reranker
from app.rag.intent_agent import IntentAgent
from app.retrieval.hybrid import get_retriever

logger = get_logger(__name__)


class MissAttributor:
    def __init__(self, db: Session):
        self.db = db

    # ----------------------------------------------------------------- 主流程
    async def diagnose(self, query: str, *, tenant_id: str = "default",
                       kb_ids: Optional[List[str]] = None, top_k: int = 10,
                       capture_gap: bool = False, user_id: str = "") -> dict:
        intent = await IntentAgent().classify(query)
        reasons: List[dict] = []

        # 越域：与工程无关被判为不需要检索
        if intent.out_of_scope and intent.intent == QueryIntent.UNKNOWN:
            reasons.append({
                "code": "intent_misroute",
                "label": "问题被判为越域（未进入检索）",
                "confidence": 0.9,
                "evidence": "Intent Agent 将查询标记为越域（out_of_scope），未进入检索管线",
                "suggestion": "确认问题是否属于工程/资料范畴；若是，请调整越域判定或显式指定检索域",
            })
            return self._build(query, intent, 0, 0.0, 0.0, reasons,
                               gap_captured=False, gap_id="")

        if not intent.need_retrieval:
            reasons.append({
                "code": "no_retrieval",
                "label": "无需检索（闲聊/越域）",
                "confidence": 1.0,
                "evidence": f"intent={intent.intent.value}, need_retrieval=False",
                "suggestion": "该查询不需要知识库检索，无需归因",
            })
            return self._build(query, intent, 0, 0.0, 0.0, reasons,
                               gap_captured=False, gap_id="")

        # 两路检索：意图域限定 vs 全库——用于识别「误路由」
        retriever = get_retriever()
        cands_intent = await retriever.retrieve(
            query, top_k=top_k, kb_ids=kb_ids or None,
            domains=intent.target_domains or None,
            vector_weight=0.6, bm25_weight=0.4)
        cands_broad = await retriever.retrieve(
            query, top_k=top_k, kb_ids=kb_ids or None, domains=None)

        n_intent = len(cands_intent)
        n_broad = len(cands_broad)
        top_intent = cands_intent[0] if n_intent else None
        top_broad = cands_broad[0] if n_broad else None
        top_fusion = top_intent.fusion_score if top_intent else 0.0

        # 重排（优先用意图域召回的结果）
        rerank_pairs = await get_reranker().rerank(
            query, [c.content for c in cands_intent], top_n=top_k)
        rerank_scores = [s for _, s in rerank_pairs]
        top_rerank = max(rerank_scores) if rerank_scores else 0.0
        mean_rerank = (sum(rerank_scores) / len(rerank_scores)) if rerank_scores else 0.0

        # 双通道均值（判断改写漂移：词面命中但语义弱）
        mean_vector = (sum(c.vector_score for c in cands_intent) / n_intent) if n_intent else 0.0
        mean_bm25 = (sum(c.bm25_score for c in cands_intent) / n_intent) if n_intent else 0.0

        # ----- 1) 缺文档（真·知识缺口）-----
        if n_intent == 0 and n_broad == 0:
            reasons.append({
                "code": "missing_doc",
                "label": "知识库缺乏覆盖该问题的文档",
                "confidence": 0.95,
                "evidence": "意图域限定与全库检索均零召回，知识库内无相关内容",
                "suggestion": "补充覆盖该问题的规范/案例/工艺文档，并确认已成功入库与建索引",
            })
        elif n_intent > 0 and top_rerank < settings.MIN_RELEVANCE_SCORE * 0.6:
            # 有召回但重排分数整体偏低：内容在库里但相关性不足
            reasons.append({
                "code": "missing_doc",
                "label": "知识库相关内容不足（召回相关性偏低）",
                "confidence": 0.7,
                "evidence": (f"意图域命中 {n_intent} 条，重排最高分 {top_rerank:.3f} "
                             f"低于相关性门槛 {settings.MIN_RELEVANCE_SCORE}"),
                "suggestion": "补充更精准的资料或扩充该主题文档，提升命中切片的语义相关性",
            })

        # ----- 2) 意图误路由 -----
        if n_intent == 0 and n_broad > 0:
            reasons.append({
                "code": "intent_misroute",
                "label": "意图路由过窄，丢掉了相关文档",
                "confidence": 0.85,
                "evidence": (f"全库检索命中 {n_broad} 条（最高融合 {top_broad.fusion_score:.3f}），"
                             f"但意图域限定后仅 {n_intent} 条，疑似路由到错误知识域"),
                "suggestion": "检查 INTENT_DOMAIN_ROUTING 配置，或让用户显式指定 domain 重新检索",
            })
        elif (top_broad is not None and top_intent is not None
              and top_broad.fusion_score > top_fusion * 1.3 and n_broad > n_intent):
            reasons.append({
                "code": "intent_misroute",
                "label": "意图域限定削弱了召回质量",
                "confidence": 0.6,
                "evidence": (f"全库 top 融合 {top_broad.fusion_score:.3f} 明显优于意图域 top "
                             f"{top_fusion:.3f}，且全库命中更多（{n_broad} vs {n_intent}）"),
                "suggestion": "放宽意图域路由策略或降低域优先级权重，避免过早收窄检索范围",
            })
        elif intent.confidence < 0.5:
            reasons.append({
                "code": "intent_misroute",
                "label": "意图识别置信度偏低",
                "confidence": 0.4,
                "evidence": f"Intent Agent 置信度仅 {intent.confidence:.3f}，意图判定可能不稳",
                "suggestion": "补充意图样本或开启 LLM 结构化分类以提升路由精度",
            })

        # ----- 3) 查询改写/表述漂移 -----
        if (n_intent > 0 and mean_bm25 > 0 and mean_vector > 0
                and mean_bm25 > mean_vector * 1.6
                and top_rerank >= settings.MIN_RELEVANCE_SCORE * 0.5):
            reasons.append({
                "code": "rewrite_drift",
                "label": "查询改写/表述与文档语义漂移",
                "confidence": 0.5,
                "evidence": (f"命中切片 BM25 均值 {mean_bm25:.3f} 明显高于向量均值 {mean_vector:.3f}，"
                             f"关键词面命中但语义匹配弱，疑似改写引入漂移"),
                "suggestion": "优化查询改写/同义词扩展策略，避免改写引入无关术语；或保留用户原问直接检索",
            })

        # ----- 4) 切分过碎 -----
        # 仅当查询本身有一定相关性（否则无关查询会把低分碎片误判为切分问题）
        doc_counts = Counter(c.doc_id for c in cands_intent)
        fragmented = {d: cnt for d, cnt in doc_counts.items() if cnt >= 3}
        if (fragmented and top_fusion < 0.6
                and top_rerank >= settings.MIN_RELEVANCE_SCORE * 0.5):
            max_cnt = max(fragmented.values())
            reasons.append({
                "code": "chunking_bad",
                "label": "文档切分过碎，相关内容被打散",
                "confidence": 0.45,
                "evidence": (f"同一文档在召回中碎片化出现最多 {max_cnt} 次，"
                             f"但无单一切片拿到高分（top 融合 {top_fusion:.3f}）"),
                "suggestion": "调整切分粒度（增大 chunk_size / 按语义或条款边界切分），合并相邻碎片",
            })

        # ----- 排序 + 过滤噪声 -----
        reasons.sort(key=lambda r: r["confidence"], reverse=True)
        reasons = [r for r in reasons if r["confidence"] >= 0.2]

        # ----- 结论判定 -----
        codes = {r["code"] for r in reasons}
        if "missing_doc" in codes and any(r["confidence"] >= 0.7 for r in reasons if r["code"] == "missing_doc"):
            verdict = "missing_doc"
        elif "intent_misroute" in codes:
            verdict = "intent_misroute"
        elif "chunking_bad" in codes:
            verdict = "chunking_bad"
        elif "rewrite_drift" in codes:
            verdict = "rewrite_drift"
        elif not reasons:
            verdict = "retrieval_ok"
        else:
            verdict = "mixed"

        # ----- 治理闭环：确属知识缺口才记录 -----
        gap_captured = False
        gap_id = ""
        if capture_gap and verdict == "missing_doc":
            try:
                from app.services.governance_service import GovernanceService
                gap = GovernanceService(self.db).capture_gap(
                    query=query, intent=intent.intent.value,
                    domains=intent.target_domains, user_id=user_id or "anonymous",
                    confidence=intent.confidence)
                if gap:
                    gap_captured = True
                    gap_id = gap.id
                    logger.info("未命中归因→知识缺口 | query=%s | gap=%s", query[:40], gap.id)
            except Exception as e:  # noqa: BLE001
                logger.warning("归因喂治理失败：%s", e)

        return self._build(query, intent, n_intent, top_fusion, top_rerank,
                           reasons, gap_captured=gap_captured, gap_id=gap_id,
                           verdict=verdict, n_broad=n_broad,
                           top_broad_fusion=top_broad.fusion_score if top_broad else 0.0,
                           mean_rerank=mean_rerank)

    # ----------------------------------------------------------------- 组装
    def _build(self, query, intent, n_intent, top_fusion, top_rerank, reasons,
               *, gap_captured, gap_id, verdict="mixed", n_broad=0,
               top_broad_fusion=0.0, mean_rerank=0.0) -> dict:
        return {
            "query": query,
            "intent": intent.intent.value,
            "intent_confidence": intent.confidence,
            "target_domains": intent.target_domains,
            "out_of_scope": intent.out_of_scope,
            "need_retrieval": intent.need_retrieval,
            "retrieved_count": n_intent,
            "broad_retrieved_count": n_broad,
            "top_fusion_score": round(top_fusion, 6),
            "top_rerank_score": round(top_rerank, 6),
            "mean_rerank_score": round(mean_rerank, 6),
            "top_broad_fusion_score": round(top_broad_fusion, 6),
            "verdict": verdict,
            "reasons": reasons,
            "gap_captured": gap_captured,
            "gap_id": gap_id,
        }
