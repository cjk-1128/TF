"""Word 解析：保留标题层级，表格转 Markdown。"""
from __future__ import annotations

from pathlib import Path

from app.core.exceptions import DocumentParseError
from app.ingestion.parsers.base import BaseParser, ParsedBlock, ParsedDocument
from app.utils.text import clean_text


class DocxParser(BaseParser):
    suffixes = (".docx", ".doc")

    def parse(self, path: Path) -> ParsedDocument:
        try:
            from docx import Document as DocxDocument
            from docx.oxml.ns import qn
            from docx.table import Table
            from docx.text.paragraph import Paragraph
        except ImportError as e:  # pragma: no cover
            raise DocumentParseError("未安装 python-docx") from e

        try:
            d = DocxDocument(str(path))
        except Exception as e:  # noqa: BLE001
            raise DocumentParseError(f"Word 打开失败（.doc 需先转 .docx）: {e}")

        doc = ParsedDocument(meta={"source": path.name})
        for child in d.element.body.iterchildren():
            if child.tag == qn("w:p"):
                p = Paragraph(child, d)
                text = clean_text(p.text)
                if not text:
                    continue
                style = p.style.name if p.style is not None else ""
                if style.lower().startswith("heading") or style.startswith("标题"):
                    lvl = "".join(c for c in style if c.isdigit())
                    doc.blocks.append(ParsedBlock(
                        text=text, block_type="heading",
                        heading_level=int(lvl) if lvl else 1,
                        meta={"heading_title": text},
                    ))
                else:
                    doc.blocks.append(ParsedBlock(text=text))
            elif child.tag == qn("w:tbl"):
                tb = Table(child, d)
                lines = []
                for i, row in enumerate(tb.rows):
                    cells = [c.text.strip().replace("\n", " ") for c in row.cells]
                    lines.append("| " + " | ".join(cells) + " |")
                    if i == 0:
                        lines.append("|" + "---|" * len(cells))
                if lines:
                    doc.blocks.append(ParsedBlock(text="\n".join(lines), block_type="table"))
        if not doc.blocks:
            raise DocumentParseError("Word 文档为空")
        return doc
