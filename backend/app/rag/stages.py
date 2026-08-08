"""
Stage0 - Stage7 各阶段实现
=========================
Stage0 工程上下文管理   : 加载会话上下文与历史，归一化检索范围
Stage1 智能路由         : 意图识别 -> 知识域路由 -> 是否需要检索
Stage2 查询改写         : 指代消解 + 术语扩展 + 规范编号抽取 + 子查询拆解
Stage3 混合检索         : 向量 + BM25 双通道 RRF 融合
Stage4 重排序           : CrossEncoder / 规则重排 + 强条与时效加权
Stage5 上下文构建       : 去重、预算裁剪、编号、结构化拼装
Stage6 智能生成 + 引用增强
Stage7 知识治理闭环     : 可信度评估、日志落库、知识缺口捕获
"""
from __future__ import annotations

import re
import time
from typing import List

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.constants import (INTENT_DOMAIN_ROUTING, ConfidenceLevel,
                                KnowledgeDomain, QueryIntent)
from app.core.logging import get_logger
from app.llm.base import ChatMessage
from app.llm.factory import get_llm, get_reranker
from app.models.conversation import Conversation, Message
from app.models.knowledge import Chunk, Document
from app.rag import prompts
from app.rag.state import CitationItem, RAGState
from app.retrieval.hybrid import Candidate, get_retriever
from app.utils.text import (STANDARD_CODE_RE, extract_keywords, tokenize,
                            truncate)

logger = get_logger(__name__)


# ============================================================
# Stage0 工程上下文管理
# ============================================================
async def stage0_context(state: RAGState, db: Session) -> RAGState:
    t0 = time.perf_counter()
    conv = None
    if state.conversation_id:
        conv = db.query(Conversation).filter(Conversation.id == state.conversation_id).first()

    if conv:
        state.project_name = state.project_name or conv.project_name or ""
        state.project_type = state.project_type or conv.project_type or ""
        state.discipline = state.discipline if state.discipline != "general" else (conv.discipline or "general")
        state.region = state.region or conv.region or ""
        if not state.kb_ids:
            state.kb_ids = list(conv.kb_ids or [])

        # 注意：当前轮的 user 消息已先行落库，必须排除，否则会被当成历史
        q = db.query(Message).filter(Message.conversation_id == conv.id)
        if state.current_message_id:
            q = q.filter(Message.id != state.current_message_id)
        msgs = (q.order_by(Message.created_at.desc())
                .limit(settings.MAX_HISTORY_ROUNDS * 2).all())
        state.history = [{"role": m.role, "content": truncate(m.content, 400)}
                         for m in reversed(msgs)]

    state.trace("stage0", "工程上下文管理", t0,
                history_rounds=len(state.history) // 2,
                project=state.project_name, kb_scope=len(state.kb_ids))
    return state


# ============================================================
# Stage1 智能路由（Intent Agent）
# ============================================================
async def stage1_route(state: RAGState) -> RAGState:
    t0 = time.perf_counter()
    from app.rag.intent_agent import IntentAgent

    agent = IntentAgent()
    decision = await agent.classify(state.query, explicit_domains=state.domains or None)
    plan = agent.build_plan(decision, top_k=state.top_k)

    state.intent = decision.intent
    state.intent_confidence = decision.confidence
    state.need_retrieval = decision.need_retrieval
    state.target_domains = decision.target_domains
    state.out_of_scope = decision.out_of_scope
    state.retrieval_plan = plan

    state.trace("stage1", "Intent Agent 路由", t0,
                intent=decision.intent.value, intent_label=decision.intent.label,
                confidence=decision.confidence,
                need_retrieval=decision.need_retrieval,
                out_of_scope=decision.out_of_scope,
                strategy=plan.strategy, top_k=plan.top_k,
                domains=decision.target_domains)
    return state


