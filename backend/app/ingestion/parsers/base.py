"""文档解析器基类与数据结构。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List


@dataclass
class ParsedBlock:
    """解析产出的原子块（段落/表格行/标题）"""
    text: str
    page_no: int = 0
    block_type: str = "paragraph"  # paragraph / heading / table / list
    heading_level: int = 0
    meta: Dict = field(default_factory=dict)


@dataclass
class ParsedDocument:
    blocks: List[ParsedBlock] = field(default_factory=list)
    meta: Dict = field(default_factory=dict)

    @property
    def full_text(self) -> str:
        return "\n".join(b.text for b in self.blocks if b.text.strip())


class BaseParser(ABC):
    suffixes: tuple[str, ...] = ()

    @abstractmethod
    def parse(self, path: Path) -> ParsedDocument: ...

    def supports(self, path: Path) -> bool:
        return path.suffix.lower() in self.suffixes
