"""PDF 解析：逐页抽取，识别章节标题与条文号。"""
from __future__ import annotations

import re
from pathlib import Path

from app.core.exceptions import DocumentParseError
from app.core.logging import get_logger
from app.ingestion.parsers.base import BaseParser, ParsedBlock, ParsedDocument
from app.utils.text import clean_text

logger = get_logger(__name__)

# 章节标题：1 总则 / 5.2 混凝土养护 / 5.2.1 xxx
_HEADING_RE = re.compile(r"^\s*(\d{1,2}(?:\.\d{1,3}){0,3})\s+([^\n]{2,60})$")
_APPENDIX_RE = re.compile(r"^\s*附录\s*[A-Z]\s*[^\n]{0,60}$")


class PDFParser(BaseParser):
    suffixes = (".pdf",)

    def parse(self, path: Path) -> ParsedDocument:
        try:
            from pypdf import PdfReader
        except ImportError as e:  # pragma: no cover
            raise DocumentParseError("未安装 pypdf") from e

        try:
            reader = PdfReader(str(path))
        except Exception as e:  # noqa: BLE001
            raise DocumentParseError(f"PDF 打开失败: {e}")

        doc = ParsedDocument(meta={"page_count": len(reader.pages), "source": path.name})
        for pno, page in enumerate(reader.pages, start=1):
            try:
                raw = page.extract_text() or ""
            except Exception as e:  # noqa: BLE001
                logger.warning("第 %d 页解析失败: %s", pno, e)
                continue
            text = clean_text(raw)
            if not text:
                continue
            for para in re.split(r"\n\s*\n", text):
                para = para.strip()
                if len(para) < 2:
                    continue
                m = _HEADING_RE.match(para.split("\n")[0]) if len(para) < 80 else None
                if m:
                    doc.blocks.append(ParsedBlock(
                        text=para, page_no=pno, block_type="heading",
                        heading_level=m.group(1).count(".") + 1,
                        meta={"clause_no": m.group(1), "heading_title": m.group(2).strip()},
                    ))
                elif _APPENDIX_RE.match(para):
                    doc.blocks.append(ParsedBlock(text=para, page_no=pno,
                                                  block_type="heading", heading_level=1))
                else:
                    doc.blocks.append(ParsedBlock(text=para, page_no=pno))
        if not doc.blocks:
            raise DocumentParseError("PDF 未提取到文本，可能为扫描件（需 OCR）")
        return doc
