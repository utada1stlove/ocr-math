"""本地引擎：pix2tex（LaTeX-OCR），CPU 可跑，离线可用。

它识别的是**一段公式**；整页题目（中文题干 + 多个公式 + 选项）需要先把区域裁开，
这部分能力后续接入版面分析后再补。
"""

from __future__ import annotations

import importlib.util
from datetime import datetime
from pathlib import Path

from ..schema import Problem
from .base import OCRResult


class LocalEngine:
    name = "local"

    @classmethod
    def available(cls) -> tuple[bool, str]:
        if importlib.util.find_spec("pix2tex") is None:
            return False, "未安装 pix2tex。安装：pip install pix2tex（首次运行自动下载约 70MB 权重）"
        try:
            import torch  # noqa: F401
        except Exception as exc:  # pragma: no cover - 取决于环境
            return False, f"torch 不可用：{exc}"
        return True, "pix2tex 已安装（CPU 推理）"

    def __init__(self) -> None:
        self._model = None

    def _load(self):
        if self._model is None:
            from pix2tex.cli import LatexOCR

            self._model = LatexOCR()
        return self._model

    def recognize(self, image: Path) -> OCRResult:
        available, reason = self.available()
        if not available:
            raise RuntimeError(reason)

        from PIL import Image

        model = self._load()
        with Image.open(image) as img:
            latex = (model(img.convert("RGB")) or "").strip()

        warnings = [
            "本地引擎只识别公式片段：中文题干、选项、答案需要人工补齐。",
            "请核对数字、上下标和分式——公式识别最常错的就是这些位置。",
        ]
        if not latex:
            return OCRResult(engine=self.name, problems=[], warnings=["没有识别出公式"], raw="")

        problem = Problem(
            id=f"ocr-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
            statement=latex,
            difficulty=3,
        )
        return OCRResult(engine=self.name, problems=[problem], warnings=warnings, raw=latex)
