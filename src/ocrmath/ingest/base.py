"""OCR 引擎接口：所有引擎都返回同一套 ``Problem`` 结构，下游排版/编译不感知来源。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable

from ..schema import Problem


@dataclass
class OCRResult:
    engine: str
    problems: list[Problem] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    raw: str = ""


@runtime_checkable
class OCREngine(Protocol):
    name: str

    @classmethod
    def available(cls) -> tuple[bool, str]:
        """返回 (是否可用, 不可用时的说明)。"""

    def recognize(self, image: Path) -> OCRResult:
        ...
