# 变更日志

按时间倒序。每条记「改了什么、为什么、怎么验的」，方便回头定位「这个改动当时凭什么是安全的」。

版本口径：`0.1.0` 尚无 release，下面按工作批次分组，批次名对应 git 提交主题。

---

## 2026-10-24 · CI 验证：`latex` workflow 在真 runner 上跑通

提交：`docs: latex workflow 已在 GitHub runner 上验证通过`

### 为什么

`latex.yml` 的 Debian TeX 包清单是按依赖关系推出来的——本机是 TeX Live 2026 全量安装，模拟不了 Ubuntu runner 的最小包布局，所以这条从没在真 GitHub runner 上跑过，是 `TODO.md` 里唯一「只能人做」的阻塞项。

### 结果

- 手动 `workflow_dispatch` 一次，**通过**：xelatex 编译、五套模板渲染、页数检查、Overfull / Missing character 扫描全绿。
- 已知隐患没有复现：`texlive-latex-extra` 不依赖 `texlive-pictures`，而 `tcolorbox` 的 `skins` 库需要 pgf/tikz，此前补的包是对的，说明「按依赖推包名 + 报错回填」这条路子可用。

### 文档

- `TODO.md` 第 0 节「阻塞项」清空。
- `PLAN.md` 第 7 条的「遗留风险」改为「已验证」。

---

## 2026-10-24 · 本地审计修复：gate 路径、GBK 报错、build 测试

提交：`fix: 慢速档假红 + 非 UTF-8 题库报错 + build.py 补测试`

### 改了什么、为什么

1. `scripts/gate.py` / `scripts/ci_latex_gate.py`：新增 `_abs_pythonpath()`，`_env()` 把 `PYTHONPATH` 每一项 `Path.resolve()` 成绝对路径并去重。
   - 为什么：`PLAN.md` 教用户写相对路径 `PYTHONPATH="src;.venv/Lib/site-packages"`，而插图 fixture 的子进程 cwd 是 `Temp/figcheck-*`，相对项一离开原目录就失效，症状是子进程 `ModuleNotFoundError: No module named 'yaml'`，在 gate 里表现为「插图 sheet: build 退出码 1」等 5 项**假红**。
   - 验证：`PYTHONPATH="src;.venv/Lib/site-packages" python scripts/gate.py slow` → 慢速档全部通过。
2. `src/ocrmath/store.py` 的 `load_problems()` 与 `src/ocrmath/cli.py` 的 `cmd_add()`：`read_text(encoding="utf-8")` 的 `UnicodeDecodeError` 单独捕获，报「文件不是 UTF-8 编码（可能是记事本另存的 GBK/ANSI），请另存为 UTF-8 后重试」，并带文件名。
   - 为什么：GBK/ANSI 题库会让 `UnicodeDecodeError` 漏到 `main()` 的兜底分支，用户只看到 `'utf-8' codec can't decode byte 0xd6 in position 41: invalid continuation byte`——既不知道是哪个文件，也不知道该怎么办。
   - 验证：新增 `tests/test_store.py::EncodingTests`、`tests/test_cli.py::AddEncodingTests`。
3. 新增 `tests/test_build.py`（14 个用例）：`src/ocrmath/build.py` 原先 118 行零测试。用 `mock.patch` 替换 `shutil.which` 与 `subprocess.run`，不依赖真 LaTeX，覆盖：latexmk 缺失、成功路径（拷 PDF + 解析页数）、`file:line:` 与 `! ` 两种报错格式、最多 5 条、解析不出时的退出码兜底、报成功但无 PDF、缺图、`TimeoutExpired`、`_tail` 截断、`BuildResult` 默认值互不共享。
4. `.github/workflows/quick.yml`：注释里的「67 个单测」改成 118，并把 `build` 加进覆盖清单（原数字是历史批次遗留的漂移）。
5. `.gitignore`：加 `.agent-teams/`（AgentTeams 会话状态）、`dist/`、`build/`、`*.egg-info/`；删掉根目录的空目录 `probe4-fyuzpwe0/`。

### 验证

- `python -m unittest discover -s tests` → 118 tests OK（原 102 + 新增 16）。
- `python scripts/gate.py slow` → 慢速档全部通过（含 pack 页数 2/3/4）。
- `python -m ocrmath validate --strict` → 9 题，0 错 0 警。

