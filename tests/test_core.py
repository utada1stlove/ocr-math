"""核心逻辑的快速回归测试（不需要 LaTeX 编译）。

运行： python -m unittest discover -s tests -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ocrmath.render import RenderConfig, render  # noqa: E402
from ocrmath.schema import Problem  # noqa: E402
from ocrmath.select import SelectOptions, group_problems, select_problems  # noqa: E402
from ocrmath.store import Taxonomy, load_problems, problem_files  # noqa: E402


class SchemaTests(unittest.TestCase):
    def test_chinese_aliases(self) -> None:
        problem = Problem.from_mapping(
            {
                "编号": "demo-1",
                "题干": "已知 $x>0$，求最小值。",
                "答案": "$4$",
                "知识点": "基本不等式, 函数性质",
                "难度": 4,
                "留白": 25,
            }
        )
        self.assertEqual(problem.id, "demo-1")
        self.assertEqual(problem.tags, ["基本不等式", "函数性质"])
        self.assertEqual(problem.workspace_mm, 25.0)

    def test_invalid_id_and_empty_statement(self) -> None:
        issues = Problem(id="bad id!", statement="").validate()
        errors = [i for i in issues if i.level == "error"]
        self.assertGreaterEqual(len(errors), 2)

    def test_latex_health_checks(self) -> None:
        issues = Problem(id="x-1", statement="求 $x+1 的值，占 50% 比例。").validate()
        warnings = " ".join(i.message for i in issues if i.level == "warning")
        self.assertIn("$", warnings)
        self.assertIn("%", warnings)

    def test_detail_fields_and_aliases(self) -> None:
        problem = Problem.from_mapping(
            {
                "编号": "demo-2",
                "题干": "已知 $a>0$，求最小值。",
                "答案": "$4$",
                "分步": ["第一步。", "第二步。"],
                "易错点": ["漏端点。"],
                "思路提示": "先分离参数。",
                "讲评建议": "强调取等条件。",
            }
        )
        self.assertEqual(problem.steps, ["第一步。", "第二步。"])
        self.assertEqual(problem.pitfalls, ["漏端点。"])
        self.assertEqual(problem.hint, "先分离参数。")
        self.assertEqual(problem.teaching, "强调取等条件。")
        self.assertEqual([i for i in problem.validate() if i.level == "error"], [])


class StoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.taxonomy = Taxonomy.load(ROOT / "data" / "taxonomy.yaml")
        self.problems, issues = load_problems(problem_files(ROOT / "data"))
        self.issues = issues

    def test_bank_loads_without_errors(self) -> None:
        self.assertEqual([i for i in self.issues if i.level == "error"], [])
        # 题库会持续增长，这里只保证「读得到、非空」，不锁具体题数
        self.assertGreater(len(self.problems), 0)
        self.assertEqual(len({p.id for p in self.problems}), len(self.problems))

    def test_all_problems_valid(self) -> None:
        issues = []
        for problem in self.problems:
            issues.extend(problem.validate(self.taxonomy.known_tags))
        self.assertEqual([i for i in issues if i.level == "error"], [])

    def test_tag_filter_and_difficulty(self) -> None:
        chosen = select_problems(
            self.problems,
            SelectOptions(tags=["导数应用", "概率"], difficulty_min=2, difficulty_max=2),
        )
        self.assertEqual({p.id for p in chosen}, {"fx-001", "prob-001"})

    def test_ids_keep_order(self) -> None:
        chosen = select_problems(self.problems, SelectOptions(ids=["seq-001", "fx-001"]))
        self.assertEqual([p.id for p in chosen], ["seq-001", "fx-001"])

    def test_grouping_follows_taxonomy_order(self) -> None:
        groups = group_problems(self.problems, "tag", self.taxonomy.order())
        titles = [title for title, _ in groups]
        self.assertIn("函数性质", titles)
        self.assertEqual(len(self.problems), sum(len(items) for _, items in groups))


class RenderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.taxonomy = Taxonomy.load(ROOT / "data" / "taxonomy.yaml")
        self.problems, _ = load_problems(problem_files(ROOT / "data"))

    def test_sheet_tex_contains_key_pieces(self) -> None:
        cfg = RenderConfig(title="测试卷", answers="end", group_by="tag")
        tex = render(self.problems, self.taxonomy, cfg, ROOT / "templates")
        self.assertIn(r"\documentclass", tex)
        self.assertIn("参考答案与解析", tex)
        self.assertIn("测试卷", tex)
        self.assertGreaterEqual(tex.count(r"\needspace"), len(self.problems))

    def test_card_has_no_answer_when_disabled(self) -> None:
        cfg = RenderConfig(template="card", answers="none")
        card = render(self.problems[:1], self.taxonomy, cfg, ROOT / "templates")
        self.assertNotIn("答案：", card)

    def test_inline_answers_show_up(self) -> None:
        cfg = RenderConfig(template="card", answers="inline")
        card = render(self.problems[:1], self.taxonomy, cfg, ROOT / "templates")
        self.assertIn("答案：", card)

    def test_student_has_no_answers_or_workspace(self) -> None:
        cfg = RenderConfig(template="student", group_by="tag")
        tex = render(self.problems, self.taxonomy, cfg, ROOT / "templates")
        self.assertIn(r"\documentclass", tex)
        self.assertNotIn("【答案】", tex)
        self.assertNotIn("【解析】", tex)
        self.assertNotIn("草稿", tex)

    def test_answers_use_steps_and_pitfalls(self) -> None:
        cfg = RenderConfig(template="answers")
        tex = render(self.problems, self.taxonomy, cfg, ROOT / "templates")
        self.assertIn("【答案】", tex)
        self.assertIn("【易错点】", tex)
        self.assertIn("求导：", tex)
        self.assertNotIn("【讲评】", tex)

    def test_teacher_has_hint_and_teaching(self) -> None:
        cfg = RenderConfig(template="teacher")
        tex = render(self.problems, self.taxonomy, cfg, ROOT / "templates")
        self.assertIn("【思路】", tex)
        self.assertIn("【讲评】", tex)
        self.assertIn("教师版", tex)


class FigureRenderTests(unittest.TestCase):
    """插图渲染：模板要出 \\includegraphics，且路径只用文件名（图已拷进构建目录）。"""

    def setUp(self) -> None:
        self.taxonomy = Taxonomy.load(ROOT / "data" / "taxonomy.yaml")
        self.problem = Problem(
            id="fig-t-1",
            statement="如图，求 $BC$。",
            answer="$5$",
            figures=["figs/triangle.png"],
            figure_width=0.5,
            tags=["解三角形"],
        )

    def _render(self, template: str) -> str:
        cfg = RenderConfig(template=template)
        return render([self.problem], self.taxonomy, cfg, ROOT / "templates")

    def test_preamble_loads_graphicx(self) -> None:
        self.assertIn(r"\usepackage{graphicx}", self._render("student"))

    def test_statement_templates_include_the_figure(self) -> None:
        for template in ("sheet", "card", "student", "teacher"):
            tex = self._render(template)
            self.assertIn(r"\includegraphics", tex, f"{template} 应渲染插图")
            # 只写文件名：绝对路径在 Windows 上会被 LaTeX 的 \\ 规则坑到
            self.assertIn("triangle.png", tex)
            self.assertNotIn("figs/triangle.png", tex)

    def test_width_ratio_is_applied(self) -> None:
        self.assertIn("0.50", self._render("student"))

    def test_problem_without_figures_has_no_includegraphics(self) -> None:
        plain = Problem(id="fig-t-2", statement="无图题。", answer="$1$")
        tex = render([plain], self.taxonomy, RenderConfig(template="student"), ROOT / "templates")
        self.assertNotIn(r"\includegraphics", tex)

    def test_multiple_figures_render_in_order(self) -> None:
        multi = Problem(
            id="fig-t-3",
            statement="两幅图。",
            figures=["figs/a.png", "figs/b.png"],
        )
        tex = render([multi], self.taxonomy, RenderConfig(template="student"), ROOT / "templates")
        self.assertEqual(tex.count(r"\includegraphics"), 2)
        self.assertLess(tex.index("a.png"), tex.index("b.png"))

    def test_figure_height_feeds_needspace_estimate(self) -> None:
        # 有图的题估算高度必须更大，否则 \\needspace 会低估导致图被切到下一页
        from ocrmath.render import _question_height_mm

        without = _question_height_mm("同一句题干。", [])
        with_fig = _question_height_mm("同一句题干。", [], ["a.png"], 0.6)
        self.assertGreater(with_fig, without)


if __name__ == "__main__":
    unittest.main()
