"""题库读写的回归测试：词表缺失要报错、追加不能破坏原文件。

对应审计 AUDIT.md 问题 5（append_problem 重写 YAML）、9（--root 找不到时假装成功）。
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from support import TempProject  # noqa: E402

from ocrmath.schema import Problem  # noqa: E402
from ocrmath.store import Taxonomy, append_problem, load_problems, problem_files  # noqa: E402

COMMENTED_FILE = """\
# 高一函数专题：本文件按教学进度维护，请勿删注释
# 负责人：数学组

- id: keep-001
  statement: 已有题目。
  answer: $1$          # 行尾注释也要保住
  my_note: 教研组备注
  difficulty: 3
"""


class TaxonomyTests(unittest.TestCase):
    def test_missing_file_raises_instead_of_pretending_empty(self) -> None:
        with TempProject(taxonomy=None) as project:
            with self.assertRaises(FileNotFoundError):
                Taxonomy.load(project.path / "data" / "taxonomy.yaml")

    def test_empty_file_is_allowed(self) -> None:
        with TempProject() as project:
            path = project.write("data/taxonomy.yaml", "name: 空词表\ntags: {}\n")
            taxonomy = Taxonomy.load(path)
            self.assertEqual(taxonomy.known_tags, set())

    def test_groups_and_order(self) -> None:
        with TempProject() as project:
            taxonomy = Taxonomy.load(project.path / "data" / "taxonomy.yaml")
            self.assertIn("导数应用", taxonomy.known_tags)
            self.assertLess(taxonomy.order()["函数性质"], taxonomy.order()["等差数列"])


class AppendProblemTests(unittest.TestCase):
    def test_comments_and_unknown_fields_survive(self) -> None:
        with TempProject() as project:
            target = project.write_problems("bank.yaml", COMMENTED_FILE)
            append_problem(target, Problem(id="new-001", statement="新题目。", answer="$2$"))
            text = project.read("data/problems/bank.yaml")

            self.assertIn("# 高一函数专题：本文件按教学进度维护，请勿删注释", text)
            self.assertIn("# 负责人：数学组", text)
            self.assertIn("# 行尾注释也要保住", text)
            self.assertIn("my_note: 教研组备注", text)
            self.assertIn("new-001", text)

    def test_appended_problem_still_loads(self) -> None:
        with TempProject() as project:
            target = project.write_problems("bank.yaml", COMMENTED_FILE)
            append_problem(target, Problem(id="new-002", statement="新题目。", answer="$2$", extra={"my_note": "备注"}))
            problems, issues = load_problems([target])
            self.assertEqual([i for i in issues if i.level == "error"], [])
            self.assertEqual([p.id for p in problems], ["keep-001", "new-002"])
            self.assertEqual(problems[1].extra, {"my_note": "备注"})

    def test_new_file_is_created(self) -> None:
        with TempProject() as project:
            target = project.path / "data" / "problems" / "inbox.yaml"
            append_problem(target, Problem(id="fresh-1", statement="题目。"))
            self.assertTrue(target.exists())
            problems, _ = load_problems([target])
            self.assertEqual([p.id for p in problems], ["fresh-1"])

    def test_refuses_file_that_is_not_a_list(self) -> None:
        with TempProject() as project:
            target = project.write_problems("bad.yaml", "name: 这不是题目列表\n")
            with self.assertRaises(ValueError):
                append_problem(target, Problem(id="x-1", statement="题目。"))


class LoadProblemsTests(unittest.TestCase):
    def test_duplicate_ids_reported(self) -> None:
        with TempProject() as project:
            path = project.write_problems(
                "dup.yaml",
                "- id: dup-1\n  statement: 一。\n- id: dup-1\n  statement: 二。\n",
            )
            _, issues = load_problems([path])
            self.assertTrue(any("重复" in i.message for i in issues))

    def test_bad_yaml_reported(self) -> None:
        with TempProject() as project:
            path = project.write_problems("broken.yaml", "- id: [unclosed\n")
            problems, issues = load_problems([path])
            self.assertEqual(problems, [])
            self.assertTrue(any(i.level == "error" for i in issues))

    def test_problem_files_sorted(self) -> None:
        with TempProject() as project:
            project.write_problems("b.yaml", "- id: b-1\n  statement: 题。\n")
            project.write_problems("a.yaml", "- id: a-1\n  statement: 题。\n")
            names = [p.name for p in problem_files(project.path / "data")]
            self.assertEqual(names, ["a.yaml", "b.yaml"])


class EncodingTests(unittest.TestCase):
    """GBK/ANSI 保存的题库文件要提示「不是 UTF-8」，而不是抛 codec 原文。"""

    def test_gbk_file_reports_encoding_not_codec_error(self) -> None:
        with TempProject() as project:
            target = project.path / "data" / "problems" / "gbk.yaml"
            target.write_bytes(
                "- id: gbk-001\n  statement: 中文题干\n  answer: $1$\n".encode("gbk")
            )
            problems, issues = load_problems([target])
            self.assertEqual(problems, [])
            errors = [i for i in issues if i.level == "error"]
            self.assertEqual(len(errors), 1)
            self.assertEqual(errors[0].problem_id, "gbk.yaml")
            self.assertIn("UTF-8", errors[0].message)
            self.assertNotIn("codec", errors[0].message)


if __name__ == "__main__":
    unittest.main()
