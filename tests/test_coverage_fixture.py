"""覆盖性题库的回归测试：用 tests/fixtures/coverage 压边界题型。

正式题库（data/problems）只有 9 道简化题，掩盖了多小问、表格、矩阵、
超长解析这些真实题型的排版风险。这份 fixture 就是专门用来撞它们的：
它必须永远能通过 validate --strict，且五套模板都能渲染出来。

fixture 里刻意保留了几种「容易踩但不该报错」的写法，改动校验规则时它们
会最先变红——这正是留着它的意义。
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ocrmath.render import RenderConfig, render  # noqa: E402
from ocrmath.schema import Problem  # noqa: E402
from ocrmath.store import Taxonomy, load_problems  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "coverage"


class CoverageFixtureTests(unittest.TestCase):
    """十道覆盖题：全部合法，且五套模板都渲染得出来。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.taxonomy = Taxonomy.load(FIXTURE / "taxonomy.yaml")
        cls.problems, cls.load_issues = load_problems([FIXTURE / "problems" / "coverage.yaml"])

    def test_fixture_has_ten_problems(self) -> None:
        self.assertEqual(len(self.problems), 10)
        self.assertEqual([i for i in self.load_issues if i.level == "error"], [])

    def test_fixture_is_strict_clean(self) -> None:
        issues = []
        for problem in self.problems:
            issues.extend(problem.validate(self.taxonomy.known_tags))
        self.assertEqual(
            [str(i) for i in issues],
            [],
            "覆盖性 fixture 必须零问题；它变红通常说明校验规则误报或漏报",
        )

    def test_every_template_renders_the_fixture(self) -> None:
        for template in ("sheet", "card", "student", "answers", "teacher"):
            with self.subTest(template=template):
                cfg = RenderConfig(template=template, title="覆盖性", group_by="tag")
                tex = render(self.problems, self.taxonomy, cfg, ROOT / "templates")
                self.assertIn(r"\begin{document}", tex)
                self.assertNotIn("{{", tex, "渲染结果不该残留 Jinja 标记")

    def test_multi_part_statement_survives(self) -> None:
        # cov-001 是多小问解答题：(1)(2)(3) 目前作为正文文本排版
        cov1 = next(p for p in self.problems if p.id == "cov-001")
        self.assertIn("（1）", cov1.statement)
        self.assertIn("（3）", cov1.statement)

    def test_tabular_ampersands_are_not_flagged(self) -> None:
        # cov-002 的题干里有 tabular，& 是列分隔符，不该报「未转义 &」
        cov2 = next(p for p in self.problems if p.id == "cov-002")
        self.assertIn("tabular", cov2.statement)
        messages = [i.message for i in cov2.validate(self.taxonomy.known_tags)]
        self.assertEqual(messages, [])

    def test_full_width_comma_tags_are_split(self) -> None:
        # cov-007 写成字符串形式 tags: 集合运算，自定义知识点
        cov7 = next(p for p in self.problems if p.id == "cov-007")
        self.assertEqual(cov7.tags, ["集合运算", "自定义知识点"])

    def test_choice_with_full_width_comma_is_kept_intact(self) -> None:
        # cov-008 的第三个选项内部有全角逗号，不能被切
        cov8 = next(p for p in self.problems if p.id == "cov-008")
        self.assertEqual(len(cov8.choices), 4)
        self.assertTrue(any("，" in c for c in cov8.choices))

    def test_escaped_specials_are_clean(self) -> None:
        # cov-005 里有 95\\% / a\\_1 / b\\#2，都是正确转义
        cov5 = next(p for p in self.problems if p.id == "cov-005")
        messages = [i.message for i in cov5.validate(self.taxonomy.known_tags)]
        self.assertEqual(messages, [])


if __name__ == "__main__":
    unittest.main()
