"""题库数据 -> LaTeX 源码。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from .schema import Problem
from .select import group_problems
from .store import Taxonomy

TEMPLATES = ("sheet", "card", "student", "answers", "teacher")
ANSWER_MODES = ("none", "end", "inline")

# 排版高度估算：只用于 \needspace 判断，宁可略大也不要让标题孤零零留在页底
_CHARS_PER_LINE = 42
_LINE_MM = 5.7


def _line_count(text: str) -> int:
    plain = text.replace("$", "")
    total = 0
    for para in plain.split("\n"):
        total += max(1, (len(para) + _CHARS_PER_LINE - 1) // _CHARS_PER_LINE)
    return total


def _question_height_mm(statement: str, choices: list[str]) -> int:
    height = 7.0 + _LINE_MM * _line_count(statement)
    if choices:
        height += 2.0 + 7.2 * len(choices)
    return int(round(height))


def _detail_height_mm(answer: str, solution: str, steps: list[str], pitfalls: list[str]) -> int:
    height = 4.0
    if answer:
        height += 9.0
    if steps:
        height += 5.0 + sum(5.7 * _line_count(step) + 1.0 for step in steps)
    elif solution:
        height += 5.0 + 5.7 * _line_count(solution)
    if pitfalls:
        height += 4.0 + sum(5.7 * _line_count(item) + 1.0 for item in pitfalls)
    return int(round(height))


@dataclass
class RenderConfig:
    template: str = "sheet"
    title: str = ""
    subtitle: str = ""
    answers: str = "none"
    gap_mm: float = 6.0
    workspace_mm: float = 40.0
    fill: bool = False
    show_tags: bool = False
    show_difficulty: bool = False
    group_by: str = "none"
    font_size: str = "11pt"
    margin_mm: float = 20.0
    seed: int | None = None
    # student：是否一题一页（默认连续排，省纸）
    one_per_page: bool = False
    # answers：是否在答案前重复题干（默认不重复，只给题号 + 答案 + 详解）
    echo_statement: bool = False

    def validate(self) -> None:
        if self.template not in TEMPLATES:
            raise ValueError(f"template 只能是 {TEMPLATES}")
        if self.answers not in ANSWER_MODES:
            raise ValueError(f"answers 只能是 {ANSWER_MODES}")
        if self.group_by not in ("none", "tag"):
            raise ValueError("group_by 只能是 none 或 tag")


def render(
    problems: list[Problem],
    taxonomy: Taxonomy,
    cfg: RenderConfig,
    templates_dir: Path,
) -> str:
    cfg.validate()
    if not problems:
        raise ValueError("没有可排版的题目")

    env = Environment(
        loader=FileSystemLoader(templates_dir),
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
        undefined=StrictUndefined,
    )
    context = _build_context(problems, taxonomy, cfg)
    return env.get_template(f"{cfg.template}.tex.j2").render(**context)


def _build_context(problems: list[Problem], taxonomy: Taxonomy, cfg: RenderConfig) -> dict[str, Any]:
    grouped = group_problems(problems, cfg.group_by, taxonomy.order())

    groups: list[dict[str, Any]] = []
    answers: list[dict[str, Any]] = []
    number = 0
    for title, items in grouped:
        rendered_items = []
        for problem in items:
            number += 1
            workspace = cfg.workspace_mm if problem.workspace_mm is None else problem.workspace_mm
            rendered_items.append(
                {
                    "number": number,
                    "statement": problem.statement,
                    "choices": problem.choices,
                    "tags": problem.tags,
                    "difficulty": problem.difficulty,
                    "workspace_mm": workspace,
                    "answer": problem.answer,
                    "solution": problem.solution,
                    "steps": problem.steps,
                    "pitfalls": problem.pitfalls,
                    "hint": problem.hint,
                    "teaching": problem.teaching,
                    "height_mm": _question_height_mm(problem.statement, problem.choices),
                    "detail_mm": _detail_height_mm(
                        problem.answer, problem.solution, problem.steps, problem.pitfalls
                    ),
                }
            )
            answers.append({"number": number, "answer": problem.answer, "solution": problem.solution})
        groups.append({"title": title, "problems": rendered_items})

    header = {
        "title": cfg.title,
        "subtitle": cfg.subtitle,
        "gap_mm": cfg.gap_mm,
        "answers": cfg.answers,
        "fill": cfg.fill,
        "show_tags": cfg.show_tags,
        "show_difficulty": cfg.show_difficulty,
        "font_size": cfg.font_size,
        "margin_mm": cfg.margin_mm,
        "total": number,
        "one_per_page": cfg.one_per_page,
        "echo_statement": cfg.echo_statement,
    }
    return {"cfg": header, "groups": groups, "answers": answers}
