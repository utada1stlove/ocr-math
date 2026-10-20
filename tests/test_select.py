"""选题逻辑的回归测试：显式 ids 不该被二次过滤、limit 不该接受非正数。

对应审计 AUDIT.md 问题 6（--limit 负数 / 反向难度区间 / --ids 被二次过滤）。
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from ocrmath.schema import Problem  # noqa: E402
from ocrmath.select import SelectOptions, select_problems  # noqa: E402


def _bank() -> list[Problem]:
    return [
        Problem(id="a-1", statement="题一。", tags=["函数性质"], difficulty=1),
        Problem(id="a-2", statement="题二。", tags=["导数应用"], difficulty=2),
        Problem(id="a-3", statement="题三。", tags=["等差数列"], difficulty=3),
        Problem(id="a-4", statement="题四。", tags=["等差数列"], difficulty=5),
    ]


class ExplicitIdsTests(unittest.TestCase):
    def test_ids_keep_requested_order(self) -> None:
        chosen = select_problems(_bank(), SelectOptions(ids=["a-3", "a-1"]))
        self.assertEqual([p.id for p in chosen], ["a-3", "a-1"])

    def test_ids_are_not_filtered_by_difficulty(self) -> None:
        # 点名要 a-1（难度 1），却给了难度区间 4-5：不该静默变成空
        chosen = select_problems(_bank(), SelectOptions(ids=["a-1"], difficulty_min=4, difficulty_max=5))
        self.assertEqual([p.id for p in chosen], ["a-1"])

    def test_ids_are_not_filtered_by_tags(self) -> None:
        chosen = select_problems(_bank(), SelectOptions(ids=["a-1"], tags=["等差数列"]))
        self.assertEqual([p.id for p in chosen], ["a-1"])

    def test_ids_are_not_shuffled_by_seed(self) -> None:
        chosen = select_problems(_bank(), SelectOptions(ids=["a-1", "a-2", "a-3"], seed=7))
        self.assertEqual([p.id for p in chosen], ["a-1", "a-2", "a-3"])

    def test_duplicate_ids_are_collapsed(self) -> None:
        chosen = select_problems(_bank(), SelectOptions(ids=["a-1", "a-1", "a-2"]))
        self.assertEqual([p.id for p in chosen], ["a-1", "a-2"])

    def test_ids_still_respect_limit(self) -> None:
        chosen = select_problems(_bank(), SelectOptions(ids=["a-1", "a-2", "a-3"], limit=2))
        self.assertEqual([p.id for p in chosen], ["a-1", "a-2"])

    def test_unknown_id_raises(self) -> None:
        with self.assertRaises(KeyError):
            select_problems(_bank(), SelectOptions(ids=["nope"]))


class LimitTests(unittest.TestCase):
    def test_zero_limit_rejected(self) -> None:
        with self.assertRaises(ValueError):
            select_problems(_bank(), SelectOptions(limit=0))

    def test_negative_limit_rejected(self) -> None:
        with self.assertRaises(ValueError):
            select_problems(_bank(), SelectOptions(limit=-1))

    def test_positive_limit_applies(self) -> None:
        chosen = select_problems(_bank(), SelectOptions(limit=2))
        self.assertEqual(len(chosen), 2)


class DifficultyRangeTests(unittest.TestCase):
    def test_reversed_range_rejected(self) -> None:
        with self.assertRaises(ValueError):
            select_problems(_bank(), SelectOptions(difficulty_min=4, difficulty_max=2))

    def test_range_still_filters(self) -> None:
        chosen = select_problems(_bank(), SelectOptions(difficulty_min=2, difficulty_max=3))
        self.assertEqual([p.id for p in chosen], ["a-2", "a-3"])


class TagTests(unittest.TestCase):
    def test_tag_any_and_all(self) -> None:
        any_tags = select_problems(_bank(), SelectOptions(tags=["函数性质", "等差数列"]))
        self.assertEqual([p.id for p in any_tags], ["a-1", "a-3", "a-4"])
        all_tags = select_problems(
            _bank(), SelectOptions(tags=["等差数列"], tag_mode="all")
        )
        self.assertEqual([p.id for p in all_tags], ["a-3", "a-4"])


if __name__ == "__main__":
    unittest.main()
