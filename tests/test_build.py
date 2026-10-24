"""build.py 的回归测试：latexmk 缺失、缺图、超时、报错解析、页数提取。

这些用例不调用真实 LaTeX：``shutil.which`` 和 ``subprocess.run`` 都被替换掉，
所以能在没装 TeX 的机器和 CI 上跑。
"""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from support import TempProject  # noqa: E402

from ocrmath.build import BuildResult, _parse_errors, _tail, build  # noqa: E402


class FakeProc:
    """subprocess.run 的替身：只提供 build 用到的两个字段。"""

    def __init__(self, returncode: int = 0, stdout: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout


def fake_run(pages: int = 7, returncode: int = 0, log: str | None = None, make_pdf: bool = True):
    """造一个 subprocess.run 替身，按 latexmk 的样子在 build 目录里落文件。"""

    def runner(command, cwd=None, **kwargs):
        directory = Path(cwd)
        text = log if log is not None else f"Output written on main.pdf ({pages} pages)."
        (directory / "main.log").write_text(text, encoding="utf-8")
        if make_pdf:
            (directory / "main.pdf").write_bytes(b"%PDF-1.4 fake")
        return FakeProc(returncode=returncode, stdout=text)

    return runner


class BuildTests(unittest.TestCase):
    def test_missing_latexmk_is_reported(self) -> None:
        with TempProject() as project, mock.patch("ocrmath.build.shutil.which", return_value=None):
            result = build("x", project.path / "out.pdf", project.path / "build")
            self.assertFalse(result.ok)
            self.assertIn("找不到 latexmk", result.errors[0])

    def test_success_copies_pdf_and_reads_pages(self) -> None:
        with TempProject() as project:
            out = project.path / "dist" / "sheet.pdf"
            with mock.patch("ocrmath.build.shutil.which", return_value="latexmk"), mock.patch(
                "ocrmath.build.subprocess.run", side_effect=fake_run(pages=7)
            ):
                result = build("hello", out, project.path / "build")
            self.assertTrue(result.ok, result.errors)
            self.assertEqual(result.pages, 7)
            self.assertTrue(out.exists())
            self.assertEqual(result.pdf, out)
            self.assertEqual((project.path / "build" / "main.tex").read_text(encoding="utf-8"), "hello")

    def test_compile_failure_parses_file_line_errors(self) -> None:
        log = (
            "main.tex:12: Undefined control sequence.\n"
            "l.12 \foo\n"
            "! Emergency stop.\n"
        )
        with TempProject() as project:
            with mock.patch("ocrmath.build.shutil.which", return_value="latexmk"), mock.patch(
                "ocrmath.build.subprocess.run",
                side_effect=fake_run(returncode=1, log=log, make_pdf=False),
            ):
                result = build("x", project.path / "out.pdf", project.path / "build")
            self.assertFalse(result.ok)
            self.assertTrue(any("main.tex:12" in e for e in result.errors), result.errors)
            self.assertTrue(any("Emergency stop" in e for e in result.errors), result.errors)
            self.assertTrue(result.log_tail)

    def test_unparsable_failure_mentions_exit_code(self) -> None:
        with TempProject() as project:
            with mock.patch("ocrmath.build.shutil.which", return_value="latexmk"), mock.patch(
                "ocrmath.build.subprocess.run",
                side_effect=fake_run(returncode=3, log="something odd", make_pdf=False),
            ):
                result = build("x", project.path / "out.pdf", project.path / "build")
            self.assertFalse(result.ok)
            self.assertIn("退出码 3", result.errors[0])

    def test_success_without_pdf_is_a_failure(self) -> None:
        with TempProject() as project:
            with mock.patch("ocrmath.build.shutil.which", return_value="latexmk"), mock.patch(
                "ocrmath.build.subprocess.run", side_effect=fake_run(make_pdf=False)
            ):
                result = build("x", project.path / "out.pdf", project.path / "build")
            self.assertFalse(result.ok)
            self.assertIn("未生成 main.pdf", result.errors[0])

    def test_missing_figure_fails_before_running_latexmk(self) -> None:
        with TempProject() as project:
            ghost = project.path / "nope.png"
            with mock.patch("ocrmath.build.shutil.which", return_value="latexmk"), mock.patch(
                "ocrmath.build.subprocess.run"
            ) as run:
                result = build("x", project.path / "out.pdf", project.path / "build", figures=[ghost])
            self.assertFalse(result.ok)
            self.assertIn("找不到插图", result.errors[0])
            run.assert_not_called()

    def test_timeout_is_reported(self) -> None:
        with TempProject() as project:
            with mock.patch("ocrmath.build.shutil.which", return_value="latexmk"), mock.patch(
                "ocrmath.build.subprocess.run", side_effect=subprocess.TimeoutExpired("latexmk", 5)
            ):
                result = build("x", project.path / "out.pdf", project.path / "build", timeout=5)
            self.assertFalse(result.ok)
            self.assertIn("编译超时", result.errors[0])

    def test_figure_is_copied_into_build_dir(self) -> None:
        with TempProject() as project:
            figure = project.path / "fig" / "diagram.png"
            figure.parent.mkdir(parents=True, exist_ok=True)
            figure.write_bytes(b"png")
            with mock.patch("ocrmath.build.shutil.which", return_value="latexmk"), mock.patch(
                "ocrmath.build.subprocess.run", side_effect=fake_run()
            ):
                result = build("x", project.path / "out.pdf", project.path / "build", figures=[figure])
            self.assertTrue(result.ok, result.errors)
            self.assertTrue((project.path / "build" / "diagram.png").exists())


class ParseErrorsTests(unittest.TestCase):
    def test_empty_log_has_no_errors(self) -> None:
        self.assertEqual(_parse_errors(""), [])

    def test_bang_style_error_collects_context(self) -> None:
        log = (
            "! LaTeX Error: File `missing.sty' not found.\n"
            "\n"
            "Type X to quit or <RETURN> to proceed,\n"
        )
        errors = _parse_errors(log)
        self.assertEqual(len(errors), 1)
        self.assertIn("missing.sty", errors[0])
        self.assertIn("Type X to quit", errors[0])

    def test_at_most_five_errors(self) -> None:
        log = "".join(f"main.tex:{n}: bad line\n" for n in range(1, 12))
        self.assertEqual(len(_parse_errors(log)), 5)


class TailTests(unittest.TestCase):
    def test_keeps_last_lines_only(self) -> None:
        text = "".join(f"line{n}\n" for n in range(100))
        tail = _tail(text, lines=10)
        self.assertNotIn("line88", tail)
        self.assertIn("line99", tail)
        self.assertEqual(len(tail.splitlines()), 10)

    def test_short_text_is_returned_whole(self) -> None:
        self.assertEqual(_tail("a\nb", lines=60), "a\nb")


class BuildResultTests(unittest.TestCase):
    def test_defaults_are_independent_lists(self) -> None:
        first, second = BuildResult(ok=True), BuildResult(ok=False)
        first.errors.append("x")
        self.assertEqual(second.errors, [])


if __name__ == "__main__":
    unittest.main()
