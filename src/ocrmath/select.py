"""按条件从题库中选题。"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from .schema import Problem


@dataclass
class SelectOptions:
    ids: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    tag_mode: str = "any"  # any | all
    difficulty_min: int = 1
    difficulty_max: int = 5
    limit: int | None = None
    seed: int | None = None


def select_problems(problems: list[Problem], options: SelectOptions) -> list[Problem]:
    result = list(problems)

    if options.ids:
        wanted = [pid.strip() for pid in options.ids if pid.strip()]
        by_id = {p.id: p for p in result}
        missing = [pid for pid in wanted if pid not in by_id]
        if missing:
            raise KeyError(f"题库中找不到这些 id：{', '.join(missing)}")
        result = [by_id[pid] for pid in wanted]

    if options.tags:
        tags = [t.strip() for t in options.tags if t.strip()]
        if options.tag_mode == "all":
            result = [p for p in result if all(t in p.tags for t in tags)]
        else:
            result = [p for p in result if any(t in p.tags for t in tags)]

    result = [p for p in result if options.difficulty_min <= p.difficulty <= options.difficulty_max]

    if options.seed is not None:
        random.Random(options.seed).shuffle(result)

    if options.limit is not None:
        result = result[: options.limit]

    return result


def group_problems(
    problems: list[Problem],
    group_by: str,
    taxonomy_order: dict[str, int] | None = None,
) -> list[tuple[str | None, list[Problem]]]:
    """分章节。返回 (章节标题, 题目列表)，标题为 None 表示不分组。"""
    if group_by != "tag":
        return [(None, problems)]

    order = taxonomy_order or {}
    unclassified = "未分类"
    buckets: dict[str, list[Problem]] = {}
    for problem in problems:
        key = problem.tags[0] if problem.tags else unclassified
        buckets.setdefault(key, []).append(problem)

    def sort_key(name: str) -> tuple[int, str]:
        return (order.get(name, len(order) + 1), name)

    return [(name, buckets[name]) for name in sorted(buckets, key=sort_key)]