# ============================================================
# Stage2 查询改写
# ============================================================
_SYNONYMS = {
    "养护": ["保湿", "浇水", "覆盖", "洒水养护"],
    "拆模": ["模板拆除", "拆除模板"],
    "强度": ["抗压强度", "试块强度", "同条件试块"],
    "保护层": ["钢筋保护层", "保护层厚度"],
    "配合比": ["混凝土配合比", "设计配合比"],
    "基坑": ["深基坑", "基坑支护", "土方开挖"],
    "验收": ["检验批", "验收标准", "质量验收"],
    "裂缝": ["开裂", "龟裂", "裂纹"],
    "渗漏": ["漏水", "渗水", "防水失效"],
    "焊缝": ["焊接质量", "焊缝探伤", "无损检测"],
    "沉降": ["沉降观测", "不均匀沉降", "变形监测"],
    "脚手架": ["外脚手架", "落地式脚手架", "悬挑脚手架"],
}


async def stage2_rewrite(state: RAGState) -> RAGState:
    t0 = time.perf_counter()
    q = state.query.strip()

    # 抽取规范编号（精确锚点，必须保留）
    state.extracted_codes = [re.sub(r"\s+", "", m.group(1)).upper()
                             for m in STANDARD_CODE_RE.finditer(q)]

    parts = [q]
    # 术语扩展
    expand: List[str] = []
    for key, syns in _SYNONYMS.items():
        if key in q:
            expand.extend(syns)
    if expand:
        parts.append(" ".join(dict.fromkeys(expand))[:80])

    # 工程上下文注入（提高领域相关性）
    ctx_bits = [b for b in (state.project_type, state.region) if b]
    if ctx_bits:
        parts.append(" ".join(ctx_bits))

    # 指代消解：出现代词且有历史时，拼上一轮用户问题的关键词
    if state.history and re.search(r"(它|该|这个|上面|刚才|前面|此)", q):
        last_user = next((h["content"] for h in reversed(state.history)
                          if h["role"] == "user"), "")
        if last_user:
            parts.append(" ".join(extract_keywords(last_user, 6)))

    rewritten = " ".join(parts).strip()

    # 有 LLM 时用模型改写，效果更好
    if settings.LLM_PROVIDER == "openai_compatible" and state.history:
        try:
            hist = "\n".join(f"{h['role']}: {truncate(h['content'], 120)}"
                             for h in state.history[-4:])
            res = await get_llm().chat(
                [ChatMessage("user", prompts.REWRITE_PROMPT.format(history=hist, query=q))],
                temperature=0.0, max_tokens=120)
            cand = res.content.strip().strip('"')
            if 3 < len(cand) < 200:
                rewritten = cand + (" " + " ".join(state.extracted_codes)
                                    if state.extracted_codes else "")
        except Exception as e:  # noqa: BLE001
            logger.warning("LLM 查询改写失败，使用规则改写: %s", e)

    state.rewritten_query = rewritten
    # 子查询拆解：多问句场景
    subs = [s.strip() for s in re.split(r"[?？;；]|以及|还有", q) if len(s.strip()) > 5]
    state.sub_queries = subs[:3] if len(subs) > 1 else []

    state.trace("stage2", "查询改写", t0, rewritten=truncate(rewritten, 120),
                codes=state.extracted_codes, sub_queries=state.sub_queries)
    return state


