"""解析与切分测试。"""
from __future__ import annotations

import pytest

from app.ingestion.chunker import EngineeringChunker
from app.ingestion.parsers import TextParser
from app.utils.text import (extract_clause_no, extract_keywords,
                            extract_standard_code, is_mandatory_clause,
                            tokenize)
from tests.conftest import SAMPLE_TEXT


def test_tokenize_engineering_terms():
    toks = tokenize("C30混凝土坍落度和保护层厚度的验收标准")
    assert "混凝土" in toks
    assert "坍落度" in toks
    assert "保护层" in toks or "保护层厚度" in toks


def test_extract_standard_code():
    assert extract_standard_code("依据 GB 50204-2015 规定") == "GB 50204-2015".replace(" -", "-")
    assert extract_standard_code("按JGJ130-2011执行").startswith("JGJ")
    assert extract_standard_code("没有编号的普通文本") == ""


def test_extract_clause_no():
    assert extract_clause_no("7.4.2 采用覆盖浇水养护的混凝土") == "7.4.2"
    assert extract_clause_no("普通段落内容") == ""


def test_mandatory_detection():
    assert is_mandatory_clause("严禁在基坑边坡顶部堆载超过设计值")
    assert is_mandatory_clause("脚手架搭设人员必须持证上岗")
    assert not is_mandatory_clause("本条为一般性说明内容，供参考使用")


def test_keywords():
    kws = extract_keywords(SAMPLE_TEXT, 10)
    assert len(kws) > 0
    assert any("混凝土" in k or "养护" in k for k in kws)


def test_text_parser_headings():
    doc = TextParser.parse_text(SAMPLE_TEXT)
    assert len(doc.blocks) > 3
    assert any(b.block_type == "heading" for b in doc.blocks)


def test_chunker_section_path():
    doc = TextParser.parse_text(SAMPLE_TEXT)
    chunks = EngineeringChunker(chunk_size=300, overlap=50).split(doc)
    assert len(chunks) >= 2
    assert any(c.section_path for c in chunks)
    assert all(c.char_count > 0 for c in chunks)
    # 序号连续
    assert [c.seq for c in chunks] == list(range(len(chunks)))


def test_chunker_keeps_clause_no():
    doc = TextParser.parse_text(SAMPLE_TEXT)
    chunks = EngineeringChunker(chunk_size=200, overlap=30).split(doc)
    assert any(c.clause_no.startswith("7.4") for c in chunks)


def test_chunker_table_not_split():
    md = "# 表格\n\n" + "| 项目 | 允许偏差 |\n|---|---|\n" + \
         "\n".join(f"| 项{i} | {i}mm |" for i in range(60))
    doc = TextParser.parse_text(md)
    chunks = EngineeringChunker(chunk_size=100).split(doc)
    table_chunks = [c for c in chunks if "|" in c.content]
    assert table_chunks, "表格块应被保留"
