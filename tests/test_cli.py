"""CLI 层的回归测试：参数校验、--skip 取值、add 的「先全查再写」。

对应审计 AUDIT.md 问题 3（全角逗号）、6（选题参数）、7（--skip 不校验）、
8（不支持的参数静默无效）、9（--root 找不到目录却当空题库）。
这些用例只跑纯 Python 路径，不调用 LaTeX。
"""

from __future__ import annotations

import argparse
import contextlib
import io
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from ocrmath import __version__, cli, render  # noqa: E402
from support import TempProject  # noqa: E402


def _run(argv: list[str]) -> tuple[int, str, str]:
    """跑一次 cli.main，返回 (exit, stdout, stderr)。"""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main(argv)
    return code, out.getvalue(), err.getvalue()


class SplitTests(unittest.TestCase):
    def test_full_width_comma_is_a_separator(self) -> None:
        # 中文输入法打出的「，」不该让 --tags 变成一个不存在的知识点
        self.assertEqual(cli._split("函数性质，导数应用"), ["函数性质", "导数应用"])

    def test_mixed_separators_and_spaces(self) -> None:
        self.assertEqual(cli._split(" a, b，c；d "), ["a", "b", "c", "d"])

    def test_empty_is_empty(self) -> None:
        self.assertEqual(cli._split(""), [])
        self.assertEqual(cli._split(None), [])


class DifficultyTests(unittest.TestCase):
    def test_single_value(self) -> None:
        self.assertEqual(cli._difficulty("3"), (3, 3))

    def test_range(self) -> None:
        self.assertEqual(cli._difficulty("2-4"), (2, 4))

    def test_full_width_dash(self) -> None:
        # 中文输入法会打出全角连字符
        self.assertEqual(cli._difficulty("2－4"), (2, 4))
        self.assertEqual(cli._difficulty("2—4"), (2, 4))

    def test_reversed_range_is_rejected(self) -> None:
        # 以前 4-2 会静默选出空集，看起来像「题库里没有这个难度的题」
        with self.assertRaises(argparse.ArgumentTypeError):
            cli._difficulty("4-2")

    def test_out_of_range_is_rejected(self) -> None:
        with self.assertRaises(argparse.ArgumentTypeError):
            cli._difficulty("0-3")
        with self.assertRaises(argparse.ArgumentTypeError):
            cli._difficulty("1-9")

    def test_garbage_is_rejected(self) -> None:
        with self.assertRaises(argparse.ArgumentTypeError):
            cli._difficulty("abc")


class PositiveIntTests(unittest.TestCase):
    def test_positive(self) -> None:
        self.assertEqual(cli._positive_int("3"), 3)

    def test_zero_and_negative_rejected(self) -> None:
        for raw in ("0", "-1"):
            with self.assertRaises(argparse.ArgumentTypeError):
                cli._positive_int(raw)


class RootResolutionTests(unittest.TestCase):
    def test_walks_up_to_project_root(self) -> None:
        with TempProject() as project:
            nested = project.path / "src" / "deep"
            nested.mkdir(parents=True)
            self.assertEqual(cli._resolve_root(nested, explicit=False), project.path.resolve())

    def test_explicit_root_is_never_rewritten(self) -> None:
        with TempProject() as project:
            nested = project.path / "out"
            nested.mkdir()
            # 显式给了 --root 就照用，绝不悄悄换成上层目录
            self.assertEqual(cli._resolve_root(nested, explicit=True), nested.resolve())


class ListMissingRootTests(unittest.TestCase):
    def test_missing_taxonomy_errors_instead_of_empty_bank(self) -> None:
        # 没有 taxonomy.yaml 的目录：以前会打印「题库为空」并返回 0
        with TempProject(taxonomy=None) as project:
            code, out, err = _run(["list", "--root", str(project.path)])
        self.assertEqual(code, 2, out + err)
        self.assertIn("taxonomy.yaml", err)


