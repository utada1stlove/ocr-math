"""OCR 引擎注册表。新增引擎只需在这里登记。"""

from __future__ import annotations

from .base import OCRResult
from .cloud import CloudEngine
from .local import LocalEngine

ENGINES: dict[str, type] = {
    LocalEngine.name: LocalEngine,
    CloudEngine.name: CloudEngine,
}


def get_engine(name: str):
    try:
        engine_cls = ENGINES[name]
    except KeyError:
        raise KeyError(f"未知引擎「{name}」，可选：{', '.join(sorted(ENGINES))}") from None
    return engine_cls()


__all__ = ["ENGINES", "OCRResult", "get_engine"]
