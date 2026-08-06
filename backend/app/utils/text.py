"""文本工具：中英混合分词、清洗、摘要、关键词、规范编号识别。"""
from __future__ import annotations

import hashlib
import re
from typing import List

try:
    import jieba
    jieba.setLogLevel(60)
    _HAS_JIEBA = True
except Exception:  # noqa: BLE001
    _HAS_JIEBA = False

# 土木工程常用术语，加入自定义词典可显著提升分词质量
ENGINEERING_TERMS = [
    "混凝土", "钢筋", "预应力", "模板", "脚手架", "深基坑", "基坑支护", "地下连续墙",
    "灌注桩", "预制桩", "承台", "筏板基础", "独立基础", "剪力墙", "框架结构", "钢结构",
    "焊缝", "高强螺栓", "防水卷材", "防水涂料", "止水带", "后浇带", "施工缝", "变形缝",
    "养护", "拆模", "试块", "抗压强度", "坍落度", "配合比", "水灰比", "保护层厚度",
    "沉降观测", "监测预警", "安全专项方案", "危大工程", "验收标准", "强制性条文",
    "隐蔽工程", "旁站", "见证取样", "质量通病", "蜂窝麻面", "裂缝", "露筋", "空鼓",
    "渗漏", "回填土", "压实度", "地基承载力", "标准贯入试验", "静载试验",
    "盾构", "隧道衬砌", "锚杆", "喷射混凝土", "路基", "沥青面层", "桥梁支座",
]
if _HAS_JIEBA:
    for _t in ENGINEERING_TERMS:
        jieba.add_word(_t, freq=2000)

_TOKEN_RE = re.compile(r"[\u4e00-\u9fa5]+|[a-zA-Z][a-zA-Z\-]*|\d+(?:\.\d+)*")
_STOPWORDS = {
    "的", "了", "和", "是", "在", "有", "与", "及", "或", "对", "为", "上", "下", "中",
    "我", "你", "他", "它", "这", "那", "什么", "怎么", "如何", "请问", "一下", "可以",
    "需要", "应该", "以及", "等等", "一个", "进行", "通过", "由于", "关于", "the", "a",
    "an", "of", "to", "is", "are", "in", "on", "for", "and", "or",
}

# 规范编号：GB 50204-2015 / JGJ 130-2011 / DB11/T 1234-2020 / CJJ 1-2008
# 注意：不能用 \b 前缀——中文属于 \w，"按JGJ130-2011" 中"按"与"J"之间没有词边界
STANDARD_CODE_RE = re.compile(
    r"(?<![A-Za-z0-9])"
    r"((?:GB/T|GBT|GB|JGJ|JG|JTG|JTS|CJJ|CECS|DL|SL|TB|YB|DB\d{2}(?:/T)?|Q/[A-Z0-9]+)"
    r"\s*/?\s*T?\s*\d{1,5}(?:\.\d+)?\s*[-—]\s*\d{4})"
    r"(?![0-9])",
    re.IGNORECASE,
)
# 条文号：5.2.1 / 第5.2.1条
CLAUSE_RE = re.compile(r"(?:第)?(\d{1,2}(?:\.\d{1,3}){1,3})\s*(?:条)?")


def tokenize(text: str) -> List[str]:
    """中英混合分词，过滤停用词与单字噪声。"""
    if not text:
        return []
    if _HAS_JIEBA:
        raw = [w.strip() for w in jieba.lcut(text) if w.strip()]
    else:
        raw = _TOKEN_RE.findall(text)
    out = []
    for w in raw:
        wl = w.lower()
        if wl in _STOPWORDS:
            continue
        if len(w) == 1 and not ("\u4e00" <= w <= "\u9fa5"):
            continue
        if not _TOKEN_RE.match(w):
            continue
        out.append(wl)
    return out


def clean_text(text: str) -> str:
    if not text:
        return ""
    text = text.replace("\u3000", " ").replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    # 去掉常见页眉页脚残留
    text = re.sub(r"^\s*[-—]{0,2}\s*\d{1,4}\s*[-—]{0,2}\s*$", "", text, flags=re.M)
    return text.strip()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def extract_standard_code(text: str) -> str:
    m = STANDARD_CODE_RE.search(text or "")
    if not m:
        return ""
    return re.sub(r"\s+", " ", m.group(1)).upper().replace(" -", "-").replace("- ", "-")


def extract_clause_no(text: str) -> str:
    head = (text or "")[:60]
    m = CLAUSE_RE.match(head.strip())
    return m.group(1) if m else ""


def extract_keywords(text: str, top_k: int = 12) -> List[str]:
    """TF 排序 + 工程术语优先。"""
    toks = tokenize(text)
    if not toks:
        return []
    freq: dict[str, int] = {}
    for t in toks:
        if len(t) < 2:
            continue
        freq[t] = freq.get(t, 0) + 1
    term_set = {t.lower() for t in ENGINEERING_TERMS}
    ranked = sorted(freq.items(),
                    key=lambda kv: (kv[0] in term_set, kv[1], len(kv[0])), reverse=True)
    return [k for k, _ in ranked[:top_k]]


def make_summary(text: str, max_len: int = 200) -> str:
    t = clean_text(text)
    if len(t) <= max_len:
        return t
    sents = re.split(r"(?<=[。！？!?\n])", t)
    buf = ""
    for s in sents:
        if len(buf) + len(s) > max_len:
            break
        buf += s
    return (buf or t[:max_len]).strip() + "…"


def is_mandatory_clause(text: str) -> bool:
    """强制性条文识别（黑体条文常含 必须/严禁/不得/应）"""
    head = (text or "")[:150]
    return any(k in head for k in ("必须", "严禁", "不得", "禁止"))


def truncate(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit] + "…"