---

## 2026-10-20 · 文档：待办清单独立成 `TODO.md`

提交：`docs: 新增 TODO.md，待办与只能人工做的阻塞项集中一处`

### 为什么

待办原本散在 `PLAN.md` 的「下一步」一节，混着「已完成」的划掉条目、路线图说明和技术债。三种性质的东西挤在一起，结果是：

- 想知道「还剩什么没做」得先把已划掉的和设计说明过滤掉；
- 「需要人做的事」（比如去 GitHub 手动触发 workflow）和「我下次能做的事」没分开，容易漏；
- 完成一项后要同时改 `PLAN.md` 和别处，两边漂移。

### 现在

`TODO.md` 按三类组织：

| 分段 | 内容 |
|---|---|
| 0. 阻塞项 | 只能人做、我无法代劳的（当前只有一条：GitHub 上手动触发 `latex` workflow） |
| 1. 功能待办 | 按优先级；每条写了落点和坑，不是光一句「做 XX」 |
| 2. 技术债 / 已知限制 | 不急着做但要记着，含「为什么不现在做」的理由 |
| 3. 未决工具问题 | 本会话非 `run_code` 工具全挂，重启后需复验 |

`PLAN.md` 的「下一步」一节保留路线图视角，但顶部加了指向 `TODO.md` 的说明，明确「别再往这里加条目」。README 的「变更记录」段落改成四份文档的分工说明。

每条待办都写了验证方式和已知风险，而不是只留标题——例如「真实题目入库」标了「题数一变，`ci_pack_check.py` 的 `EXPECTED_PAGES` 必须同步改」，「多小问」标了「已有题目 statement 里内嵌了（1），混用会重复编号，建议先积累真实题目再抽象」。

---

## 2026-10-20 · 能力补强：含图题 + LaTeX 体检扩容

提交：`57970aa feat: 支持含图题，并把 LaTeX 体检扩到 & # _`（23 files, +848/-30）

### 背景：为什么要做这件事

审计（`AUDIT.md`）修的是「已知会出错的地方」，但它没回答一个问题——**换一批真实题型，管线还撑得住吗？**

做法是搭一个带 `templates/` 的临时项目，塞 10 道刻意刁难的题（多小问、`tabular` 表格、`pmatrix`+`cases`、需插图、转义字符、超长解析、极长题干、词表外 tag、选项内全角逗号），把五套模板全编一遍：

```
validate --strict  → 10 题 0 错误 1 警告
五模板 build        → 全部 exit 0（sheet 4 页 / card 10 页 / student 2 页 / answers 3 页 / teacher 4 页）
main.log            → Overfull=0 Underfull=0 MissingChar=0 Err=0
```

结论：**多小问（纯文本 `（1）（2）`）、表格、矩阵、超长题解析，现有管线本来就能扛**，不用动。真正的缺口只有两个，且都不是「错了」而是「做不到」：

1. 含图题完全排不了——导言区连 `graphicx` 都没有。
2. 校验只认 `%` 和 `$`，`&`、`#`、数学模式外的 `_` 一律放过，要等编译才炸。

### 改动 1：插图

| 文件 | 做了什么 |
|---|---|
| `src/ocrmath/schema.py` | `Problem` 增 `figures: list[str]`（相对 `data/`）与 `figure_width: float`（0.1–1.0，默认 0.6）；中文别名 `图 / 插图 / 图片`、`图宽`；`validate` 查宽度范围与空路径 |
| `templates/_figures.tex.j2`（新） | `figure()` 宏统一出 `\includegraphics[width=..\linewidth,keepaspectratio]`，`figures()` 宏遍历 |
| `templates/*.tex.j2`（5 个） | `{% import %}` 后在题干后插 `{{ fig.figures(p) }}` |
| `templates/_preamble.tex.j2` | 加 `\usepackage{graphicx}` |
| `src/ocrmath/render.py` | 新增 `_figure_height_mm()`；`_question_height_mm` 计入图高（按「正文宽 × 比例」当正方形，偏保守）；上下文里只传**文件名** |
| `src/ocrmath/build.py` | `build(..., figures=())`：编译前把图 `shutil.copyfile` 进构建目录；缺图提前返回 `ok=False` |
| `src/ocrmath/cli.py` | 新增 `_figure_issues()` 查文件存在（放 cli 而非 `Problem.validate`——校验器不该碰文件系统）；`_compile()` 把路径传给 `build` |

