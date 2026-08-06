"""
零依赖本地实现（无需任何 API Key 即可跑通全链路）
===============================================
- HashEmbedding : 基于 jieba 分词 + 哈希映射 + 子词 n-gram 的确定性稠密向量，
                  语义能力弱于真实模型，但可保证同义词面重叠时的余弦相似度有效，
                  适合开发调试与 CI 测试。
- RuleReranker  : 多信号规则重排（词面覆盖率 + 短语命中 + 强条加权 + 位置衰减）。
- MockLLM       : 抽取式生成器，严格基于上下文片段组织答案并输出角标引用，
                  完全遵守"所有回答必须基于知识库"的开发规则。
"""
from __future__ import annotations

import hashlib
import math
import re
from typing import AsyncIterator, List

from app.core.config import settings
from app.llm.base import (BaseEmbedding, BaseLLM, BaseReranker, ChatMessage,
                          LLMResult)
from app.utils.text import tokenize

_TOKEN_RE = re.compile(r"[\u4e00-\u9fa5]+|[a-zA-Z]+|\d+(?:\.\d+)*")


class HashEmbedding(BaseEmbedding):
    def __init__(self, dim: int | None = None):
        self.dim = dim or settings.EMBEDDING_DIM

    def _vec(self, text: str) -> List[float]:
        v = [0.0] * self.dim
        toks = tokenize(text)
        if not toks:
            return v
        # 词频 + bigram，缓解纯词袋的顺序无关问题
        grams = list(toks)
        grams += [toks[i] + toks[i + 1] for i in range(len(toks) - 1)]
        for g in grams:
            h = hashlib.md5(g.encode("utf-8")).digest()
            idx = int.from_bytes(h[:4], "big") % self.dim
            sign = 1.0 if h[4] % 2 == 0 else -1.0
            # 长词权重更高（工程术语通常较长）
            v[idx] += sign * (1.0 + 0.15 * min(len(g), 8))
        norm = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / norm for x in v]

    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        return [self._vec(t) for t in texts]


class RuleReranker(BaseReranker):
    """无模型依赖的规则重排器。"""

    async def rerank(self, query: str, docs: List[str], top_n: int) -> List[tuple[int, float]]:
        if not docs:
            return []
        q_tokens = set(tokenize(query))
        q_raw = query.lower()
        scored: list[tuple[int, float]] = []
        for i, d in enumerate(docs):
            d_tokens = set(tokenize(d))
            if not q_tokens:
                cover = 0.0
            else:
                cover = len(q_tokens & d_tokens) / len(q_tokens)
            # 短语连续命中加分
            phrase = 0.0
            for n in (4, 3, 2):
                for j in range(len(q_raw) - n + 1):
                    if q_raw[j:j + n] in d.lower():
                        phrase = max(phrase, n / 6.0)
                        break
                if phrase:
                    break
            # 规范条文号命中
            clause_bonus = 0.0
            for m in re.findall(r"\d+(?:\.\d+){1,3}", query):
                if m in d:
                    clause_bonus = 0.25
                    break
            # 强制性条文标志
            mandatory = 0.1 if ("必须" in d or "严禁" in d or "不得" in d or "应" in d[:80]) else 0.0
            # 位置衰减（保留一路召回顺序的先验）
            pos = 1.0 / (1.0 + 0.05 * i)
            score = (0.55 * cover + 0.20 * phrase + clause_bonus + mandatory) * pos
            scored.append((i, round(min(score, 1.0), 6)))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_n]


class LexicalInteractionReranker(BaseReranker):
    """本地 Cross-Encoder 风格重排器（零依赖，Sprint 2）。

    真正的 CrossEncoder 用单一模型对 (query, doc) 做联合打分；本地无模型时，
    这里用"向量交互 + 词面交互"联合估计相关性，逼近 CrossEncoder 的效果：
      - 向量交互：query 与每个 doc 的余弦相似（表达联合语义匹配），
        复用 Embedding 且命中 Sprint1 缓存，不会重复推理；
      - 词面交互：词面覆盖率 + 短语连续命中 + 条文号 + 强制性标志，
        与 RuleReranker 同源，作为补充信号。
    因此该重排器比纯规则的 RuleReranker 更贴近"交叉编码"，且无需任何外部服务。
    """

    async def rerank(self, query: str, docs: List[str], top_n: int) -> List[tuple[int, float]]:
        if not docs:
            return []

        # 1) 向量交互（联合语义匹配）
        cos: List[float] = [0.0] * len(docs)
        try:
            from app.llm.factory import get_embedding
            emb = get_embedding()
            qv = await emb.embed_query(query)
            dvecs = await emb.embed_texts(docs)
            cos = [self._cos(qv, dv) for dv in dvecs]
        except Exception as e:  # noqa: BLE001
            logger.warning("本地 CrossEncoder 向量交互失败，退纯词面: %s", e)

        # 2) 词面交互特征 + 融合
        q_tokens = set(tokenize(query))
        q_raw = query.lower()
        scored: List[tuple[int, float]] = []
        for i, d in enumerate(docs):
            lex = self._lexical(query, d, q_tokens, q_raw)
            # 向量为主信号（0.65），词面为辅（0.35）
            score = 0.65 * max(0.0, cos[i]) + 0.35 * lex
            scored.append((i, round(min(score, 1.0), 6)))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_n]

    @staticmethod
    def _cos(a: list, b: list) -> float:
        if not a or not b:
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        na = sum(x * x for x in a) ** 0.5
        nb = sum(x * x for x in b) ** 0.5
        if na == 0 or nb == 0:
            return 0.0
        return dot / (na * nb)

    @staticmethod
    def _lexical(query: str, doc: str, q_tokens: set, q_raw: str) -> float:
        d_tokens = set(tokenize(doc))
        cover = (len(q_tokens & d_tokens) / len(q_tokens)) if q_tokens else 0.0
        phrase = 0.0
        for n in (4, 3, 2):
            for j in range(len(q_raw) - n + 1):
                if q_raw[j:j + n] in doc.lower():
                    phrase = max(phrase, n / 6.0)
                    break
            if phrase:
                break
        clause_bonus = 0.0
        for m in re.findall(r"\d+(?:\.\d+){1,3}", query):
            if m in doc:
                clause_bonus = 0.25
                break
        mandatory = 0.1 if ("必须" in doc or "严禁" in doc or "不得" in doc) else 0.0
        return 0.55 * cover + 0.20 * phrase + clause_bonus + mandatory


