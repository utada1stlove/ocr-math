"""统一入口：按档位跑对应的闸门，本地和 CI 用同一套命令。

用法：
    python scripts/gate.py fast     # 不装 TeX 也能跑：单测 + validate + 渲染冒烟
    python scripts/gate.py slow     # 需要 TeX Live：五模板编译 + 日志机检 + pack 页数
    python scripts/gate.py all      # 两档都跑

CI 的 quick.yml 调 fast，latex.yml 调 slow，这样本地复现 CI 只需要一条命令。
退出码：0 全绿；1 有失败。
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


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


def _python(args: list[str], root: Path) -> int:
    env = _env(REPO)
    command = [sys.executable, *args]
    print(f"\n$ {' '.join(command)}")
    return subprocess.run(command, cwd=root, env=env).returncode


def fast(root: Path) -> int:
    steps = [
        # 不加 -t .：tests/ 不是包（没有 __init__.py），指定 top-level 会 ImportError
        (["-m", "unittest", "discover", "-s", "tests"], "单测"),
        (["-m", "ocrmath", "validate", "--strict"], "validate --strict"),
        ([str(REPO / "scripts" / "ci_render_smoke.py"), "--root", str(root)], "渲染冒烟"),
    ]
    failed = []
    for args, label in steps:
        code = _python(args, root)
        if code != 0:
            failed.append(f"{label}（退出码 {code}）")
    return _report(failed, "快速档")


def slow(root: Path) -> int:
    steps = [
        ([str(REPO / "scripts" / "ci_latex_gate.py"), "--root", str(root)], "五模板编译 + 日志机检"),
        ([str(REPO / "scripts" / "ci_pack_check.py"), "--root", str(root)], "pack 页数核对"),
    ]
    failed = []
    for args, label in steps:
        code = _python(args, root)
        if code != 0:
            failed.append(f"{label}（退出码 {code}）")
    return _report(failed, "慢速档")


def _report(failed: list[str], tier: str) -> int:
    print()
    if failed:
        print(f"{tier}未通过：", file=sys.stderr)
        for line in failed:
            print(f"  - {line}", file=sys.stderr)
        return 1
    print(f"{tier}全部通过。")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="统一闸门入口")
    parser.add_argument("tier", choices=["fast", "slow", "all"], nargs="?", default="fast")
    parser.add_argument("--root", default=None, help="项目根目录（默认仓库根）")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve() if args.root else REPO
    if args.tier == "fast":
        return fast(root)
    if args.tier == "slow":
        return slow(root)
    code = fast(root)
    slow_code = slow(root)
    return code or slow_code


if __name__ == "__main__":
    raise SystemExit(main())
