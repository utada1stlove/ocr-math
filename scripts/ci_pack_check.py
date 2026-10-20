"""CI 慢速档：跑一次 pack --strict，核对页数与 manifest。

pack 会真的编译三份 PDF，所以这一档和 ci_latex_gate.py 一样只在
workflow_dispatch / nightly 里跑。它守的是「三份文档的页数没有漂移」——
页数是版面回归最灵敏的信号：审计修复前后 student/answers/teacher 一直是
2/3/4 页，一旦数字变了，说明模板或渲染逻辑动到了版面。

用法：python scripts/ci_pack_check.py [--root PATH] [--out DIR]
退出码：0 全绿；1 有失败。
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

# 题库不变时的期望页数。改题库或改版面后请同步更新，别把它当摆设
EXPECTED_PAGES = {"student": 2, "answers": 3, "teacher": 4}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="pack --strict + 页数核对")
    parser.add_argument("--root", default=None, help="项目根目录（默认脚本上一级）")
    parser.add_argument("--out", default=None, help="输出目录（默认临时目录，不污染 out/）")
    args = parser.parse_args(argv)

    repo = Path(__file__).resolve().parents[1]
    root = Path(args.root).resolve() if args.root else repo
    out_dir = Path(args.out).resolve() if args.out else Path(tempfile.mkdtemp(prefix="pack-check-"))

    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(filter(None, [str(repo / "src"), env.get("PYTHONPATH", "")]))

    command = [
        sys.executable, "-m", "ocrmath", "pack",
        "--root", str(root),
        "--out", str(out_dir),
        "--name", "verify",
        "--title", "高一数学 周末练习",
        "--subtitle", "函数、三角、数列与概率",
        "--group-by", "tag",
        "--strict",
    ]
    print("$ " + " ".join(command))
    result = subprocess.run(
        command, cwd=root, env=env,
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if result.stdout.strip():
        print(result.stdout.rstrip())
    if result.stderr.strip():
        print(result.stderr.rstrip(), file=sys.stderr)
    if result.returncode != 0:
        print(f"pack --strict 失败（退出码 {result.returncode}）。", file=sys.stderr)
        return 1

    manifest_path = out_dir / "manifest.json"
    if not manifest_path.exists():
        print(f"找不到 {manifest_path}", file=sys.stderr)
        return 1
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    failures: list[str] = []
    if manifest.get("failed"):
        failures.append(f"manifest.failed 非空：{manifest['failed']}")
    if len(manifest.get("problems", [])) != 9:
        failures.append(f"题目数不是 9，而是 {len(manifest.get('problems', []))}")

    pages = {doc["kind"]: doc["pages"] for doc in manifest.get("documents", [])}
    for kind, expected in EXPECTED_PAGES.items():
        actual = pages.get(kind)
        if actual is None:
            failures.append(f"缺少 {kind} 文档")
        elif actual != expected:
            failures.append(f"{kind} 页数 {actual}，期望 {expected}（版面可能漂了）")

    if failures:
        print(f"\n{len(failures)} 项不通过：", file=sys.stderr)
        for line in failures:
            print(f"  - {line}", file=sys.stderr)
        return 1

    summary = "、".join(f"{k} {v} 页" for k, v in EXPECTED_PAGES.items())
    print(f"\npack --strict 通过：{summary}。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
