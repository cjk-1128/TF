"""解析器注册与分发。"""
from __future__ import annotations

from pathlib import Path
from typing import List

from app.core.exceptions import DocumentParseError
from app.ingestion.parsers.base import BaseParser, ParsedBlock, ParsedDocument
from app.ingestion.parsers.docx_parser import DocxParser
from app.ingestion.parsers.excel_parser import ExcelParser
from app.ingestion.parsers.pdf_parser import PDFParser
from app.ingestion.parsers.text_parser import TextParser

_PARSERS: List[BaseParser] = [PDFParser(), DocxParser(), ExcelParser(), TextParser()]


def get_parser(path: Path) -> BaseParser:
    for p in _PARSERS:
        if p.supports(path):
            return p
    raise DocumentParseError(f"不支持的文件类型: {path.suffix}")


def parse_file(path: Path) -> ParsedDocument:
    return get_parser(path).parse(path)


__all__ = ["ParsedBlock", "ParsedDocument", "BaseParser",
           "get_parser", "parse_file", "TextParser"]
