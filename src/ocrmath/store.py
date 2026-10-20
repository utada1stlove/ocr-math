"""题库与知识点词表的读写。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

import yaml

from .schema import Issue, Problem


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
        if path is None or not path.exists():
            return cls()
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
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or []
        if isinstance(raw, dict) and "problems" in raw:
            raw = raw["problems"]
        if not isinstance(raw, list):
            raise ValueError(f"{path} 不是题目列表，拒绝追加")
    else:
        raw = []
    raw.append(problem.to_mapping())
    text = yaml.safe_dump(raw, allow_unicode=True, sort_keys=False, width=1000)
    path.write_text(text, encoding="utf-8")
