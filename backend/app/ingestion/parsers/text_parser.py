"""纯文本 / Markdown 解析。"""
from __future__ import annotations

import re
from pathlib import Path

from app.ingestion.parsers.base import BaseParser, ParsedBlock, ParsedDocument
from app.utils.text import clean_text

_MD_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
_NUM_HEADING = re.compile(r"^\s*(\d{1,2}(?:\.\d{1,3}){0,3})\s+(\S[^\n]{0,60})$")


class TextParser(BaseParser):
    suffixes = (".txt", ".md", ".markdown")

    def parse(self, path: Path) -> ParsedDocument:
        raw = path.read_text(encoding="utf-8", errors="ignore")
        return self.parse_text(raw, source=path.name)

    @staticmethod
    def parse_text(raw: str, source: str = "inline") -> ParsedDocument:
        doc = ParsedDocument(meta={"source": source})
        for para in re.split(r"\n\s*\n", clean_text(raw)):
            para = para.strip()
            if not para:
                continue
            first = para.split("\n")[0]
            m = _MD_HEADING.match(first)
            if m and len(para) < 200:
                doc.blocks.append(ParsedBlock(
                    text=para, block_type="heading", heading_level=len(m.group(1)),
                    meta={"heading_title": m.group(2).strip()}))
                continue
            n = _NUM_HEADING.match(first) if len(para) < 90 else None
            if n:
                doc.blocks.append(ParsedBlock(
                    text=para, block_type="heading",
                    heading_level=n.group(1).count(".") + 1,
                    meta={"clause_no": n.group(1), "heading_title": n.group(2).strip()}))
                continue
            doc.blocks.append(ParsedBlock(text=para))
        return doc