几个刻意的决定：

- **图拷进构建目录**，`main.tex` 只写文件名。好处是构建目录自包含，换机器/换目录重编不会因为绝对路径炸掉；Windows 上反斜杠还容易被 LaTeX 吃掉。
- **缺图在 build 层就失败**，不等 LaTeX 报一堆 `File not found`。错误信息直接给出手上有的那个路径。
- **文件存在性检查放在 cli**。`Problem.validate()` 是纯数据校验，测试里构造 `Problem` 时磁盘上没有那个 png 是正常的，不该因此失败。
- **高度估算按正方形估**，故意偏大。`\needspace` 宁可多留白，也不能让图被切到下一页。

### 改动 2：LaTeX 体检扩容

`_latex_issues()` 重写为环境跟踪版。扫描时维护 `$...$`、`\(...\)`、`\[...\]` 三个数学模式标记，以及 `\begin{}...\end{}` 的栈，然后新增三条 warning：

- 未转义 `&`（表格外会被当成对齐符）
- 未转义 `#`（macro parameter character）
- 数学模式外的 `_`（Missing $ inserted）

关键是**不能误报**：`tabular`/`matrix` 里的 `&` 是列分隔符，`cases`/`align` 里的 `_` 是下标，都是合法语法。所以维护了 `_MATH_ENVS` 与 `_ALIGN_ENVS` 两张名单，命中就跳过。

顺便修了一处逻辑：以前 `}` 多余时直接 `break` 掉整段扫描，后面的 `%`、`$` 检查全部跳过；现在 `depth = 0` 继续扫。

### 改动 3：列表写法里的全角逗号

`tags: [函数性质，导数应用]`（YAML list）以前不切分，整个串变成一个 tag，然后报「知识点不在词表中」——看起来像词表漏了条目，实则笔误。`_as_list(..., split_items=True)` 现在对 `tags`/`pitfalls` 生效。

**`choices` 明确不开**：`A. 1，2` 里的全角逗号属于选项内容，切开会把一个选项拆成两个（`AUDIT.md` 决策 A，不变）。

### 测试：67 → 102

- `tests/test_schema.py`：`ListItemSeparatorTests`（切分/保序/choices 不切）、`LaTeXSpecialCharTests`（9 个用例，含 tabular/matrix/cases/`\[...\]` 不误报）、`FigureFieldTests`（别名、回落、范围、round-trip、默认不写回）
- `tests/test_core.py`：`FigureRenderTests`（graphicx、只写文件名、宽度生效、多图按序、高度估算）
- `tests/test_coverage_fixture.py`（新）+ `tests/fixtures/coverage/`：10 道覆盖题，守住「多小问/表格/超长解析不炸」这条线
- `tests/fixtures/figures/`：1x1 PNG，验插图链路真能编过

### CI 慢速档跟进

`scripts/ci_latex_gate.py` 增一轮插图 fixture 编译（`--skip-figures` 可跳过）。这一轮除了要求 exit 0 和日志干净，还额外要求**日志里真的出现 `demo.png`**——否则「编译通过」可能只是 `includegraphics` 悄悄没生效，那比报错更危险。

`answers` 模板那一轮要加 `--echo`：它默认不重复题干，也就默认不显示图，不加就验不到那条分支。

### 验证

```
python -m unittest discover -s tests   → Ran 102 tests, OK
python -m ocrmath validate --strict    → 9 题，0 个错误，0 个警告，0 题缺解析
python scripts/gate.py all             → exit 0（快速档 + 慢速档，含插图 fixture 真编译）
```

负向验证：

- 缺图 → `[错误] fig-003.figures: 找不到插图文件 data/figs/not-there.png`，`validate` exit 1、`build` exit 2 且拒绝编译
- 删掉 fixture 里的 png → 插图那轮 5 套全部 exit 1（证明这一轮真的在看文件）

