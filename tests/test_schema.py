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


class ListItemSeparatorTests(unittest.TestCase):
    """列表写法里的全角逗号：手写 YAML 时 ``tags: [A，B]`` 是常见笔误。"""

    def test_full_width_comma_inside_list_splits_tags(self) -> None:
        # 以前列表元素不切分，整个 "函数性质，导数应用" 变成一个 tag，
        # validate 报「知识点不在词表中」，看起来像是词表漏了条目。
        problem = Problem.from_mapping(
            {"id": "s-3", "statement": "题目。", "tags": ["函数性质，导数应用"]}
        )
        self.assertEqual(problem.tags, ["函数性质", "导数应用"])

    def test_full_width_comma_inside_list_splits_pitfalls(self) -> None:
        problem = Problem.from_mapping(
            {"id": "s-4", "statement": "题目。", "pitfalls": ["漏端点，忘记验证"]}
        )
        self.assertEqual(problem.pitfalls, ["漏端点", "忘记验证"])

    def test_list_items_keep_their_order(self) -> None:
        problem = Problem.from_mapping(
            {"id": "s-5", "statement": "题目。", "tags": ["A，B", "C"]}
        )
        self.assertEqual(problem.tags, ["A", "B", "C"])

    def test_choices_still_never_split(self) -> None:
        # 反向保险：split_items 只给 tags/pitfalls 开，choices 必须保持原样
        problem = Problem.from_mapping(
            {"id": "s-6", "statement": "选择。", "choices": ["$1，2$", "$3，4$"]}
        )
        self.assertEqual(problem.choices, ["$1，2$", "$3，4$"])


class LaTeXSpecialCharTests(unittest.TestCase):
    """未转义的 & # _ 一编译就炸，但审计时只查了 % 和 $。"""

    def _messages(self, statement: str) -> str:
        return " ".join(_warnings(Problem(id="c-1", statement=statement)))

    def test_unescaped_ampersand_is_reported(self) -> None:
        self.assertIn("&", self._messages("已知 a & b 两数"))

    def test_unescaped_hash_is_reported(self) -> None:
        self.assertIn("#", self._messages("第 #3 题的答案是 5"))

    def test_bare_underscore_outside_math_is_reported(self) -> None:
        self.assertIn("_", self._messages("设 a_1 为首项"))

    def test_escaped_specials_are_clean(self) -> None:
        self.assertEqual(self._messages("设 $a_1$ 为首项，占 95\\% 比例，且 b\\_2 与 c\\#3"), "")

    def test_ampersand_in_tabular_is_clean(self) -> None:
        # 表格里的 & 是列分隔符，不能误报
        tabular = "\\begin{tabular}{|c|c|} \\hline a & b \\\\ \\hline \\end{tabular}"
        self.assertEqual(self._messages(tabular), "")

    def test_ampersand_in_matrix_is_clean(self) -> None:
        matrix = "$\\begin{pmatrix} 1 & 2 \\\\ 3 & 4 \\end{pmatrix}$"
        self.assertEqual(self._messages(matrix), "")

    def test_underscore_in_cases_is_clean(self) -> None:
        cases = "$\\begin{cases} x_1, & x\\ge 0 \\\\ x_2, & x<0\\end{cases}$"
        self.assertEqual(self._messages(cases), "")

    def test_underscore_inside_inline_math_is_clean(self) -> None:
        self.assertEqual(self._messages("设 $a_1+a_2=5$"), "")

    def test_display_math_brackets_are_tracked(self) -> None:
        # \\[ ... \\] 里也是数学模式，_ 合法
        self.assertEqual(self._messages("\\[ a_1 + b_2 \\]"), "")


class FigureFieldTests(unittest.TestCase):
    """插图字段：figures 是相对 data/ 的路径列表，figure_width 是占正文宽的比例。"""

    def test_figures_default_to_empty(self) -> None:
        problem = Problem(id="f-1", statement="题目。")
        self.assertEqual(problem.figures, [])
        self.assertEqual(problem.figure_width, 0.6)

    def test_figures_accept_string_and_list(self) -> None:
        single = Problem.from_mapping({"id": "f-2", "statement": "题目。", "figures": "figs/a.png"})
        self.assertEqual(single.figures, ["figs/a.png"])
        many = Problem.from_mapping(
            {"id": "f-3", "statement": "题目。", "figures": ["figs/a.png", "figs/b.png"]}
        )
        self.assertEqual(many.figures, ["figs/a.png", "figs/b.png"])

    def test_chinese_aliases(self) -> None:
        problem = Problem.from_mapping(
            {"编号": "f-4", "题干": "题目。", "插图": ["figs/c.png"], "图宽": 0.4}
        )
        self.assertEqual(problem.figures, ["figs/c.png"])
        self.assertEqual(problem.figure_width, 0.4)

    def test_bad_width_value_falls_back_to_default(self) -> None:
        # 非数字回落默认值，范围问题交给 validate（这样 YAML 手误不会直接崩）
        problem = Problem.from_mapping({"id": "f-5", "statement": "题目。", "figure_width": "半宽"})
        self.assertEqual(problem.figure_width, 0.6)

    def test_out_of_range_width_is_an_error(self) -> None:
        for bad in (0.05, 1.5, -1):
            problem = Problem(id="f-6", statement="题目。", figure_width=bad)
            errors = [i for i in problem.validate() if i.level == "error"]
            self.assertTrue(
                any("figure_width" in i.field_name for i in errors),
                f"figure_width={bad} 应报错，实际：{[str(i) for i in errors]}",
            )

    def test_empty_figure_path_is_an_error(self) -> None:
        problem = Problem(id="f-7", statement="题目。", figures=["  "])
        errors = [i for i in problem.validate() if i.level == "error"]
        self.assertTrue(any("figures" in i.field_name for i in errors))

    def test_figures_survive_round_trip(self) -> None:
        original = Problem(
            id="f-8", statement="题目。", figures=["figs/a.png"], figure_width=0.45
        )
        restored = Problem.from_mapping(original.to_mapping())
        self.assertEqual(restored.figures, ["figs/a.png"])
        self.assertEqual(restored.figure_width, 0.45)

    def test_default_width_is_omitted_from_mapping(self) -> None:
        # 默认值不写回 YAML，避免每道题都多一行噪音
        mapping = Problem(id="f-9", statement="题目。").to_mapping()
        self.assertNotIn("figure_width", mapping)
        self.assertNotIn("figures", mapping)


if __name__ == "__main__":
    unittest.main()
