"""
RAG Pipeline 编排器
==================
优先使用 LangGraph 构建有向状态图；未安装时自动降级为等价的顺序执行器，
两种模式的阶段顺序、跳过逻辑与产出完全一致。

图结构：
    stage0 -> stage1 -> [need_retrieval?]
                          ├─ 否 -> stage6 -> stage7 -> END
                          └─ 是 -> stage2 -> stage3 -> stage4 -> stage5 -> stage6 -> stage7 -> END
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.core.logging import get_logger, new_trace_id
from app.rag import stages
from app.rag.state import RAGState

logger = get_logger(__name__)

try:  # pragma: no cover
    from langgraph.graph import END, StateGraph
    _HAS_LANGGRAPH = True
except Exception:  # noqa: BLE001
    _HAS_LANGGRAPH = False


class RAGPipeline:
    """Stage0-Stage7 全流程编排。"""

    def __init__(self):
        self._graph = None
        if _HAS_LANGGRAPH:
            try:
                self._graph = self._build_graph()
                logger.info("RAG Pipeline 使用 LangGraph 编排")
            except Exception as e:  # noqa: BLE001
                logger.warning("LangGraph 构图失败，降级顺序执行: %s", e)
        else:
            logger.info("RAG Pipeline 使用内置顺序编排（未安装 LangGraph）")

    # ---------------- LangGraph ----------------
    def _build_graph(self):
        db_holder: dict = {}

        async def n0(s: RAGState):
            return await stages.stage0_context(s, db_holder["db"])

        async def n1(s: RAGState):
            return await stages.stage1_route(s)

        async def n2(s: RAGState):
            return await stages.stage2_rewrite(s)

        async def n3(s: RAGState):
            return await stages.stage3_retrieve(s)

        async def n4(s: RAGState):
            return await stages.stage4_rerank(s)

        async def n5(s: RAGState):
            return await stages.stage5_build_context(s, db_holder["db"])

        async def n6(s: RAGState):
            return await stages.stage6_generate(s, db_holder["db"])

        async def n7(s: RAGState):
            return await stages.stage7_governance(s)

        g = StateGraph(RAGState)
        for name, fn in [("stage0", n0), ("stage1", n1), ("stage2", n2), ("stage3", n3),
                         ("stage4", n4), ("stage5", n5), ("stage6", n6), ("stage7", n7)]:
            g.add_node(name, fn)
        g.set_entry_point("stage0")
        g.add_edge("stage0", "stage1")
        g.add_conditional_edges("stage1",
                                lambda s: "retrieve" if s.need_retrieval else "direct",
                                {"retrieve": "stage2", "direct": "stage6"})
        g.add_edge("stage2", "stage3")
        g.add_edge("stage3", "stage4")
        g.add_edge("stage4", "stage5")
        g.add_edge("stage5", "stage6")
        g.add_edge("stage6", "stage7")
        g.add_edge("stage7", END)

        compiled = g.compile()
        compiled._tf_db_holder = db_holder  # type: ignore[attr-defined]
        return compiled

    # ---------------- 执行 ----------------
    async def run(self, state: RAGState, db: Session) -> RAGState:
        new_trace_id()
        logger.info("RAG 开始 | query=%s | kb=%s", state.query[:60], state.kb_ids)
        try:
            if self._graph is not None:
                self._graph._tf_db_holder["db"] = db  # type: ignore[attr-defined]
                result = await self._graph.ainvoke(state)
                state = result if isinstance(result, RAGState) else _coerce(result, state)
            else:
                state = await self._run_sequential(state, db)
        except Exception as e:  # noqa: BLE001
            logger.exception("RAG 执行异常")
            state.error = str(e)
            if not state.answer:
                state.answer = f"处理过程中发生异常，请稍后重试或联系管理员。（{e}）"
        logger.info("RAG 完成 | 耗时=%dms | 置信度=%.3f | 引用=%d",
                    state.latency_ms, state.confidence, len(state.citations))
        return state

    @staticmethod
    async def _run_sequential(state: RAGState, db: Session) -> RAGState:
        state = await stages.stage0_context(state, db)
        state = await stages.stage1_route(state)
        if state.need_retrieval:
            state = await stages.stage2_rewrite(state)
            state = await stages.stage3_retrieve(state)
            state = await stages.stage4_rerank(state)
            state = await stages.stage5_build_context(state, db)
        state = await stages.stage6_generate(state, db)
        state = await stages.stage7_governance(state)
        return state


def _coerce(result, fallback: RAGState) -> RAGState:
    """LangGraph 可能返回 dict，转回 RAGState。"""
    if isinstance(result, dict):
        for k, v in result.items():
            if hasattr(fallback, k):
                setattr(fallback, k, v)
    return fallback


_pipeline: Optional[RAGPipeline] = None


def get_pipeline() -> RAGPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = RAGPipeline()
    return _pipeline
