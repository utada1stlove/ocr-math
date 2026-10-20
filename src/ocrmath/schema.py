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
    "figures": ("figures", "figure", "images", "图", "插图", "图片"),
    "figure_width": ("figure_width", "图宽"),
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


# 知识点、易错点这类「自由文本列表」允许用全角逗号分隔——中文输入法下 `，` 是默认逗号。
# 选项（choices）不在此列：`"A. 1，2"` 里的全角逗号属于选项内容，切开会把一个选项拆成两个。
_LIST_SEP = r"[,;，；\n]"

# 所有能被识别的键名（含中文别名），用于区分「未知字段」
_KNOWN_KEYS: frozenset[str] = frozenset(key for aliases in _FIELD_ALIASES.values() for key in aliases)


def _as_list(value: Any, sep: str = r"[;,；\n]", *, split_items: bool = False) -> list[str]:
    """把 YAML 值规整成字符串列表。

    ``split_items`` 为真时，列表里的每个元素也会再按 ``sep`` 切分。
    这是为 ``tags`` / ``pitfalls`` 准备的：手写 YAML 时 ``tags: [函数性质，导数应用]``
    里的全角逗号是笔误而非内容，不切就会得到「知识点「函数性质，导数应用」不在词表中」
    这种莫名其妙的警告。``choices`` 绝不能开这个开关——``A. 1，2`` 里的全角逗号
    属于选项内容，切开会把一个选项拆成两个。
    """
    if value is None:
        return []
    if isinstance(value, str):
        parts = re.split(sep, value)
        return [p.strip() for p in parts if p.strip()]
    if isinstance(value, (list, tuple)):
        items: list[str] = []
        for raw in value:
            text = str(raw).strip()
            if not text:
                continue
            if split_items:
                items.extend(part.strip() for part in re.split(sep, text) if part.strip())
            else:
                items.append(text)
        return items
    raise TypeError(f"无法解析为列表: {value!r}")


_FIGURE_WIDTH_MIN = 0.1
_FIGURE_WIDTH_MAX = 1.0
_FIGURE_WIDTH_DEFAULT = 0.6


def _figure_width(value: Any) -> float:
    """插图宽度比例。留空或非法值一律回落默认值，范围在 validate 里查。"""
    if value in (None, ""):
        return _FIGURE_WIDTH_DEFAULT
    try:
        return float(value)
    except (TypeError, ValueError):
        return _FIGURE_WIDTH_DEFAULT

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
    # 插图：相对 <root>/data/ 的路径列表（如 figs/cube.png）。渲染时会拷进构建目录，
    # 这样 main.tex 里只有相对路径，不依赖本机的绝对路径写法。
    figures: list[str] = field(default_factory=list)
    # 插图占正文宽度的比例（0.1–1.0）
    figure_width: float = 0.6
    # 详解 / 教师用：steps 是分步推导，pitfalls 是易错点，hint 是思路提示，teaching 是讲评建议
    steps: list[str] = field(default_factory=list)
    pitfalls: list[str] = field(default_factory=list)
    hint: str = ""
    teaching: str = ""
    # 本模型不认识的键原样保存（教研备注、OCR 来源文件名……），
    # 这样 `add` 追加写回时不会把人手写的字段静默丢掉。
    extra: dict[str, Any] = field(default_factory=dict)

    # ---------------------------------------------------------------- 构造
    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "Problem":
        if not isinstance(data, dict):
            raise TypeError(f"题目必须是映射，收到 {type(data).__name__}")

        extra = {key: value for key, value in data.items() if key not in _KNOWN_KEYS}

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
            tags=_as_list(_pick(data, "tags"), sep=_LIST_SEP, split_items=True),
            difficulty=difficulty,
            workspace_mm=workspace,
            source=str(_pick(data, "source") or "").strip(),
            title=str(_pick(data, "title") or "").strip(),
            figures=_as_list(_pick(data, "figures")),
            figure_width=_figure_width(_pick(data, "figure_width")),
            steps=_as_list(_pick(data, "steps"), sep=r"\n"),
            pitfalls=_as_list(_pick(data, "pitfalls"), sep=_LIST_SEP, split_items=True),
            hint=str(_pick(data, "hint") or "").strip(),
            teaching=str(_pick(data, "teaching") or "").strip(),
            extra=extra,
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
        if self.figures:
            out["figures"] = list(self.figures)
            if self.figure_width != 0.6:
                out["figure_width"] = self.figure_width
        if self.steps:
            out["steps"] = list(self.steps)
        if self.pitfalls:
            out["pitfalls"] = list(self.pitfalls)
        if self.hint:
            out["hint"] = self.hint
        if self.teaching:
            out["teaching"] = self.teaching
        for key, value in self.extra.items():
            out.setdefault(key, value)
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
        if not _FIGURE_WIDTH_MIN <= self.figure_width <= _FIGURE_WIDTH_MAX:
            add(
                "error",
                "figure_width",
                f"插图宽度比例应在 {_FIGURE_WIDTH_MIN}–{_FIGURE_WIDTH_MAX} 之间，当前 {self.figure_width}",
            )
        for idx, figure in enumerate(self.figures, 1):
            if not figure.strip():
                add("error", f"figures[{idx}]", "插图路径为空")

        if known_tags is not None:
            for tag in self.tags:
                if tag not in known_tags:
                    add("warning", "tags", f"知识点「{tag}」不在 data/taxonomy.yaml 中")

        if self.statement:
            issues.extend(_latex_issues(self.statement, self.id))
        if self.answer:
            issues.extend(_latex_issues(self.answer, self.id, "answer"))
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