### 没做什么

`data/problems/` 仍是 9 道示例题。本轮加的是**能力**不是**内容**——真实题目要老师提供素材。因此页数基线 2/3/4 页保持不变，`ci_pack_check.py` 的 `EXPECTED_PAGES` 一个字没改。

---

## 2026-10-20 · CI 分两档落地

提交：`3657e69 ci: 分两档落 CI`（+559/-1）、`a690841 ci: latex.yml 补 texlive-pictures`

### 背景

`AUDIT.md` 里唯一没落地的项是 CI。落地时按成本切成两档——两边差一个数量级，混在一起只能二选一：要嘛贵到没人愿意等，要嘛便宜到抓不住版面回归。

| 档位 | 触发 | 耗时 | 内容 |
|---|---|---|---|
| 快速 `quick.yml` | push / PR | < 1 分钟 | 单测 + `validate --strict` + 五套模板 Jinja 渲染冒烟，**不装 TeX** |
| 慢速 `latex.yml` | 每日 02:00 + 手动 | ~10 分钟 | 五模板真编译 + `main.log` 机检 + `pack --strict` 页数核对 |

### 一个关键调整

原本打算快速档也跑 `pack --strict`。实测**没有 TeX 时 `pack` 必然 exit 1**（找不到 latexmk），所以改成直接调 `render()`：在 `StrictUndefined` 下把五套模板各渲染一遍，上下文少一个变量就红。这同样覆盖审计问题 2（`_answer_block` 宏要拿到 `steps`/`pitfalls`），但不需要 TeX。

编译与页数核对归慢速档。

### 新增脚本

| 脚本 | 作用 |
|---|---|
| `scripts/ci_render_smoke.py` | 渲染冒烟（不需 LaTeX） |
| `scripts/ci_latex_gate.py` | 五模板编译 + 日志机检 |
| `scripts/ci_pack_check.py` | `pack --strict` + 页数核对 |
| `scripts/gate.py` | 统一入口 `fast\|slow\|all`，本地复现 CI |

### 负向验证（确认不是摆设）

- 注入 `{{ nonexistent_variable }}` → exit 1，`UndefinedError`
- 空题库目录 → exit 1，「找不到模板目录」
- 注入 `\hbox to 1pt{\hskip 500pt}` → exit 1，`Overfull \hbox × 1，例：Overfull \hbox (499.0pt too wide) detected at line 28`
- `EXPECTED_PAGES` 改 student 99 → exit 1，「student 页数 2，期望 99（版面可能漂了）」

### 坑

`unittest discover` 不能加 `-t .`：`tests/` 没有 `__init__.py`，指定 top-level 会 `ImportError: Start directory is not importable`。

`latex.yml` 的 Debian 包清单：`texlive-latex-extra` 不依赖 `texlive-pictures`，而 `tcolorbox` 的 `skins` 库需要 pgf/tikz。漏装就是 `Package pgf Error`。

---

## 2026-10-20 · 审计修复（上一会话完成，本会话复验）

提交：`84ab2f0 fix: 修复审计发现的问题`、`6a6076a docs: 补审计台账与修复文档`

14 条问题 + `.gitattributes` 全部处理，逐条对照见 `AUDIT.md` 第一之二节与第九节。本会话只做复验、未改代码：

```
unittest discover -s tests   → Ran 67 tests, OK
validate --strict            → 9 题，0 个错误，0 个警告，0 题缺解析
pack --group-by tag --strict → student 2 页 / answers 3 页 / teacher 4 页
五模板 build                  → 全部 exit 0，main.log 中 Overfull=0 MissingChar=0 Err=0
```

页数与修复前完全一致，说明修复没有把版面挤变形。

---

## 待办与风险

**唯一遗留风险**：`latex.yml` 从未在 GitHub 上实跑过。Debian TeX 包名是按依赖关系推的，第一次夜间跑仍可能缺包。手动 `workflow_dispatch` 一次确认即可；失败时 workflow 会把 `out/.build/**/main.log` 传成 artifact。

**功能待办**（见 `PLAN.md`「下一步」）：真实题目入库（优先）> 多小问自动编号 > 答题横线/网格 > 答案册单独装订 > 题库批量导入。