class SkipTests(unittest.TestCase):
    def setUp(self) -> None:
        self.project = TempProject()
        self.project.write_problems("p.yaml", "problems:\n  - id: a-1\n    statement: 题。\n")

    def tearDown(self) -> None:
        self.project.cleanup()

    def test_unknown_value_is_rejected(self) -> None:
        code, _, err = _run(["pack", "--root", str(self.project.path), "--skip", "foo"])
        self.assertEqual(code, 2)
        self.assertIn("foo", err)

    def test_skipping_everything_is_an_error(self) -> None:
        # 以前只产出 manifest.json、documents: []，却 exit 0，看着像成功
        code, _, err = _run(
            ["pack", "--root", str(self.project.path), "--skip", "student,answers,teacher"]
        )
        self.assertEqual(code, 2)
        self.assertIn("至少要留一份", err)


class AddTests(unittest.TestCase):
    def setUp(self) -> None:
        self.project = TempProject()

    def tearDown(self) -> None:
        self.project.cleanup()

    def test_duplicate_ids_inside_one_file_write_nothing(self) -> None:
        source = self.project.write(
            "incoming.yaml",
            "- id: d-1\n  statement: 甲。\n- id: d-1\n  statement: 乙。\n",
        )
        code, _, err = _run(["add", "--root", str(self.project.path), str(source)])
        self.assertEqual(code, 1)
        self.assertIn("d-1", err)
        # 整批拒绝：目标文件不该被创建
        self.assertFalse(self.project.exists("data/problems/inbox.yaml"))

    def test_conflict_with_existing_writes_nothing(self) -> None:
        self.project.write_problems("inbox.yaml", "- id: e-1\n  statement: 旧题。\n")
        source = self.project.write(
            "incoming.yaml",
            "- id: e-2\n  statement: 新题一。\n- id: e-1\n  statement: 新题二。\n",
        )
        code, _, err = _run(["add", "--root", str(self.project.path), str(source)])
        self.assertEqual(code, 1)
        self.assertIn("e-1", err)
        # e-2 排在冲突项之前，也不能被写进去
        self.assertNotIn("e-2", self.project.read("data/problems/inbox.yaml"))


class RenderEstimateTests(unittest.TestCase):
    def test_cjk_counts_double(self) -> None:
        # 估算按半角宽度算：一个汉字顶两个字符宽
        self.assertEqual(render._display_width("汉字"), 4)
        self.assertEqual(render._display_width("ab"), 2)

    def test_mixed_text_needs_more_lines_than_char_count_suggests(self) -> None:
        text = "已知函数" * 20  # 80 个汉字 = 160 宽度单位，至少两行
        self.assertGreaterEqual(render._line_count(text), 2)


class AddEncodingTests(unittest.TestCase):
    """add 读到 GBK 文件要报人话，别让 UnicodeDecodeError 漏到顶层。"""

    def test_gbk_source_reports_encoding_error(self) -> None:
        with TempProject() as project:
            src = project.path / "gbk-src.yaml"
            src.write_bytes("- id: gbk-002\n  statement: 中文\n  answer: $1$\n".encode("gbk"))
            code, _out, err = _run(["add", "--root", str(project.path), str(src)])
            self.assertEqual(code, 2)
            self.assertIn("UTF-8", err)
            self.assertNotIn("codec", err)


class VersionTests(unittest.TestCase):
    def test_version_flag_prints_package_version(self) -> None:
        out = io.StringIO()
        with contextlib.redirect_stdout(out), self.assertRaises(SystemExit) as caught:
            cli.main(["--version"])
        self.assertEqual(caught.exception.code, 0)
        self.assertIn(__version__, out.getvalue())


class AddDuplicateTests(unittest.TestCase):
    """一批里 id 自己撞车：整批拒写，不能写进去一半。"""

    def test_duplicate_ids_inside_batch_are_rejected(self) -> None:
        with TempProject() as project:
            src = project.path / "dup.yaml"
            src.write_text(
                """- id: dup-1
  statement: 甲题。
- id: dup-1
  statement: 乙题。
""",
                encoding="utf-8",
            )
            code, _out, err = _run(["add", "--root", str(project.path), str(src)])
            self.assertEqual(code, 1)
            self.assertIn("dup-1", err)
            self.assertFalse((project.path / "data" / "problems" / "inbox.yaml").exists())


if __name__ == "__main__":
    unittest.main()
