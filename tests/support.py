"""测试辅助：在仓库 `.tmp/` 下搭一个临时题库项目。

不用 ``tempfile.mkdtemp()``：Windows + DSH 沙箱下 0o700 的临时目录会触发 ACL 拒绝
（见 PLAN.md「环境与坑」），所以统一落在已被 git 忽略的 `.tmp/test-tmp/` 里。
"""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_TAXONOMY = """
name: 测试词表
tags:
  函数性质:
    - 单调性
    - 导数应用
  数列:
    - 等差数列
"""

SAMPLE_PROBLEM = """
- id: t-001
  statement: 求 $1+1$ 的值。
  answer: $2$
  tags: [函数性质]
  difficulty: 2
"""


class TempProject:
    """一个最小可用的项目根：``data/taxonomy.yaml`` + ``data/problems/``。"""

    def __init__(self, taxonomy: str | None = DEFAULT_TAXONOMY) -> None:
        self.path = ROOT / ".tmp" / "test-tmp" / uuid.uuid4().hex
        (self.path / "data" / "problems").mkdir(parents=True, exist_ok=True)
        if taxonomy is not None:
            (self.path / "data" / "taxonomy.yaml").write_text(taxonomy.strip() + "\n", encoding="utf-8")

    # ------------------------------------------------------------------ 写入
    def write(self, relative: str, text: str) -> Path:
        target = self.path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        return target

    def write_problems(self, name: str, text: str) -> Path:
        return self.write(f"data/problems/{name}", text)

    # ------------------------------------------------------------------ 读取
    def read(self, relative: str) -> str:
        return (self.path / relative).read_text(encoding="utf-8")

    def exists(self, relative: str) -> bool:
        return (self.path / relative).exists()

    # ------------------------------------------------------------- 生命周期
    def cleanup(self) -> None:
        shutil.rmtree(self.path, ignore_errors=True)

    def __enter__(self) -> "TempProject":
        return self

    def __exit__(self, *exc_info: object) -> bool:
        self.cleanup()
        return False
