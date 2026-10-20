"""题库与知识点词表的读写。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

import yaml

from .schema import Issue, Problem

# 顶层 `problems:` 形式的文件里，列表项所在行的缩进
_ITEM_RE = re.compile(r"^(\s*)-\s")


@dataclass
class Taxonomy:
    name: str = "未命名词表"
    groups: dict[str, list[str]] = field(default_factory=dict)

    @property
    def known_tags(self) -> set[str]:
        known: set[str] = set()
        for group, children in self.groups.items():
            known.add(group)
            known.update(children)
        return known

    def order(self) -> dict[str, int]:
        """知识点在排版分组时的先后顺序。"""
        result: dict[str, int] = {}
        for group, children in self.groups.items():
            result.setdefault(group, len(result))
            for child in children:
                result.setdefault(child, len(result))
        return result

    @classmethod
    def load(cls, path: Path | None) -> "Taxonomy":
        """读词表。

        文件不存在就直接报错——以前返回空词表，于是 `--root` 指错目录时
        `ocrmath list` 会打印「题库为空」并返回 0，看起来像「这个题库就是空的」。
        """
        if path is None:
            raise FileNotFoundError("没有指定知识点词表路径（应为 <root>/data/taxonomy.yaml）")
        if not path.exists():
            raise FileNotFoundError(
                f"找不到知识点词表 {path}：请确认 --root 指向项目根目录"
                f"（即 data/taxonomy.yaml 所在的目录）"
            )
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(raw, dict):
            raise ValueError(f"{path} 顶层应为映射")
        return cls(name=str(raw.get("name", path.stem)), groups=_normalize_tags(raw.get("tags") or {}))


def _normalize_tags(raw: Any) -> dict[str, list[str]]:
    if isinstance(raw, list):
        return {str(item): [] for item in raw}
    if not isinstance(raw, dict):
        return {}
    groups: dict[str, list[str]] = {}
    for key, value in raw.items():
        if value is None:
            groups[str(key)] = []
        elif isinstance(value, (list, tuple)):
            groups[str(key)] = [str(v) for v in value]
        else:  # 单个子标签
            groups[str(key)] = [str(value)]
    return groups


def problem_files(data_dir: Path) -> list[Path]:
    directory = data_dir / "problems"
    if not directory.exists():
        return []
    return sorted(
        [p for p in directory.iterdir() if p.suffix in (".yaml", ".yml")],
        key=lambda p: p.name,
    )


def load_problems(paths: Iterable[Path]) -> tuple[list[Problem], list[Issue]]:
    problems: list[Problem] = []
    issues: list[Issue] = []

    for path in paths:
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            issues.append(Issue("error", f"YAML 解析失败：{exc}", problem_id=str(path.name)))
            continue

        if raw is None:
            continue
        if isinstance(raw, dict) and "problems" in raw:
            raw = raw["problems"]
        if not isinstance(raw, list):
            issues.append(Issue("error", "文件顶层应为题目列表或 {problems: [...]}", problem_id=str(path.name)))
            continue

        for index, item in enumerate(raw, 1):
            try:
                problem = Problem.from_mapping(item)
            except (TypeError, ValueError) as exc:
                issues.append(Issue("error", f"第 {index} 题字段有误：{exc}", problem_id=path.name))
                continue
            problems.append(problem)

    seen: dict[str, int] = {}
    for problem in problems:
        seen[problem.id] = seen.get(problem.id, 0) + 1
    for pid, count in seen.items():
        if count > 1:
            issues.append(Issue("error", f"id 重复出现 {count} 次", problem_id=pid))
    return problems, issues


def append_problem(path: Path, problem: Problem) -> None:
    """把一道题追加到 ``path`` 末尾。

    采用**纯文本追加**而不是「读入 -> safe_dump 整个文件」：后者会把文件里的注释
    （含行尾注释）全部抹掉，并给没写的字段补默认值。代价是只在文件末尾追加几行文本，
    其余字节原样保留。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    block = yaml.safe_dump(
        [problem.to_mapping()], allow_unicode=True, sort_keys=False, width=1000, default_flow_style=False
    )

    if not path.exists() or not path.read_text(encoding="utf-8").strip():
        path.write_text(block, encoding="utf-8")
        return

    text = path.read_text(encoding="utf-8")
    parsed = yaml.safe_load(text)
    indent = ""
    if isinstance(parsed, dict):
        if "problems" not in parsed or not isinstance(parsed["problems"], list):
            raise ValueError(f"{path} 不是题目列表，拒绝追加")
        # 顶层 `problems:` 形式：新条目要跟已有条目缩进对齐
        for line in text.splitlines():
            match = _ITEM_RE.match(line)
            if match and match.group(1):
                indent = match.group(1)
                break
    elif not isinstance(parsed, list):
        raise ValueError(f"{path} 不是题目列表，拒绝追加")

    if indent:
        block = "".join(indent + line if line.strip() else line for line in block.splitlines(keepends=True))

    if not text.endswith("\n"):
        text += "\n"
    if not text.endswith("\n\n"):
        text += "\n"
    path.write_text(text + block, encoding="utf-8")
