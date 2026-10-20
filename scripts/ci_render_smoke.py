"""CI 快速档：不装 TeX 也能跑的渲染冒烟测试。

纯粹调用 ocrmath.render.render，把五套模板各渲染一遍 .tex 源码，
验证 Jinja 模板与上下文（StrictUndefined 下少一个变量就抛异常）没有回归。

为什么快速档不跑 pack：pack 会调 latexmk 编译 PDF，没有 TeX Live 必然失败，
属于慢档的职责。这个脚本覆盖「模板/上下文对不对」，编译层交给 ci_latex_gate.py。

用法：python scripts/ci_render_smoke.py [--root PATH]
退出码：0 全部通过；1 有模板渲染失败或文本异常。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

TEMPLATES = ("sheet", "card", "student", "answers", "teacher")


REPO = Path(__file__).resolve().parents[1]


def _root(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit).resolve()
    return REPO


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="渲染冒烟测试（不需要 LaTeX）")
    parser.add_argument("--root", default=None, help="项目根目录（默认脚本上一级）")
    args = parser.parse_args(argv)
    root = _root(args.root)

    # 代码永远来自本仓库；--root 只用来指定 data/ 与 templates/
    for candidate in (root / "src", REPO / "src"):
        if candidate.is_dir():
            sys.path.insert(0, str(candidate))
            break

    from ocrmath.render import RenderConfig, render
    from ocrmath.store import Taxonomy, load_problems, problem_files

    if not (root / "data" / "taxonomy.yaml").exists():
        print(f"找不到知识点词表：{root / 'data' / 'taxonomy.yaml'}", file=sys.stderr)
        return 1
    if not (root / "templates").is_dir():
        print(f"找不到模板目录：{root / 'templates'}", file=sys.stderr)
        return 1

    taxonomy = Taxonomy.load(root / "data" / "taxonomy.yaml")
    problems, issues = load_problems(problem_files(root / "data"))
    errors = [f"{i.problem_id}: {i.message}" for i in issues if i.level == "error"]
    if errors:
        print("题库存在错误：", file=sys.stderr)
        for line in errors:
            print(f"  {line}", file=sys.stderr)
        return 1
    if not problems:
        print("题库为空，渲染冒烟没有意义。", file=sys.stderr)
        return 1

    print(f"题库 {len(problems)} 题，逐套模板渲染：")
    failed = 0
    for template in TEMPLATES:
        cfg = RenderConfig(
            template=template,
            title="高一数学 周末练习",
            subtitle="函数、三角、数列与概率",
            group_by="tag",
        )
        try:
            tex = render(problems, taxonomy, cfg, root / "templates")
        except Exception as exc:
            print(f"  [失败] {template}: {type(exc).__name__}: {exc}", file=sys.stderr)
            failed += 1
            continue

        found = []
        # StrictUndefined 能挡住缺变量；这里再兜一层「模板没被求值」的低级错误
        if "{{" in tex or "{%" in tex:
            found.append("渲染结果里残留 Jinja 标记")
        if "Undefined" in tex:
            found.append("渲染结果里出现 Undefined")
        if "\\begin{document}" not in tex or "\\end{document}" not in tex:
            found.append("缺少 document 环境")
        if len(tex) < 200:
            found.append(f"输出过短（{len(tex)} 字符）")

        # answers 默认只给题号 + 答案，不重复题干（--echo 才重复）；其余模板都要有题干
        wants_statement = template != "answers" or cfg.echo_statement
        if wants_statement:
            for problem in problems:
                if problem.statement and problem.statement not in tex:
                    found.append(f"题干未出现：{problem.id}")
        # 含答案的模板必须真的把答案排进去（审计问题 1 的答案体检、问题 2 的 steps 都落在这条线上）
        if template in ("answers", "teacher"):
            for problem in problems:
                if problem.answer and problem.answer not in tex:
                    found.append(f"答案未出现：{problem.id}")

        if found:
            print(f"  [失败] {template}: " + "；".join(found), file=sys.stderr)
            failed += 1
        else:
            print(f"  [通过] {template}: {len(tex)} 字符")

    if failed:
        print(f"\n{failed}/{len(TEMPLATES)} 套模板渲染失败。", file=sys.stderr)
        return 1
    print(f"\n{len(TEMPLATES)} 套模板全部渲染通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