# ============================================================
# Stage3 混合检索
# ============================================================
async def stage3_retrieve(state: RAGState) -> RAGState:
    t0 = time.perf_counter()
    if not state.need_retrieval:
        state.trace("stage3", "混合检索", t0, skipped=True)
        return state

    plan = state.retrieval_plan
    top_k = plan.top_k if plan else (state.top_k or settings.RETRIEVAL_TOP_K)
    threshold = plan.score_threshold if plan else settings.SCORE_THRESHOLD
    vw = plan.vector_weight if plan else settings.HYBRID_VECTOR_WEIGHT
    bw = plan.bm25_weight if plan else settings.HYBRID_BM25_WEIGHT
    domain_priority = plan.domain_priority if plan else state.target_domains

    # ---- 检索缓存（Sprint1 多级缓存接入检索管线）----
    # 键包含查询+范围+检索策略，确保不同意图/参数不串缓存
    from app.core.cache import default_cache, query_cache_key
    cache_key = query_cache_key(
        state.effective_query,
        kb=tuple(state.kb_ids or []), dom=tuple(state.domains or []),
        **(plan.as_ctx() if plan else {"tk": top_k, "th": threshold,
                                       "vw": vw, "bw": bw,
                                       "dp": tuple(domain_priority or [])}),
    )
    cached = default_cache.get(cache_key)
    if cached is not None:
        import copy
        cands = [Candidate(**copy.deepcopy(d)) for d in cached]
        state.candidates = cands
        state.trace("stage3", "混合检索(缓存命中)", t0, recalled=len(cands),
                    strategy=plan.strategy if plan else "default")
        return state

    retriever = get_retriever()
    cands = await retriever.retrieve(
        state.effective_query, top_k=top_k,
        kb_ids=state.kb_ids or None,
        domains=state.domains or None,
        domain_priority=domain_priority,
        vector_weight=vw, bm25_weight=bw, score_threshold=threshold,
        tenant_id=state.tenant_id or "",
    )

    # 子查询补充召回（多跳问题）
    if state.sub_queries:
        seen = {c.chunk_id for c in cands}
        for sq in state.sub_queries:
            extra = await retriever.retrieve(sq, top_k=max(4, top_k // 3),
                                             kb_ids=state.kb_ids or None,
                                             domains=state.domains or None,
                                             domain_priority=domain_priority,
                                             tenant_id=state.tenant_id or "")
            for c in extra:
                if c.chunk_id not in seen:
                    c.fusion_score *= 0.9  # 子查询召回降权
                    cands.append(c)
                    seen.add(c.chunk_id)
        cands.sort(key=lambda x: x.fusion_score, reverse=True)

    # 规范编号硬匹配提权
    if state.extracted_codes:
        for c in cands:
            code = (c.meta.get("standard_code") or "").upper().replace(" ", "")
            if code and any(code.startswith(x[:9]) for x in state.extracted_codes):
                c.fusion_score = round(c.fusion_score * 1.35, 6)
        cands.sort(key=lambda x: x.fusion_score, reverse=True)

    # 写回缓存（L1 内存 + L2 Redis，命中 Sprint1 缓存层）；深拷贝避免后续 stage 改写 meta 污染缓存
    try:
        import copy
        default_cache.set(cache_key, [copy.deepcopy(c.__dict__) for c in cands],
                          ttl=settings.CACHE_TTL_SECONDS)
    except Exception as e:  # noqa: BLE001
        logger.warning("检索缓存写入失败（不影响主流程）: %s", e)

    state.candidates = cands
    state.trace("stage3", "混合检索", t0, recalled=len(cands),
                top_score=round(cands[0].fusion_score, 4) if cands else 0.0,
                strategy=plan.strategy if plan else "default")
    return state


# ============================================================
# Stage4 重排序
# ============================================================
async def stage4_rerank(state: RAGState) -> RAGState:
    t0 = time.perf_counter()
    if not state.candidates:
        state.trace("stage4", "重排序", t0, skipped=True)
        return state

    top_n = settings.RERANK_TOP_N
    docs = [c.content for c in state.candidates]
    pairs = await get_reranker().rerank(state.effective_query, docs, top_n=min(top_n * 3, len(docs)))

    reranked: List[Candidate] = []
    for idx, score in pairs:
        c = state.candidates[idx]
        boost = 1.0
        if c.meta.get("is_mandatory"):
            boost *= 1.10          # 强制性条文优先
        if c.meta.get("governance_status") == "deprecated":
            boost *= 0.55          # 已废弃文档降权
        elif c.meta.get("governance_status") == "need_update":
            boost *= 0.85
        # rerank 分与融合分加权，避免单一信号失真
        final = round((0.65 * score + 0.35 * min(c.fusion_score, 1.0)) * boost, 6)
        c.meta["rerank_score"] = round(score, 6)
        c.meta["final_score"] = final
        reranked.append(c)

    reranked.sort(key=lambda x: x.meta.get("final_score", 0.0), reverse=True)
    kept = reranked[:top_n]

    # ---- 相关性门槛：拦截"知识库其实没覆盖，却被迫凑出引用"的情况 ----
    # 判据一：top1 必须达到 MIN_RELEVANCE_SCORE
    # 判据二：至少 MIN_SUPPORT_COUNT 条达到 MIN_RELEVANCE_SCORE*MIN_SUPPORT_RATIO
    #        （无关问题的典型特征是仅 top1 擦边、其余分数断崖式下跌）
    floor = settings.MIN_RELEVANCE_SCORE
    support_floor = floor * settings.MIN_SUPPORT_RATIO
    top_score = kept[0].meta.get("final_score", 0.0) if kept else 0.0
    support = sum(1 for c in kept if c.meta.get("final_score", 0.0) >= support_floor)
    relevant = bool(kept) and top_score >= floor and support >= settings.MIN_SUPPORT_COUNT

    if not relevant:
        state.below_relevance_floor = True
        state.rejected = kept          # 保留候选供前端"召回片段"面板排查
        state.reranked = []
        state.trace("stage4", "重排序", t0, input=len(state.candidates), output=0,
                    top_score=round(top_score, 4), support=support,
                    rejected_by_floor=True,
                    reason=f"最高分 {top_score:.3f} / 支撑 {support} 条未达门槛"
                           f"（需 ≥{floor} 且 ≥{settings.MIN_SUPPORT_COUNT} 条 ≥{support_floor:.3f}）")
        return state

    state.reranked = kept
    state.trace("stage4", "重排序", t0, input=len(state.candidates),
                output=len(state.reranked), support=support,
                top_score=round(top_score, 4))
    return state


# ============================================================
# Stage5 上下文构建
# ============================================================
async def stage5_build_context(state: RAGState, db: Session) -> RAGState:
    t0 = time.perf_counter()
    if not state.reranked:
        state.context_text = ""
        state.trace("stage5", "上下文构建", t0, chunks=0)
        return state

    # 补齐文档元数据（标题、规范编号、治理状态）
    doc_ids = list({c.doc_id for c in state.reranked if c.doc_id})
    doc_map = {}
    if doc_ids:
        for d in db.query(Document).filter(Document.id.in_(doc_ids)).all():
            doc_map[d.id] = d

    blocks: List[str] = []
    used: List[Candidate] = []
    budget = settings.MAX_CONTEXT_CHARS
    seen_hash: set[str] = set()

    for c in state.reranked:
        body = (c.content or "").strip()
        if not body:
            continue
        # 近似去重：前 80 字 + 长度
        sig = body[:80] + str(len(body) // 50)
        if sig in seen_hash:
            continue
        seen_hash.add(sig)

        d = doc_map.get(c.doc_id)
        title = d.title if d else c.meta.get("doc_title", "未知文档")
        code = (d.standard_code if d else "") or c.meta.get("standard_code", "")
        gov = d.governance_status if d else "valid"
        sec = c.meta.get("section_path", "")
        clause = c.meta.get("clause_no", "")
        page = c.meta.get("page_no", 0)

        head = f"[{len(used) + 1}] 《{title}》"
        if code:
            head += f"（{code}）"
        if sec:
            head += f" | 章节：{sec}"
        if clause:
            head += f" | 条文：{clause}"
        if page:
            head += f" | 第{page}页"
        if gov == "deprecated":
            head += " | ⚠已废弃，仅供参考"
        elif gov == "need_update":
            head += " | ⚠待更新"

        block = f"{head}\n{body}"
        if len(block) > budget:
            if budget < 300:
                break
            block = block[:budget] + "…"
        budget -= len(block)
        blocks.append(block)
        used.append(c)
        if budget <= 200:
            break

    state.context_chunks = used
    state.context_text = "\n\n".join(blocks)
    state.trace("stage5", "上下文构建", t0, chunks=len(used),
                chars=len(state.context_text))
    return state


# ============================================================
# Stage6 智能生成 + 引用增强
# ============================================================
async def stage6_generate(state: RAGState, db: Session) -> RAGState:
    t0 = time.perf_counter()

    if state.intent == QueryIntent.CHITCHAT:
        state.answer = ("我是 TerraForge 土木工程智能知识助手，可以帮你查询施工规范条文、"
                        "分析质量问题、检索工程案例、生成施工方案要点。"
                        "所有回答都基于已入库的工程资料并标注出处。请描述你的工程问题。")
        state.confidence, state.confidence_level = 1.0, ConfidenceLevel.HIGH
        state.need_human_review = False
        state.trace("stage6", "智能生成", t0, mode="chitchat")
        return state

    if state.below_relevance_floor:
        state.answer = prompts.BELOW_FLOOR_ANSWER
        state.trace("stage6", "智能生成", t0, mode="below_floor")
        return state

    if not state.context_chunks:
        state.answer = prompts.NO_CONTEXT_ANSWER
        state.trace("stage6", "智能生成", t0, mode="no_context")
        return state

    history_block = ""
    if state.history:
        hist = "\n".join(f"{'用户' if h['role'] == 'user' else '助手'}：{truncate(h['content'], 200)}"
                         for h in state.history[-4:])
        history_block = f"【历史对话】\n{hist}\n\n"

    user_msg = prompts.USER_TEMPLATE.format(
        context_block=f"【参考资料】\n{state.context_text}",
        history_block=history_block,
        project_name=state.project_name or "未指定",
        project_type=state.project_type or "未指定",
        discipline=state.discipline or "general",
        region=state.region or "未指定",
        query=state.query,
    )
    messages = [ChatMessage("system", prompts.build_system_prompt(state.intent)),
                ChatMessage("user", user_msg)]

    try:
        res = await get_llm().chat(messages)
        state.answer = res.content.strip()
        state.token_usage = res.usage or {}
    except Exception as e:  # noqa: BLE001
        logger.error("生成失败: %s", e)
        state.error = str(e)
        state.answer = ("生成环节调用失败，以下为检索到的原始工程依据，请人工研判：\n\n"
                        + truncate(state.context_text, 2000))

    # ---- 引用增强：只保留答案实际引用的角标 ----
    cited = {int(n) for n in re.findall(r"\[(\d{1,2})\]", state.answer)}
    doc_ids = list({c.doc_id for c in state.context_chunks if c.doc_id})
    doc_map = {d.id: d for d in db.query(Document).filter(Document.id.in_(doc_ids)).all()} \
        if doc_ids else {}

    citations: List[CitationItem] = []
    for i, c in enumerate(state.context_chunks, start=1):
        if cited and i not in cited:
            continue
        d = doc_map.get(c.doc_id)
        citations.append(CitationItem(
            index_no=i, chunk_id=c.chunk_id, doc_id=c.doc_id,
            doc_title=d.title if d else c.meta.get("doc_title", ""),
            standard_code=(d.standard_code if d else "") or c.meta.get("standard_code", ""),
            section_path=c.meta.get("section_path", ""),
            clause_no=c.meta.get("clause_no", ""),
            page_no=int(c.meta.get("page_no", 0) or 0),
            snippet=truncate(re.sub(r"^【[^】]*】\n?", "", c.content).strip(), 220),
            score=float(c.meta.get("final_score", c.fusion_score)),
            domain=c.domain,
        ))
    # 答案未标角标时，退回展示全部上下文来源（保证可追溯）
    if not citations:
        for i, c in enumerate(state.context_chunks, start=1):
            d = doc_map.get(c.doc_id)
            citations.append(CitationItem(
                index_no=i, chunk_id=c.chunk_id, doc_id=c.doc_id,
                doc_title=d.title if d else "", 
                standard_code=(d.standard_code if d else ""),
                section_path=c.meta.get("section_path", ""),
                clause_no=c.meta.get("clause_no", ""),
                page_no=int(c.meta.get("page_no", 0) or 0),
                snippet=truncate(c.content, 220),
                score=float(c.meta.get("final_score", c.fusion_score)),
                domain=c.domain))
    state.citations = citations
    state.trace("stage6", "智能生成与引用增强", t0,
                answer_chars=len(state.answer), citations=len(citations),
                cited_indexes=sorted(cited))
    return state


# ============================================================
# Stage7 可信度评估 + 治理闭环
# ============================================================
async def stage7_governance(state: RAGState) -> RAGState:
    t0 = time.perf_counter()

    if state.intent == QueryIntent.CHITCHAT:
        state.trace("stage7", "知识治理闭环", t0, skipped=True)
        return state

    if not state.context_chunks:
        state.confidence = 0.0
        state.confidence_level = ConfidenceLevel.LOW
        state.need_human_review = True
        if state.below_relevance_floor:
            state.review_hint = ("检索命中但相关性未达门槛（证据不足以支撑结论），"
                                 "已按'无证据不作答'原则拦截，建议补充知识库或改写问题。")
            state.trace("stage7", "知识治理闭环", t0, confidence=0.0,
                        gap=True, reason="below_relevance_floor")
        else:
            state.review_hint = "知识库零召回，答案不具备依据，必须人工确认或补充资料。"
            state.trace("stage7", "知识治理闭环", t0, confidence=0.0, gap=True)
        # 安全类问题强制提示（即便被地板拦截，仍须安全专项审核）
        if any(k in state.query for k in ("安全", "坍塌", "倾覆", "危大", "临边", "高处", "起重")):
            state.need_human_review = True
            state.review_hint = (state.review_hint + " 涉及施工安全，实施前必须经安全专项审核。").strip()
        return state

    scores = [float(c.meta.get("final_score", c.fusion_score)) for c in state.context_chunks]
    top = max(scores)
    avg = sum(scores) / len(scores)

    # 信号1：检索相关性
    s_rel = min(1.0, 0.6 * top + 0.4 * avg)
    # 信号2：证据数量
    s_cnt = min(1.0, len(state.context_chunks) / 4.0)
    # 信号3：来源一致性（多篇不同文档相互印证）
    s_div = min(1.0, len({c.doc_id for c in state.context_chunks}) / 3.0)
    # 信号4：答案引用密度
    cited = len({int(n) for n in re.findall(r"\[(\d{1,2})\]", state.answer)})
    s_cite = min(1.0, cited / max(1, min(3, len(state.context_chunks))))
    # 信号5：问答词面覆盖
    q_tok, a_tok = set(tokenize(state.query)), set(tokenize(state.answer))
    s_cov = len(q_tok & a_tok) / (len(q_tok) or 1)
    # 信号6：时效性惩罚
    penalty = 1.0
    if any(c.meta.get("governance_status") == "deprecated" for c in state.context_chunks):
        penalty *= 0.75
    if "未提供" in state.answer or "知识库未" in state.answer:
        penalty *= 0.6

    conf = (0.34 * s_rel + 0.14 * s_cnt + 0.14 * s_div +
            0.24 * s_cite + 0.14 * s_cov) * penalty
    state.confidence = round(min(1.0, conf), 4)

    if state.confidence >= settings.CONFIDENCE_HIGH:
        state.confidence_level = ConfidenceLevel.HIGH
        state.need_human_review = False
        state.review_hint = ""
    elif state.confidence >= settings.CONFIDENCE_LOW:
        state.confidence_level = ConfidenceLevel.MEDIUM
        state.need_human_review = False
        state.review_hint = "证据链中等，涉及关键工序或安全事项时建议由技术负责人复核。"
    else:
        state.confidence_level = ConfidenceLevel.LOW
        state.need_human_review = True
        state.review_hint = "可信度偏低：检索证据不充分或与问题匹配度不高，请人工确认并考虑补充知识库。"

    # 安全类问题强制提示
    if any(k in state.query for k in ("安全", "坍塌", "倾覆", "危大", "临边", "高处", "起重")):
        state.need_human_review = True
        state.review_hint = (state.review_hint + " 涉及施工安全，实施前必须经安全专项审核。").strip()

    state.trace("stage7", "知识治理闭环", t0,
                confidence=state.confidence, level=state.confidence_level.value,
                signals={"rel": round(s_rel, 3), "cnt": round(s_cnt, 3),
                         "div": round(s_div, 3), "cite": round(s_cite, 3),
                         "cov": round(s_cov, 3), "penalty": penalty},
                need_review=state.need_human_review)
    return state
