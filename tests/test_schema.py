"""数据模型的回归测试：LaTeX 体检覆盖面、分隔符、未知字段保留。

对应审计 AUDIT.md 问题 1（answer 不体检）、3（全角逗号）、5（未知字段丢失）。
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from ocrmath.schema import Problem  # noqa: E402


def _warnings(problem: Problem) -> list[str]:
    return [i.message for i in problem.validate() if i.level == "warning"]


class AnswerHealthCheckTests(unittest.TestCase):
    """answer 也要做 LaTeX 体检——它是试卷上最短、最易手抖的字段。"""

    def test_unescaped_percent_in_answer_is_reported(self) -> None:
        problem = Problem(id="p-1", statement="求及格率。", answer="及格率 30% 的学生")
        self.assertTrue(
            any("answer" in i.field_name and "%" in i.message for i in problem.validate()),
            f"answer 里的 % 应被报出，实际：{[str(i) for i in problem.validate()]}",
        )

    def test_odd_dollar_in_answer_is_reported(self) -> None:
        problem = Problem(id="p-2", statement="求范围。", answer="$a \\le 1")
        self.assertTrue(
            any("answer" in i.field_name and "$" in i.message for i in problem.validate()),
            f"answer 里的奇数 $ 应被报出，实际：{[str(i) for i in problem.validate()]}",
        )

    def test_healthy_answer_has_no_warnings(self) -> None:
        problem = Problem(id="p-3", statement="求值。", answer="$a \\le 1$，占比 30\\%")
        self.assertEqual(_warnings(problem), [])

    def test_empty_answer_is_allowed(self) -> None:
        problem = Problem(id="p-4", statement="求值。", answer="")
        self.assertEqual(_warnings(problem), [])


class SeparatorTests(unittest.TestCase):
    """中文输入法打出来的是全角逗号。"""

    def test_full_width_comma_splits_tags(self) -> None:
        problem = Problem.from_mapping({"id": "s-1", "statement": "题目。", "tags": "函数性质，导数应用"})
        self.assertEqual(problem.tags, ["函数性质", "导数应用"])

    def test_full_width_comma_does_not_split_choices(self) -> None:
        # 选项内部本身就可能带全角逗号（"A. 1，2"），切了会把一个选项拆成两个
        problem = Problem.from_mapping(
            {"id": "s-2", "statement": "选择。", "choices": ["$1，2$", "$3，4$"]}
        )
        self.assertEqual(problem.choices, ["$1，2$", "$3，4$"])


class ExtraFieldTests(unittest.TestCase):
    """未知字段不能被静默丢掉（教研备注、来源链接之类）。"""

    def test_unknown_field_survives_round_trip(self) -> None:
        raw = {
            "id": "x-1",
            "statement": "题目。",
            "my_note": "教研组备注",
            "ocr_from": "IMG_0042.png",
        }
        problem = Problem.from_mapping(raw)
        self.assertEqual(problem.extra, {"my_note": "教研组备注", "ocr_from": "IMG_0042.png"})
        mapping = problem.to_mapping()
        self.assertEqual(mapping["my_note"], "教研组备注")
        self.assertEqual(mapping["ocr_from"], "IMG_0042.png")

    def test_known_aliases_are_not_extra(self) -> None:
        problem = Problem.from_mapping({"编号": "x-2", "题干": "题目。", "答案": "$1$", "难度": 4})
        self.assertEqual(problem.extra, {})

    def test_extra_survives_second_round_trip(self) -> None:
        first = Problem.from_mapping({"id": "x-3", "statement": "题目。", "my_note": "备注"})
        second = Problem.from_mapping(first.to_mapping())
        self.assertEqual(second.extra, {"my_note": "备注"})


if __name__ == "__main__":
    unittest.main()
