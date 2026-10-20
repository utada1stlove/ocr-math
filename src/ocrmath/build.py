"""LaTeX 源码 -> PDF（xelatex via latexmk）。"""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

_TEX_ERROR = re.compile(r"^(.+?\.tex):(\d+):\s*(.+)$")
_PAGES = re.compile(r"Output written on .*?\((\d+) pages?")


@dataclass
class BuildResult:
    ok: bool
    pdf: Path | None = None
    tex: Path | None = None
    pages: int | None = None
    errors: list[str] = field(default_factory=list)
    log_tail: str = ""


def build(tex: str, out_pdf: Path, build_dir: Path, timeout: int = 300) -> BuildResult:
    latexmk = shutil.which("latexmk")
    if not latexmk:
        return BuildResult(
            ok=False,
            errors=["找不到 latexmk：请安装 TeX Live / MiKTeX，并把 bin 目录加入 PATH"],
        )

    build_dir.mkdir(parents=True, exist_ok=True)
    tex_path = build_dir / "main.tex"
    tex_path.write_text(tex, encoding="utf-8")

    command = [
        latexmk,
        "-xelatex",
        "-interaction=nonstopmode",
        "-halt-on-error",
        "-file-line-error",
        "main.tex",
    ]
    try:
        proc = subprocess.run(
            command,
            cwd=build_dir,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return BuildResult(ok=False, tex=tex_path, errors=[f"编译超时（>{timeout}s）"])

    log_path = build_dir / "main.log"
    log = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else proc.stdout
    pages_match = _PAGES.search(log)
    pages = int(pages_match.group(1)) if pages_match else None

    if proc.returncode != 0:
        errors = _parse_errors(log) or _parse_errors(proc.stdout)
        if not errors:
            errors = [f"编译失败（latexmk 退出码 {proc.returncode}），见 {log_path}"]
        return BuildResult(ok=False, tex=tex_path, errors=errors, log_tail=_tail(log))

    pdf_path = build_dir / "main.pdf"
    if not pdf_path.exists():
        return BuildResult(ok=False, tex=tex_path, errors=["编译报告成功但未生成 main.pdf"], log_tail=_tail(log))

    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(pdf_path, out_pdf)
    return BuildResult(ok=True, pdf=out_pdf, tex=tex_path, pages=pages, log_tail=_tail(log))


def _parse_errors(log: str) -> list[str]:
    lines = log.splitlines()
    errors: list[str] = []
    for index, line in enumerate(lines):
        stripped = line.strip()
        match = _TEX_ERROR.match(stripped)
        if match and not stripped.startswith("! "):
            block = [stripped] + [ln for ln in lines[index + 1 : index + 4] if ln.strip()]
            errors.append("\n".join(block))
        elif stripped.startswith("! "):
            block = [stripped] + [ln for ln in lines[index + 1 : index + 6] if ln.strip()]
            errors.append("\n".join(block))
        if len(errors) >= 5:
            break
    return errors


def _tail(text: str, lines: int = 60) -> str:
    return "\n".join(text.splitlines()[-lines:])