class MockLLM(BaseLLM):
    """
    抽取式"生成"：不编造内容，只从上下文中挑选与问题最相关的句子重组，
    并保留 [n] 角标。用于无 API Key 场景下的端到端演示与测试。
    """

    async def chat(self, messages: List[ChatMessage], *, temperature=None,
                   max_tokens=None) -> LLMResult:
        user = next((m.content for m in reversed(messages) if m.role == "user"), "")
        content = self._compose(user)
        return LLMResult(
            content=content,
            usage={"prompt_tokens": sum(len(m.content) for m in messages) // 2,
                   "completion_tokens": len(content) // 2,
                   "total_tokens": (sum(len(m.content) for m in messages) + len(content)) // 2},
            model="mock-extractive",
        )

    async def stream(self, messages: List[ChatMessage], *, temperature=None) -> AsyncIterator[str]:
        res = await self.chat(messages)
        buf = res.content
        for i in range(0, len(buf), 24):
            yield buf[i:i + 24]

    # ---------------- 内部 ----------------
    @staticmethod
    def _compose(prompt: str) -> str:
        # Prompt 结构：... 【参考资料】\n[1] ...\n[2] ... 【用户问题】xxx
        ctx_part = ""
        question = ""
        if "【参考资料】" in prompt:
            ctx_part = prompt.split("【参考资料】", 1)[1]
        if "【用户问题】" in ctx_part:
            ctx_part, question = ctx_part.split("【用户问题】", 1)
        question = question.strip().split("\n")[0]
        if not ctx_part.strip():
            return "当前知识库未提供相关依据，无法给出可靠结论。建议补充相关规范或案例文档后重试，或联系对应专业负责人确认。"

        blocks = re.split(r"\n(?=\[\d+\])", ctx_part.strip())
        q_tokens = set(tokenize(question))
        picked: list[tuple[int, str, float, str]] = []
        for b in blocks:
            b = b.strip()
            m = re.match(r"\[(\d+)\]\s*(.*)", b.split("\n", 1)[0])
            if not m:
                continue
            idx, source = int(m.group(1)), m.group(2).strip()
            body = b.split("\n", 1)[1] if "\n" in b else ""
            # 去掉切片正文里的章节路径前缀与 Markdown 标题符号
            body = re.sub(r"【[^】]{0,120}】", " ", body)
            body = re.sub(r"^\s*#{1,6}\s*", "", body, flags=re.M)
            body = re.sub(r"\s+", " ", body).strip()
            if len(body) < 10:
                continue
            sents = [s.strip() for s in re.split(r"(?<=[。；！？;!?])", body)
                     if len(s.strip()) > 10]
            best, best_s = (sents[0] if sents else body[:200]), 0.0
            for s in sents:
                st = set(tokenize(s))
                sc = len(q_tokens & st) / (len(q_tokens) or 1)
                # 含数字/单位的句子更可能是工程结论
                if re.search(r"\d+\s*(?:d|天|mm|MPa|N/mm|m³|%|kg|℃)", s):
                    sc += 0.12
                if sc > best_s:
                    best_s, best = sc, s
            picked.append((idx, best, best_s, source))

        picked.sort(key=lambda x: x[2], reverse=True)
        top, seen = [], set()
        for item in picked:
            sig = item[1][:40]
            if sig in seen:
                continue
            seen.add(sig)
            top.append(item)
            if len(top) >= 4:
                break
        if not top:
            return "当前知识库未提供相关依据，建议补充资料后重试。"

        lines = ["**结论与依据**", ""]
        for idx, sent, _, source in top:
            sent = sent if len(sent) <= 320 else sent[:320] + "…"
            lines.append(f"- {sent} [{idx}]")
        lines += [
            "",
            "**说明**：以上内容直接摘自知识库检索到的工程资料，未作推断性扩展。"
            "如需结合具体工程条件形成实施方案，请由项目技术负责人复核后执行。",
        ]
        return "\n".join(lines)
