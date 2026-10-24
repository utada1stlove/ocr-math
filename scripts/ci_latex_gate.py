"""CI 慢速档：真实编译五套模板，并机检 LaTeX 日志。

这一档需要 TeX Live / MiKTeX（xelatex + ctex + latexmk），所以只放在
workflow_dispatch / nightly 里跑，不挡每次 push。

检查项（对应 AUDIT.md 第九节的验收口径）：
  1. 五套模板 build 全部 exit 0
  2. main.log 里 Overfull \\hbox = 0
  3. main.log 里 Missing character = 0
  4. main.log 里没有 TeX 错误（行首 "!"）
  5. 含图题能编过：用 tests/fixtures/figures 单独跑一轮，
     日志里既不能有「File ... not found」，也得真的读到图片

用法：python scripts/ci_latex_gate.py [--root PATH] [--allow-overfull] [--skip-figures]
退出码：0 全绿；1 有不通过项。
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

TEMPLATES = ("sheet", "card", "student", "answers", "teacher")

# 插图 fixture：一题单图、一题两图，图是 1x1 PNG，只验链路不验内容。
FIGURES_FIXTURE = Path("tests") / "fixtures" / "figures"

# main.log 里出现即算失败的模式
_FATAL_PATTERNS = (
    ("Overfull \\hbox", re.compile(r"^Overfull \\hbox", re.MULTILINE)),
    ("Missing character", re.compile(r"^Missing character:", re.MULTILINE)),
    ("TeX 错误", re.compile(r"^! ", re.MULTILINE)),
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="编译五套模板并机检 LaTeX 日志")
    parser.add_argument("--root", default=None, help="项目根目录（默认脚本上一级）")
    parser.add_argument("--allow-overfull", action="store_true", help="放过 Overfull \\hbox（仅调试用）")
    parser.add_argument("--skip-figures", action="store_true", help="跳过插图 fixture 那一轮")
    args = parser.parse_args(argv)

    repo = Path(__file__).resolve().parents[1]
    root = Path(args.root).resolve() if args.root else repo

    failures: list[str] = []
    for template in TEMPLATES:
        print(f"=== build {template}")
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "ocrmath",
                "build",
                "--root",
                str(root),
                "--template",
                template,
                "--title",
                "高一数学 周末练习",
                "--subtitle",
                "函数、三角、数列与概率",
                "--group-by",
                "tag",
            ],
            cwd=root,
            env=_env(repo),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.stdout.strip():
            print(result.stdout.rstrip())
        if result.returncode != 0:
            print(result.stderr.rstrip(), file=sys.stderr)
            failures.append(f"{template}: build 退出码 {result.returncode}")
            continue

        log_path = root / "out" / ".build" / template / "main.log"
        if not log_path.exists():
            failures.append(f"{template}: 找不到 {log_path}")
            continue
        log = log_path.read_text(encoding="utf-8", errors="replace")

        for label, pattern in _FATAL_PATTERNS:
            if label == "Overfull \\hbox" and args.allow_overfull:
                continue
            hits = pattern.findall(log)
            if hits:
                sample = [line.strip() for line in log.splitlines() if pattern.match(line)][:3]
                failures.append(f"{template}: {label} × {len(hits)}，例：{sample[0] if sample else ''}")

    if not args.skip_figures:
        failures.extend(_check_figures(repo, args.allow_overfull))

    print()
    if failures:
        print(f"{len(failures)} 项不通过：", file=sys.stderr)
        for line in failures:
            print(f"  - {line}", file=sys.stderr)
        return 1

    print("五套模板编译通过，日志无 Overfull / Missing character / 错误。")
    if not args.skip_figures:
        print("插图 fixture 编译通过，日志确认读到了图片。")
    return 0


def _check_figures(repo: Path, allow_overfull: bool) -> list[str]:
    """把插图 fixture 拷到临时项目里编一轮，确认含图题真的能出 PDF。

    单独跑而不是塞进主题库：主题库要维持「9 题 / 2-3-4 页」这条基线，
    多两题就会让页数基线失效；而且缺图/多图这类边界本来就不该混进真题库。
    """
    fixture = repo / FIGURES_FIXTURE
    if not fixture.is_dir():
        return [f"找不到插图 fixture：{fixture}"]

    failures: list[str] = []
    with tempfile.TemporaryDirectory(prefix="figcheck-") as tmp:
        project = Path(tmp)
        shutil.copytree(fixture, project, dirs_exist_ok=True)
        shutil.copytree(repo / "templates", project / "templates", dirs_exist_ok=True)

        for template in TEMPLATES:
            print(f"=== build {template}（插图 fixture）")
            command = [
                sys.executable, "-m", "ocrmath", "build",
                "--root", str(project),
                "--template", template,
                "--title", "插图 fixture",
            ]
            # answers 默认不重复题干，因此也不显示图；开 --echo 才能真正验到那条分支
            if template == "answers":
                command.append("--echo")
            result = subprocess.run(
                command,
                cwd=project,
                env=_env(repo),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            if result.stdout.strip():
                print(result.stdout.rstrip())
            if result.returncode != 0:
                print(result.stderr.rstrip(), file=sys.stderr)
                failures.append(f"插图 {template}: build 退出码 {result.returncode}")
                continue

            log_path = project / "out" / ".build" / template / "main.log"
            if not log_path.exists():
                failures.append(f"插图 {template}: 找不到 {log_path}")
                continue
            log = log_path.read_text(encoding="utf-8", errors="replace")

            # 图必须真的被读进去，否则「编译通过」可能只是 includegraphics 没生效
            if "demo.png" not in log:
                failures.append(f"插图 {template}: 日志里没有 demo.png，图可能没被读入")
            if re.search(r"File .*demo\.png. not found", log):
                failures.append(f"插图 {template}: LaTeX 报图找不到")

            for label, pattern in _FATAL_PATTERNS:
                if label == "Overfull \\hbox" and allow_overfull:
                    continue
                hits = pattern.findall(log)
                if hits:
                    sample = [line.strip() for line in log.splitlines() if pattern.match(line)][:3]
                    failures.append(
                        f"插图 {template}: {label} × {len(hits)}，例：{sample[0] if sample else ''}"
                    )
    return failures


def _abs_pythonpath(value: str) -> str:
    """把 PYTHONPATH 里每一项都转成绝对路径。

    子进程的 cwd 不一定和调用方相同（插图 fixture 在临时目录里跑），相对项一离开
    原目录就指向不存在的路径，症状是子进程报 No module named 'yaml'——看起来像
    代码坏了，其实是路径失效。去重并保留顺序，避免 PYTHONPATH 越滚越长。
    """
    entries: list[str] = []
    for part in value.split(os.pathsep):
        part = part.strip()
        if not part:
            continue
        resolved = str(Path(part).resolve())
        if resolved not in entries:
            entries.append(resolved)
    return os.pathsep.join(entries)


def _env(repo: Path) -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = _abs_pythonpath(
        os.pathsep.join(filter(None, [str(repo / "src"), env.get("PYTHONPATH", "")]))
    )
    env.setdefault("PYTHONIOENCODING", "utf-8")
    return env


if __name__ == "__main__":
    raise SystemExit(main())

