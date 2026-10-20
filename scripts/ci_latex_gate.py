"""CI 慢速档：真实编译五套模板，并机检 LaTeX 日志。

这一档需要 TeX Live / MiKTeX（xelatex + ctex + latexmk），所以只放在
workflow_dispatch / nightly 里跑，不挡每次 push。

检查项（对应 AUDIT.md 第九节的验收口径）：
  1. 五套模板 build 全部 exit 0
  2. main.log 里 Overfull \\hbox = 0
  3. main.log 里 Missing character = 0
  4. main.log 里没有 TeX 错误（行首 "!"）

用法：python scripts/ci_latex_gate.py [--root PATH] [--allow-overfull]
退出码：0 全绿；1 有不通过项。
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

TEMPLATES = ("sheet", "card", "student", "answers", "teacher")

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
    args = parser.parse_args(argv)

    repo = Path(__file__).resolve().parents[1]
    root = Path(args.root).resolve() if args.root else repo

    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(filter(None, [str(repo / "src"), env.get("PYTHONPATH", "")]))

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
            env=env,
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

    print()
    if failures:
        print(f"{len(failures)} 项不通过：", file=sys.stderr)
        for line in failures:
            print(f"  - {line}", file=sys.stderr)
        return 1

    print(f"五套模板编译通过，日志无 Overfull / Missing character / 错误。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

