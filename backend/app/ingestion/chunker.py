"""
工程语义切分器
=============
针对规范类文档的特点做结构感知切分：
1. 以章节标题为硬边界，切片继承完整 section_path（如 "5 混凝土 > 5.2 养护 > 5.2.1"）；
2. 表格块不拆散（表格拆开后语义完全丢失）；
3. 段落按目标长度累积，超长则按句号切分，相邻切片保留 overlap；
4. 自动识别条文号、强制性条文标志、页码。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List

from app.core.config import settings
from app.ingestion.parsers.base import ParsedBlock, ParsedDocument
from app.utils.text import (clean_text, extract_clause_no, is_mandatory_clause)

_SENT_SPLIT = re.compile(r"(?<=[。；！？!?;])")


@dataclass
class ChunkData:
    content: str
    seq: int = 0
    section_path: str = ""
    clause_no: str = ""
    page_no: int = 0
    is_mandatory: bool = False
    extra: Dict = field(default_factory=dict)

    @property
    def char_count(self) -> int:
        return len(self.content)


class EngineeringChunker:
    def __init__(self, chunk_size: int | None = None, overlap: int | None = None,
                 min_size: int | None = None):
        self.chunk_size = chunk_size or settings.CHUNK_SIZE
        self.overlap = overlap or settings.CHUNK_OVERLAP
        self.min_size = min_size or settings.MIN_CHUNK_SIZE

    # ---------------- 主入口 ----------------
    def split(self, doc: ParsedDocument) -> List[ChunkData]:
        chunks: List[ChunkData] = []
        heading_stack: List[tuple[int, str]] = []
        buffer: List[ParsedBlock] = []

        def flush():
            if buffer:
                chunks.extend(self._flush_buffer(buffer, self._path(heading_stack)))
                buffer.clear()

        for blk in doc.blocks:
            if blk.block_type == "heading":
                flush()
                lvl = max(1, blk.heading_level or 1)
                title = blk.meta.get("heading_title") or blk.text.strip()
                while heading_stack and heading_stack[-1][0] >= lvl:
                    heading_stack.pop()
                heading_stack.append((lvl, title[:80]))
                # 标题本身也作为内容前缀参与下一块
                buffer.append(blk)
            elif blk.block_type == "table":
                flush()
                chunks.extend(self._flush_buffer([blk], self._path(heading_stack),
                                                 force_single=True))
            else:
                buffer.append(blk)
                if sum(len(b.text) for b in buffer) >= self.chunk_size:
                    flush()
        flush()

        # 重排序号 + 过滤太短的碎片（标题类除外）
        out: List[ChunkData] = []
        for c in chunks:
            if c.char_count < self.min_size and not c.clause_no:
                continue
            c.seq = len(out)
            out.append(c)
        return out

    # ---------------- 内部 ----------------
    @staticmethod
    def _path(stack: List[tuple[int, str]]) -> str:
        return " > ".join(t for _, t in stack)

    def _flush_buffer(self, blocks: List[ParsedBlock], section_path: str,
                      force_single: bool = False) -> List[ChunkData]:
        text = clean_text("\n".join(b.text for b in blocks))
        if not text:
            return []
        page_no = next((b.page_no for b in blocks if b.page_no), 0)
        clause = ""
        for b in blocks:
            clause = b.meta.get("clause_no") or extract_clause_no(b.text)
            if clause:
                break

        if force_single or len(text) <= self.chunk_size:
            return [ChunkData(content=self._with_prefix(section_path, text),
                              section_path=section_path, clause_no=clause,
                              page_no=page_no,
                              is_mandatory=is_mandatory_clause(text),
                              extra={"block_type": blocks[0].block_type})]

        # 长文本：按句切，累积到 chunk_size，带 overlap
        sents = [s for s in _SENT_SPLIT.split(text) if s.strip()]
        chunks: List[ChunkData] = []
        buf = ""
        for s in sents:
            if len(buf) + len(s) > self.chunk_size and buf:
                chunks.append(self._make(buf, section_path, clause, page_no))
                buf = (buf[-self.overlap:] if self.overlap else "") + s
            else:
                buf += s
        if buf.strip():
            chunks.append(self._make(buf, section_path, clause, page_no))
        return chunks

    def _make(self, text: str, section_path: str, clause: str, page: int) -> ChunkData:
        t = text.strip()
        return ChunkData(content=self._with_prefix(section_path, t),
                         section_path=section_path,
                         clause_no=extract_clause_no(t) or clause,
                         page_no=page, is_mandatory=is_mandatory_clause(t))

    @staticmethod
    def _with_prefix(section_path: str, text: str) -> str:
        """把章节路径写进正文，让向量化时带上层级语义（关键的检索增益点）。"""
        if section_path and not text.startswith(section_path.split(" > ")[-1]):
            return f"【{section_path}】\n{text}"
        return text