# 环境跟踪：判断 & 与 _ 在当前上下文里是否合法。
# 表格/对齐环境里的 & 是列分隔符；数学环境里的 _ 是下标。
_MATH_ENVS: frozenset[str] = frozenset(
    {
        "equation", "equation*", "align", "align*", "aligned", "gather", "gather*",
        "cases", "array", "matrix", "pmatrix", "bmatrix", "vmatrix", "Vmatrix",
        "smallmatrix", "split", "multline", "multline*", "eqnarray", "eqnarray*",
        "math", "displaymath",
    }
)
_ALIGN_ENVS: frozenset[str] = _MATH_ENVS | frozenset(
    {"tabular", "tabular*", "tabularx", "tabulary", "longtable"}
)
_BEGIN_ENV_RE = re.compile(r"\\begin\{([^}]*)\}")
_END_ENV_RE = re.compile(r"\\end\{([^}]*)\}")


def _in_math_env(env_stack: list[str]) -> bool:
    return any(name in _MATH_ENVS for name in env_stack)


def _in_alignment_env(env_stack: list[str]) -> bool:
    return any(name in _ALIGN_ENVS for name in env_stack)

def _latex_issues(text: str, problem_id: str, field_name: str = "statement") -> list[Issue]:
    r"""便宜的 LaTeX 片段体检。

    只报「一编译就炸 / 悄悄吃掉半行字」的硬伤，不求完备：

    * ``{}`` 不配对
    * ``$`` 数量为奇数
    * 未转义的 ``%``（会被当注释，静默吞掉后半行）
    * 未转义的 ``&``（表格外报 Misplaced alignment tab character）
    * 未转义的 ``#``（报 macro parameter character）
    * 数学模式外的 ``_``（报 Missing $ inserted）

    扫描时跳过被反斜杠转义的字符，并跟踪 ``$...$``、``\(...\)``、``\[...\]`` 与
    ``\\begin{...}...\\end{...}``。表格/矩阵环境里的 ``&`` 是列分隔符，
    数学环境里的 ``_`` 是下标，这两类都不告警。
    """
    issues: list[Issue] = []
    depth = 0
    dollars = 0
    in_math = False
    env_stack: list[str] = []
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "\\":
            begin = _BEGIN_ENV_RE.match(text, i)
            if begin:
                env_stack.append(begin.group(1).strip())
                i = begin.end()
                continue
            end = _END_ENV_RE.match(text, i)
            if end:
                name = end.group(1).strip()
                if name in env_stack:
                    env_stack.remove(name)
                i = end.end()
                continue
            pair = text[i : i + 2]
            if pair in ("\\(", "\\["):
                in_math = True
            elif pair in ("\\)", "\\]"):
                in_math = False
            i += 2
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth < 0:
                depth = 0
        elif ch == "$":
            dollars += 1
            in_math = not in_math
        elif ch == "%":
            issues.append(
                Issue("warning", r"正文中的 % 未转义，会被 LaTeX 当成注释（写成 \%）", problem_id, field_name)
            )
        elif ch == "&" and not in_math and not _in_alignment_env(env_stack):
            issues.append(
                Issue(
                    "warning",
                    r"正文中的 & 未转义（表格外会被当成对齐符；写成 \&）",
                    problem_id,
                    field_name,
                )
            )
        elif ch == "#":
            issues.append(
                Issue("warning", r"正文中的 # 未转义（写成 \#）", problem_id, field_name)
            )
        elif ch == "_" and not in_math and not _in_math_env(env_stack):
            issues.append(
                Issue(
                    "warning",
                    r"数学模式外的 _ 未转义（下标要写进 $...$，或转义成 \_）",
                    problem_id,
                    field_name,
                )
            )
        i += 1
    if depth != 0:
        issues.append(Issue("warning", "花括号 {} 不配对，编译可能失败", problem_id, field_name))
    if dollars % 2:
        issues.append(Issue("warning", "行内公式 $ 数量为奇数，编译可能失败", problem_id, field_name))
    return issues
