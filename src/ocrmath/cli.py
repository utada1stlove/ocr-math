"""命令行入口：ocrmath build / pack / list / validate / add / ocr。

同一份题库，四种产物：
  build  出单份文档（sheet 练习册 / card 卡片 / student 纯题 / answers 详解 / teacher 教师版）
  pack   一次出 student + answers + teacher 三份，并写 manifest.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import yaml

from .build import BuildResult, build
from .ingest import get_engine
from .render import RenderConfig, render
from .schema import Problem
from .select import SelectOptions, select_problems
from .store import Taxonomy, append_problem, load_problems, problem_files

# pack 生成的顺序即发给学生的顺序：先题、再答案、最后教师版
PACK_KINDS = ("student", "answers", "teacher")
ALL_TEMPLATES = ("sheet", "card") + PACK_KINDS

# 给人看的模板名
TEMPLATE_LABELS = {
    "sheet": "习题册",
    "card": "单题卡",
    "student": "学生卷",
    "answers": "参考详解",
    "teacher": "教师版",
}

# 每个模板实际会读哪些「版式参数」：cli 声明了参数、模板却不读，就等于哑弹。
# 逐个核对过模板里的 cfg.* 引用：sheet 读 gap/workspace/fill/answers，
# card 读 workspace/answers，student 读 gap/one_per_page，answers/teacher 读 echo。
TEMPLATE_OPTIONS = {
    "sheet": {"gap", "workspace", "fill", "answers"},
    "card": {"workspace", "answers"},
    "student": {"gap", "one_per_page"},
    "answers": {"echo"},
    "teacher": {"echo"},
}

_OPTION_LABELS = {
    "gap": "--gap",
    "workspace": "--workspace",
    "fill": "--fill",
    "answers": "--answers",
    "echo": "--echo",
    "one_per_page": "--one-per-page",
}

# 与 argparse 里的默认值保持一致（判断「用户是否显式设过」用）
_OPTION_DEFAULTS = {"gap": 6.0, "workspace": 40.0}


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    explicit_root = args.root is not None
    start = Path(args.root).expanduser() if explicit_root else Path.cwd()
    root = _resolve_root(start, explicit=explicit_root)
    try:
        return args.func(args, root)
    except (ValueError, KeyError, RuntimeError, OSError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2


def _resolve_root(start: Path, *, explicit: bool) -> Path:
    """确定项目根目录。

    ``--root`` 显式给出的路径一律尊重（找不到就让后面的加载报错，不猜）；
    用默认值（当前目录）时，如果当前目录不像项目根（没有 ``data/taxonomy.yaml``），
    就往上找——这样在 ``src/``、``out/``、``templates/`` 里跑命令也能正常工作。
    往上找不到时（比如 pip 安装后在任意目录调用），退回到安装时附带的数据目录。
    """
    resolved = start.resolve()
    if explicit:
        return resolved
    for candidate in [resolved, *resolved.parents]:
        if (candidate / "data" / "taxonomy.yaml").exists():
            return candidate
    return _installed_root() or resolved


def _installed_root() -> Path | None:
    """pip 安装时 data-files 落在 <prefix>/share/ocrmath/，那里有 taxonomy.yaml 就用它。"""
    import sysconfig

    candidates = []
    for scheme in ("data", "purelib", "platlib"):
        try:
            candidates.append(Path(sysconfig.get_path(scheme)) / "share" / "ocrmath")
        except KeyError:  # 少见的自定义 scheme
            continue
    try:
        prefix = Path(sys.prefix) / "share" / "ocrmath"
    except (NameError, OSError):  # pragma: no cover - 理论兜底
        prefix = None
    if prefix is not None:
        candidates.append(prefix)
    for candidate in candidates:
        if (candidate / "data" / "taxonomy.yaml").exists():
            return candidate
    return None


# --------------------------------------------------------------------- 公共步骤
def _load(root: Path) -> tuple[Taxonomy, list[Problem], list]:
    taxonomy = Taxonomy.load(root / "data" / "taxonomy.yaml")
    files = problem_files(root / "data")
    if not files:
        raise FileNotFoundError(
            f"在 {root / 'data' / 'problems'} 下没有找到任何 .yaml：请确认 --root 指向项目根目录"
        )
    problems, issues = load_problems(files)
    for problem in problems:
        issues.extend(problem.validate(taxonomy.known_tags))
    return taxonomy, problems, issues


def _report(issues, *, fail: bool = True) -> bool:
    """打印问题；有 error 返回 False。"""
    for issue in issues:
        stream = sys.stderr if issue.level == "error" else sys.stdout
        print(issue, file=stream)
    has_error = any(issue.level == "error" for issue in issues)
    return not (has_error and fail)


def _select(problems: list[Problem], args: argparse.Namespace) -> list[Problem]:
    options = SelectOptions(
        ids=_split(args.ids),
        tags=_split(args.tags),
        tag_mode=args.tag_mode,
        difficulty_min=args.difficulty[0],
        difficulty_max=args.difficulty[1],
        limit=args.limit,
        seed=args.seed,
    )
    return select_problems(problems, options)


def _config(
    args: argparse.Namespace, template: str, title: str | None = None, group_by: str | None = None
) -> RenderConfig:
    return RenderConfig(
        template=template,
        title=title if title is not None else args.title,
        subtitle=args.subtitle,
        answers=getattr(args, "answers", "none"),
        gap_mm=args.gap,
        workspace_mm=args.workspace,
        fill=getattr(args, "fill", False),
        show_tags=args.show_tags,
        show_difficulty=args.show_difficulty,
        group_by=group_by if group_by is not None else args.group_by,
        font_size=args.font_size,
        margin_mm=args.margin,
        seed=args.seed,
        one_per_page=getattr(args, "one_per_page", False),
        echo_statement=getattr(args, "echo", False),
    )


def _compile(root: Path, chosen: list[Problem], taxonomy: Taxonomy, cfg: RenderConfig, out_pdf: Path) -> BuildResult:
    tex = render(chosen, taxonomy, cfg, root / "templates")
    result = build(tex, out_pdf, root / "out" / ".build" / out_pdf.stem)
    if result.ok:
        print(f"PDF   {out_pdf}（{result.pages} 页，{len(chosen)} 题）")
    return result


def _print_failure(result: BuildResult) -> None:
    print("编译失败：", file=sys.stderr)
    for error in result.errors:
        print(error, file=sys.stderr)
    print("\n--- 日志末尾 ---", file=sys.stderr)
    print(result.log_tail, file=sys.stderr)


def _content_checks(chosen: list[Problem], template: str) -> list[str]:
    """针对不同产物做内容提醒：不阻断编译，但会写进 stderr / manifest。"""
    warnings: list[str] = []
    if template in ("answers", "teacher"):
        no_answer = [p.id for p in chosen if not p.answer.strip()]
        if no_answer:
            warnings.append(f"{template}：{len(no_answer)} 题没有【答案】：{'、'.join(no_answer)}")
        no_detail = [p.id for p in chosen if not p.steps and not p.solution.strip()]
        if no_detail:
            warnings.append(
                f"{template}：{len(no_detail)} 题只有答案、没有解析（建议补 steps 分步）：{'、'.join(no_detail)}"
            )
    if template == "student":
        has_workspace = [p.id for p in chosen if p.workspace_mm]
        if has_workspace:
            warnings.append("student：模板不含留白，以下题目的 workspace_mm 被忽略：" + "、".join(has_workspace))
    return warnings


def _option_warnings(
    args: argparse.Namespace,
    template: str,
    *,
    scope: str = "",
    defaults: dict[str, float] | None = None,
    supported: set[str] | None = None,
) -> list[str]:
    """cli 里声明了、但该模板根本不会读的参数，明确告警，别让人以为调了就有用。

    ``supported`` 用于 pack：一份参数只要能被本次产出的任一文档读到，就不算哑弹，
    否则 ``pack --one-per-page`` 会因为答案册/教师版不读它而刷出两条假警告。
    """
    supported = TEMPLATE_OPTIONS[template] if supported is None else supported
    numeric_defaults = {**_OPTION_DEFAULTS, **(defaults or {})}
    warnings: list[str] = []
    for name in ("gap", "workspace", "fill", "answers", "echo", "one_per_page"):
        if name in supported:
            continue
        value = getattr(args, name, None)
        # 只有用户「真的传了」才告警：与默认值相同就不算
        if name in ("fill", "echo", "one_per_page"):
            touched = bool(value)
        elif name == "answers":
            touched = value not in (None, "none")
        else:  # gap / workspace
            touched = value is not None and value != numeric_defaults[name]
        if touched:
            where = f"{scope} " if scope else ""
            warnings.append(
                f"{where}{_OPTION_LABELS[name]} 对 {template}（{TEMPLATE_LABELS[template]}）模板无效，已忽略"
            )
    return warnings


# --------------------------------------------------------------------- 子命令
def cmd_build(args: argparse.Namespace, root: Path) -> int:
    taxonomy, problems, issues = _load(root)
    if not _report(issues):
        print("题库存在错误，先修好再编译。", file=sys.stderr)
        return 2

    chosen = _select(problems, args)
    if not chosen:
        print("没有题目满足筛选条件。", file=sys.stderr)
        return 2

    for warning in _content_checks(chosen, args.template):
        print(f"[提示] {warning}", file=sys.stderr)
    for warning in _option_warnings(args, args.template):
        print(f"[提示] {warning}", file=sys.stderr)

    cfg = _config(args, args.template)
    out_pdf = Path(args.out) if args.out else Path("out") / f"{cfg.template}.pdf"
    if not out_pdf.is_absolute():
        out_pdf = root / out_pdf

    result = _compile(root, chosen, taxonomy, cfg, out_pdf)
    if not result.ok:
        _print_failure(result)
        return 1
    return 0


def cmd_pack(args: argparse.Namespace, root: Path) -> int:
    taxonomy, problems, issues = _load(root)
    if not _report(issues):
        print("题库存在错误，先修好再打包。", file=sys.stderr)
        return 2

    chosen = _select(problems, args)
    if not chosen:
        print("没有题目满足筛选条件。", file=sys.stderr)
        return 2

    skipped = _split(getattr(args, "skip", ""))
    unknown = [name for name in skipped if name not in PACK_KINDS]
    if unknown:
        print(
            f"--skip 不认识这些值：{'、'.join(unknown)}（可选：{', '.join(PACK_KINDS)}）",
            file=sys.stderr,
        )
        return 2
    kinds = [kind for kind in PACK_KINDS if kind not in skipped]
    if not kinds:
        print(
            f"--skip 把三份文档全跳过了：{', '.join(PACK_KINDS)} 至少要留一份。",
            file=sys.stderr,
        )
        return 2
    warnings: dict[str, list[str]] = {}
    # 本次产出会用到哪些版式参数：只要有一份文档读它，整条命令层面就不算哑弹
    pack_supported = set().union(*(TEMPLATE_OPTIONS[kind] for kind in kinds))
    for kind in kinds:
        warnings[kind] = _content_checks(chosen, kind) + _option_warnings(
            args, kind, scope=f"pack 的 {kind}：", defaults={"gap": 8.0}, supported=pack_supported
        )
        for warning in warnings[kind]:
            print(f"[提示] {warning}", file=sys.stderr)
    gaps = [
        w for kind_warnings in warnings.values() for w in kind_warnings if "workspace_mm 被忽略" not in w
    ]
    if args.strict and gaps:
        print("严格模式下存在内容缺口，未打包（去掉 --strict 可先出稿）。", file=sys.stderr)
        return 2

    out_dir = Path(args.out) if args.out else Path("out") / args.name
    if not out_dir.is_absolute():
        out_dir = root / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    documents, failures = [], []
    for kind in kinds:
        # 学生版按知识点分组；答案与教师版连续编号，避免分组标题把版面切碎
        group_by = args.group_by if kind == "student" else "none"
        cfg = _config(args, kind, _pack_title(kind, args.title), group_by=group_by)
        out_pdf = out_dir / f"{kind}.pdf"
        result = _compile(root, chosen, taxonomy, cfg, out_pdf)
        if not result.ok:
            _print_failure(result)
            failures.append(kind)
            continue
        documents.append(
            {
                "kind": kind,
                "title": cfg.title,
                "pdf": f"{kind}.pdf",
                "pages": result.pages,
                "problems": len(chosen),
            }
        )

    manifest = {
        "name": args.name,
        "title": args.title,
        "subtitle": args.subtitle,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "problems": [p.id for p in chosen],
        "documents": documents,
        "warnings": warnings,
        "failed": failures,
    }
    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n打包目录 {out_dir}")
    for doc in documents:
        print(f"  {doc['kind']:<8}{doc['pdf']:<12}{doc['pages']} 页")
    print(f"  manifest.json")
    if failures:
        print(f"以下文档编译失败：{'、'.join(failures)}", file=sys.stderr)
        return 1
    return 0


def cmd_list(args: argparse.Namespace, root: Path) -> int:
    taxonomy, problems, issues = _load(root)
    _report(issues, fail=False)
    if not problems:
        print("题库为空。")
        return 0

    print(f"{'ID':<16}{'难度':<6}{'知识点':<24}{'解析':<4}题干")
    for problem in problems:
        snippet = " ".join(problem.statement.split())
        if len(snippet) > 36:
            snippet = snippet[:36] + "…"
        tags = "、".join(problem.tags) or "-"
        detail = "有" if problem.steps or problem.solution else "缺"
        print(f"{problem.id:<16}{problem.difficulty:<6}{tags:<24}{detail:<4}{snippet}")
    print(f"\n共 {len(problems)} 题；知识点词表：{len(taxonomy.known_tags)} 个")
    return 0


def cmd_validate(args: argparse.Namespace, root: Path) -> int:
    taxonomy, problems, issues = _load(root)
    detail_gap = [p.id for p in problems if not p.steps and not p.solution.strip()]
    for issue in issues:
        print(issue)
    if detail_gap:
        print(f"[提示] {len(detail_gap)} 题缺解析（steps/solution），答案页与教师版会偏薄：{'、'.join(detail_gap)}")
    errors = [i for i in issues if i.level == "error"]
    warnings = [i for i in issues if i.level == "warning"]
    print(f"\n{len(problems)} 题，{len(errors)} 个错误，{len(warnings)} 个警告，{len(detail_gap)} 题缺解析")
    if errors or (args.strict and warnings):
        return 1
    return 0


def cmd_add(args: argparse.Namespace, root: Path) -> int:
    taxonomy = Taxonomy.load(root / "data" / "taxonomy.yaml")
    path = Path(args.file)
    if not path.is_absolute():
        path = root / path
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict) and "problems" in raw:
        raw = raw["problems"]
    if isinstance(raw, dict):
        raw = [raw]
    if not isinstance(raw, list):
        raise ValueError(f"{path} 应为单道题或题目列表")

    parsed: list[Problem] = []
    issues = []
    for item in raw:
        problem = Problem.from_mapping(item)
        parsed.append(problem)
        issues.extend(problem.validate(taxonomy.known_tags))

    for issue in issues:
        print(issue)
    if any(i.level == "error" for i in issues):
        print("存在错误，未写入题库。", file=sys.stderr)
        return 1

    target = Path(args.into) if args.into else Path("data") / "problems" / "inbox.yaml"
    if not target.is_absolute():
        target = root / target
    existing, _ = load_problems([target]) if target.exists() else ([], [])
    existing_ids = {p.id for p in existing}

    # 先把整批校验完再写：以前是「写一道、撞 id、返回 1」，
    # 于是撞 id 之前的那几道已经落盘，但命令报告失败，调用方无从判断到底写进去几道。
    conflicts = [p.id for p in parsed if p.id in existing_ids]
    if conflicts:
        print(f"错误：这些 id 已存在于 {target}：{'、'.join(conflicts)}", file=sys.stderr)
        return 1
    dupes = sorted({p.id for p in parsed if [q.id for q in parsed].count(p.id) > 1})
    if dupes:
        print(f"错误：待写入的题目里 id 自身重复：{'、'.join(dupes)}", file=sys.stderr)
        return 1

    for problem in parsed:
        append_problem(target, problem)
        print(f"已写入 {problem.id} -> {target}")
    return 0


def cmd_ocr(args: argparse.Namespace, root: Path) -> int:
    engine = get_engine(args.engine)
    available, reason = engine.available()
    if not available:
        print(f"引擎不可用：{reason}", file=sys.stderr)
        return 2

    image = Path(args.image)
    if not image.is_absolute():
        image = root / image
    if not image.exists():
        print(f"图片不存在：{image}", file=sys.stderr)
        return 2

    result = engine.recognize(image)
    for warning in result.warnings:
        print(f"[提示] {warning}", file=sys.stderr)
    if not result.problems:
        print("没有识别结果。", file=sys.stderr)
        return 1

    payload = {"problems": [p.to_mapping() for p in result.problems]}
    text = yaml.safe_dump(payload, allow_unicode=True, sort_keys=False, width=1000)
    if args.out:
        out = Path(args.out)
        if not out.is_absolute():
            out = root / out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        print(f"已写入 {out}（请人工核对后 ocrmath add 入库）")
    else:
        print(text)
    return 0


# --------------------------------------------------------------------- 工具
def _pack_title(kind: str, base: str) -> str:
    suffix = {"student": "", "answers": " · 参考答案与详解", "teacher": " · 教师版"}[kind]
    if not base:
        return {"student": "", "answers": "参考答案与详解", "teacher": "教师版（含答案、解析、易错点与讲评）"}[kind]
    return base + suffix


def _split(text: str | None) -> list[str]:
    """逗号分隔的列表参数。中文输入法下会打出全角逗号/分号，一并认。"""
    if not text:
        return []
    return [part.strip() for part in re.split(r"[,，;；]", text) if part.strip()]


def _difficulty(text: str) -> tuple[int, int]:
    raw = text.strip().replace("－", "-").replace("—", "-").replace("–", "-")
    if "-" in raw:
        low, high = raw.split("-", 1)
        try:
            low_i, high_i = int(low), int(high)
        except ValueError:
            raise argparse.ArgumentTypeError(f"难度范围应形如 1-3，收到 {text!r}") from None
    else:
        try:
            low_i = high_i = int(raw)
        except ValueError:
            raise argparse.ArgumentTypeError(f"难度范围应形如 1-3，收到 {text!r}") from None
    for value in (low_i, high_i):
        if not 1 <= value <= 5:
            raise argparse.ArgumentTypeError("难度范围必须在 1–5")
    # 写反了会在选题时静默得到空集，看起来像「题库里没有这个难度的题」
    if low_i > high_i:
        raise argparse.ArgumentTypeError(f"难度区间写反了：{low_i} > {high_i}（想写的是 {high_i}-{low_i}）")
    return low_i, high_i


def _positive_int(text: str) -> int:
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"应为正整数，收到 {text!r}") from None
    if value < 1:
        raise argparse.ArgumentTypeError(f"应为正整数，收到 {value}")
    return value


def _add_selection(p: argparse.ArgumentParser) -> None:
    p.add_argument("--ids", help="按 id 选题，逗号分隔")
    p.add_argument("--tags", help="按知识点选题，逗号分隔")
    p.add_argument("--tag-mode", default="any", choices=["any", "all"])
    p.add_argument("--difficulty", type=_difficulty, default=(1, 5), help="难度范围，如 1-3")
    p.add_argument("--limit", type=_positive_int, help="最多几题（正整数）")
    p.add_argument("--seed", type=int)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ocrmath", description="数学试题 -> LaTeX -> PDF")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_root(p: argparse.ArgumentParser) -> None:
        p.add_argument("--root", default=None, help="项目根目录（默认当前目录，向上自动查找）")

    # ---------------------------------------------------------------- build
    build_p = sub.add_parser("build", help="选题并编译单份 PDF")
    add_root(build_p)
    build_p.add_argument("--out", help="输出 PDF 路径（默认 out/<template>.pdf）")
    build_p.add_argument("--template", default="sheet", choices=list(ALL_TEMPLATES))
    build_p.add_argument("--title", default="", help="标题")
    build_p.add_argument("--subtitle", default="", help="副标题")
    build_p.add_argument("--answers", default="none", choices=["none", "end", "inline"])
    build_p.add_argument("--gap", type=float, default=6.0, help="题间距 mm")
    build_p.add_argument("--workspace", type=float, default=40.0, help="默认草稿留白 mm")
    build_p.add_argument("--fill", action="store_true", help="页内平均撑开")
    build_p.add_argument("--one-per-page", action="store_true", help="每组题之后强制分页")
    build_p.add_argument("--echo", action="store_true", help="答案页重复题干")
    build_p.add_argument("--show-tags", action="store_true")
    build_p.add_argument("--show-difficulty", action="store_true")
    build_p.add_argument("--group-by", default="none", choices=["none", "tag"])
    build_p.add_argument("--font-size", default="11pt")
    build_p.add_argument("--margin", type=float, default=20.0)
    _add_selection(build_p)
    build_p.set_defaults(func=cmd_build)

    # ---------------------------------------------------------------- pack
    pack_p = sub.add_parser("pack", help="一次生成 学生版 + 答案详解 + 教师版")
    add_root(pack_p)
    pack_p.add_argument("--name", default="pack", help="输出目录名（默认 out/pack）")
    pack_p.add_argument("--out", help="输出目录（默认 out/<name>）")
    pack_p.add_argument("--title", default="", help="标题（三份文档共用前缀）")
    pack_p.add_argument("--subtitle", default="", help="副标题")
    pack_p.add_argument("--gap", type=float, default=8.0, help="学生版题间距 mm")
    pack_p.add_argument("--workspace", type=float, default=40.0, help="留白计算用（学生版不使用）")
    pack_p.add_argument("--one-per-page", action="store_true", help="学生版一题一页")
    pack_p.add_argument("--echo", action="store_true", help="答案页重复题干")
    pack_p.add_argument("--show-tags", action="store_true")
    pack_p.add_argument("--show-difficulty", action="store_true")
    pack_p.add_argument("--group-by", default="tag", choices=["none", "tag"])
    pack_p.add_argument("--font-size", default="11pt")
    pack_p.add_argument("--margin", type=float, default=20.0)
    pack_p.add_argument("--skip", default="", help="跳过某些产物：student,answers,teacher 的子集")
    pack_p.add_argument("--strict", action="store_true", help="答案/解析有缺口就不打包")
    _add_selection(pack_p)
    pack_p.set_defaults(func=cmd_pack)

    # ---------------------------------------------------------------- 其它
    list_p = sub.add_parser("list", help="列出题库")
    add_root(list_p)
    list_p.set_defaults(func=cmd_list)

    validate_p = sub.add_parser("validate", help="校验题库")
    add_root(validate_p)
    validate_p.add_argument("--strict", action="store_true", help="警告也算失败")
    validate_p.set_defaults(func=cmd_validate)

    add_p = sub.add_parser("add", help="把 YAML 题目校验后加入题库")
    add_root(add_p)
    add_p.add_argument("file", help="题目 YAML（单题或列表）")
    add_p.add_argument("--into", help="目标题库文件（默认 data/problems/inbox.yaml）")
    add_p.set_defaults(func=cmd_add)

    ocr_p = sub.add_parser("ocr", help="图片 -> 题目 YAML 草稿")
    add_root(ocr_p)
    ocr_p.add_argument("image")
    ocr_p.add_argument("--engine", default="local", choices=["local", "cloud"])
    ocr_p.add_argument("--out", help="输出 YAML 路径（默认打印到终端）")
    ocr_p.set_defaults(func=cmd_ocr)

    return parser


if __name__ == "__main__":
    raise SystemExit(main())
