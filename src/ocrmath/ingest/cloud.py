"""云端引擎占位：接口已定，接入时只需实现 recognize()。

设计意向：调用任意 OpenAI 兼容的多模态接口，把图片和 JSON Schema 一起发过去，
要求模型直接返回题库结构（statement/choices/answer/tags），再走同一套校验。
需要的环境变量：OCRMATH_OCR_BASE_URL、OCRMATH_OCR_API_KEY、OCRMATH_OCR_MODEL。
"""

from __future__ import annotations

import os
from pathlib import Path

from .base import OCRResult


class CloudEngine:
    name = "cloud"

    @classmethod
    def available(cls) -> tuple[bool, str]:
        missing = [
            key
            for key in ("OCRMATH_OCR_BASE_URL", "OCRMATH_OCR_API_KEY", "OCRMATH_OCR_MODEL")
            if not os.environ.get(key)
        ]
        if missing:
            return False, f"缺少环境变量：{', '.join(missing)}"
        return True, "云端接口已配置"

    def recognize(self, image: Path) -> OCRResult:
        available, reason = self.available()
        if not available:
            raise RuntimeError(reason)
        raise NotImplementedError(
            "云端适配器尚未实现：需要确定服务商后，按其视觉接口补上请求与重试逻辑。"
        )
