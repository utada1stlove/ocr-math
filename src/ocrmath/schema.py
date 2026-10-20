"""题目数据模型与校验规则。

一道题在题库里是一个 ``Problem``。``statement`` 等字段保存的是 **LaTeX 片段**
（正文 + 行内公式），不含 ``\\documentclass`` 等整份文档结构——版式由模板负责。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")

# 允许中文键名，方便手工/OCR 直接产出可读的 YAML
_FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "id": ("id", "编号"),
    "statement": ("statement", "题干", "stem", "body"),
    "choices": ("choices", "选项"),
    "answer": ("answer", "答案"),
    "solution": ("solution", "解析", "详解"),
    "tags": ("tags", "知识点", "标签"),
    "difficulty": ("difficulty", "难度"),
    "workspace_mm": ("workspace_mm", "留白"),
    "source": ("source", "来源"),
    "title": ("title", "标题"),
    # 详解与教师用字段
    "steps": ("steps", "分步", "步骤", "解析步骤"),
    "pitfalls": ("pitfalls", "易错点", "易错"),
    "hint": ("hint", "提示", "思路提示"),
    "teaching": ("teaching", "教学提示", "教学", "讲评建议"),
}


@dataclass
class Issue:
    """校验结果。level 取 ``error`` 或 ``warning``。"""

    level: str
    message: str
    problem_id: str = ""
    field_name: str = ""

    def __str__(self) -> str:
        tag = "错误" if self.level == "error" else "警告"
        loc = ".".join(part for part in (self.problem_id, self.field_name) if part)
        return f"[{tag}] {loc + ': ' if loc else ''}{self.message}"


def _as_list(value: Any, sep: str = r"[;,；\n]") -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        parts = re.split(sep, value)
        return [p.strip() for p in parts if p.strip()]
    if isinstance(value, (list, tuple)):
        return [str(v).strip() for v in value if str(v).strip()]
    raise TypeError(f"无法解析为列表: {value!r}")


def _pick(data: dict[str, Any], field_name: str) -> Any:
    for key in _FIELD_ALIASES[field_name]:
        if key in data:
            return data[key]
    return None


@dataclass
class Problem:
    id: str
    statement: str
    choices: list[str] = field(default_factory=list)
    answer: str = ""
    solution: str = ""
    tags: list[str] = field(default_factory=list)
    difficulty: int = 3
    workspace_mm: float | None = None
    source: str = ""
    title: str = ""
    # 详解 / 教师用：steps 是分步推导，pitfalls 是易错点，hint 是思路提示，teaching 是讲评建议
    steps: list[str] = field(default_factory=list)
    pitfalls: list[str] = field(default_factory=list)
    hint: str = ""
    teaching: str = ""

    # ---------------------------------------------------------------- 构造
    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "Problem":
        if not isinstance(data, dict):
            raise TypeError(f"题目必须是映射，收到 {type(data).__name__}")

        raw_workspace = _pick(data, "workspace_mm")
        workspace = None
        if raw_workspace not in (None, ""):
            workspace = float(raw_workspace)

        raw_difficulty = _pick(data, "difficulty")
        difficulty = 3 if raw_difficulty in (None, "") else int(raw_difficulty)

        return cls(
            id=str(_pick(data, "id") or "").strip(),
            statement=str(_pick(data, "statement") or "").strip(),
            choices=_as_list(_pick(data, "choices")),
            answer=str(_pick(data, "answer") or "").strip(),
            solution=str(_pick(data, "solution") or "").strip(),
            tags=_as_list(_pick(data, "tags")),
            difficulty=difficulty,
            workspace_mm=workspace,
            source=str(_pick(data, "source") or "").strip(),
            title=str(_pick(data, "title") or "").strip(),
            steps=_as_list(_pick(data, "steps"), sep=r"\n"),
            pitfalls=_as_list(_pick(data, "pitfalls")),
            hint=str(_pick(data, "hint") or "").strip(),
            teaching=str(_pick(data, "teaching") or "").strip(),
        )

    def to_mapping(self) -> dict[str, Any]:
        out: dict[str, Any] = {"id": self.id, "statement": self.statement}
        if self.choices:
            out["choices"] = list(self.choices)
        if self.answer:
            out["answer"] = self.answer
        if self.solution:
            out["solution"] = self.solution
        if self.tags:
            out["tags"] = list(self.tags)
        out["difficulty"] = self.difficulty
        if self.workspace_mm is not None:
            out["workspace_mm"] = self.workspace_mm
        if self.source:
            out["source"] = self.source
        if self.title:
            out["title"] = self.title
        if self.steps:
            out["steps"] = list(self.steps)
        if self.pitfalls:
            out["pitfalls"] = list(self.pitfalls)
        if self.hint:
            out["hint"] = self.hint
        if self.teaching:
            out["teaching"] = self.teaching
        return out

    # ---------------------------------------------------------------- 校验
    def validate(self, known_tags: set[str] | None = None) -> list[Issue]:
        issues: list[Issue] = []
        add = lambda level, field_name, message: issues.append(  # noqa: E731
            Issue(level, message, self.id, field_name)
        )

        if not self.id:
            add("error", "id", "缺少 id（题库内唯一即可，如 der-001）")
        elif not _ID_RE.match(self.id):
            add("error", "id", "id 只能包含字母、数字、点、下划线、连字符")

        if not self.statement.strip():
            add("error", "statement", "题干为空")
        if self.choices and len(self.choices) < 2:
            add("error", "choices", "选择题至少需要 2 个选项")
        if not 1 <= self.difficulty <= 5:
            add("error", "difficulty", f"难度必须是 1–5，当前 {self.difficulty}")
        if self.workspace_mm is not None and not 0 <= self.workspace_mm <= 250:
            add("error", "workspace_mm", "留白高度应在 0–250mm 之间")

        if known_tags is not None:
            for tag in self.tags:
                if tag not in known_tags:
                    add("warning", "tags", f"知识点「{tag}」不在 data/taxonomy.yaml 中")

        if self.statement:
            issues.extend(_latex_issues(self.statement, self.id))
        for idx, choice in enumerate(self.choices, 1):
            issues.extend(_latex_issues(choice, self.id, f"choices[{idx}]"))
        for idx, step in enumerate(self.steps, 1):
            if not step.strip():
                add("error", f"steps[{idx}]", "分步解析中有空步骤")
                continue
            issues.extend(_latex_issues(step, self.id, f"steps[{idx}]"))
        for idx, pitfall in enumerate(self.pitfalls, 1):
            if not pitfall.strip():
                add("error", f"pitfalls[{idx}]", "易错点为空")
                continue
            issues.extend(_latex_issues(pitfall, self.id, f"pitfalls[{idx}]"))
        if self.solution:
            issues.extend(_latex_issues(self.solution, self.id, "solution"))
        if self.hint:
            issues.extend(_latex_issues(self.hint, self.id, "hint"))
        if self.teaching:
            issues.extend(_latex_issues(self.teaching, self.id, "teaching"))
        return issues


def _latex_issues(text: str, problem_id: str, field_name: str = "statement") -> list[Issue]:
    """便宜的 LaTeX 片段体检：括号/公式符号是否配对、百分号是否转义。"""
    issues: list[Issue] = []
    depth = 0
    dollars = 0
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "\\":
            i += 2  # 跳过被转义的字符
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth < 0:
                break
        elif ch == "$":
            dollars += 1
        elif ch == "%":
            issues.append(
                Issue("warning", "正文中的 % 未转义，会被 LaTeX 当成注释（写成 \\%）", problem_id, field_name)
            )
        i += 1
    if depth != 0:
        issues.append(Issue("warning", "花括号 {} 不配对，编译可能失败", problem_id, field_name))
    if dollars % 2:
        issues.append(Issue("warning", "行内公式 $ 数量为奇数，编译可能失败", problem_id, field_name))
    return issues
