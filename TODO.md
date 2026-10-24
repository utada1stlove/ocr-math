# TODO

待办清单。`[ ]` 未做 / `[x]` 已完成 / `[!]` 需要你（人）来做。

按优先级从上往下。做完一项把 `[ ]` 改 `[x]` 并补一行「怎么验的」，
批量的历史改动记在 `CHANGELOG.md`，问题台账在 `AUDIT.md`。

最后更新：2026-10-25

---

## 0. 阻塞项：需要人来做，我无法代劳

（暂无。原先唯一的一条「在 GitHub 上手动触发一次 `latex` workflow」已于 2026-10-24 在真 runner 上跑通，
Debian TeX 包清单够用，详见 `CHANGELOG.md`。以后改模板或加宏包，仍要留意 runner 上可能缺包。）

## 1. 功能待办（按优先级）

- [ ] **真实题目入库**：把老师最近要布置的 10–20 道题录进 `data/problems/`。
  这是唯一能暴露新问题的一步，其余功能在只有 9 道示例题的情况下做了也没法验证。
  - 需要你提供题源（图片 / Word / 手写照片都行）。
  - 验证方式：`python -m ocrmath validate --strict` 全绿 + `pack --strict` 页数**合理**（不必等于 2/3/4 页，但要能解释）。
  - 注意：一旦题数变化，`scripts/ci_pack_check.py` 里写死的 `EXPECTED_PAGES = {"student": 2, "answers": 3, "teacher": 4}` 必须同步改，否则慢速档会红。这是有意的设计——页数是版面回归最灵敏的信号。
  - 入库 10 题以上时，考虑拆成多个 yaml（按章节），`problem_files()` 会全部读入。

- [ ] **多小问自动编号**：题干里的 `（1）（2）（3）` 现在是纯文本，排版上能扛（覆盖性 fixture 已证明），但没有结构化编号。
  - 若真需要：加 `parts: list[str]` 字段，模板里用 `enumitem` 的 `label=（\arabic*）` 排。
  - 风险：会让题库格式变复杂，且已有题目的 `statement` 里内嵌了 `（1）`，混用会重复编号。**建议先积累真实题目，看看到底有多少题需要**，别过早抽象。

- [ ] **答题横线 / 网格**：学生卷可选 `--ruled` 或每题 `answer_lines: 3`，模板里画 `\dotfill` 或方格。
  - 落点：`schema.py` 加 `answer_lines: int`，`student.tex.j2` 里循环出横线，`TEMPLATE_OPTIONS` 登记 `ruled` 只归 student。
  - 注意：`student` 模板目前**刻意**忽略 `workspace_mm`（老师的要求，见 `PLAN.md` 设计决定 5），加横线时要一并想清楚这两者的关系，别做成两套互相打架的留白机制。

- [ ] **答案册单独装订**：`pack` 加 `--booklet`，answers 用 A5 或双栏、可对折。
  - 落点：`RenderConfig` 加 `booklet`，`answers.tex.j2` 的 geometry 与分栏改为条件化。
  - 注意：这是版面级改动，务必跑 `python scripts/gate.py all` 确认其余四套模板没被波及。

- [ ] **题库批量导入**：从 Markdown / Word 粘贴格式批量转 YAML。
  - 比 OCR 更实用——题源通常是老师自己找来的电子版，不是照片。
  - 落点：新建 `src/ocrmath/importer/`，不要塞进 `ingest/`（那是图像识别的职责）。
  - 验收：导入结果必须过 `validate --strict`，且能 `add` 进库不丢注释（`tests/test_store.py::AppendProblemTests` 守着这条）。

## 2. 技术债 / 已知限制（不急着做，但要记着）

- [x] **`build.py` 零测试**：已补 `tests/test_build.py`（14 个用例，mock 掉 latexmk 与 subprocess）。
  验证：`python -m unittest discover -s tests`。
- [x] **非 UTF-8 题库文件报错不友好**：现在报「文件不是 UTF-8 编码（可能是记事本另存的 GBK/ANSI），请另存为 UTF-8 后重试」并带文件名。
  验证：`tests/test_store.py::EncodingTests`、`tests/test_cli.py::AddEncodingTests`。
- [x] **慢速档按文档写相对 `PYTHONPATH` 会假红**：`scripts/gate.py` 与 `scripts/ci_latex_gate.py` 的 `_env()` 现在把每项解析成绝对路径。
  验证：`PYTHONPATH="src;.venv/Lib/site-packages" python scripts/gate.py slow` 全绿。
- [x] **CLI 没有 `--version`**：已加顶层 `--version`，取值来自 `src/ocrmath/__init__.py` 的 `__version__`。
  验证：`tests/test_cli.py::VersionTests`。
- [x] **`pyproject.toml` 缺发布元数据**：补了 `readme` / `license` / `license-files` / `authors` / `[project.urls]`，`setuptools>=68` → `>=77`。
  验证：wheel 的 `METADATA` 里有 `License-Expression: GPL-3.0-only` 与三条 `Project-URL`。
- [x] **`--seed` 没有可复现测试**：`tests/test_select.py::SeedTests` 守着「同 seed 同序、只重排不丢题」。
- [x] **`add` 查重复 id 是 O(n²)**：改成一次 `Counter`；顺带补了「一批内 id 撞车整批拒写」的测试。
  验证：`tests/test_cli.py::AddDuplicateTests`。
- [ ] **`_as_list` 对 YAML list 也不切分的历史包袱**：现在 `tags`/`pitfalls` 已开 `split_items=True`，但 `steps` 仍按 `\n` 切、`choices` 按 `[;,；\n]` 切。这套规则散落在 `from_mapping` 的调用点上，加字段时容易漏。考虑集中成一张「字段 → 分隔符」表。
- [ ] **`EXPECTED_PAGES` 写死在脚本里**：改题库就要手改。可选做法是把它挪到 `tests/fixtures/` 旁边的 json，或改成「页数变化超过 ±20% 才报警」。**暂时不改**——写死更有约束力，等真被它烦到再说。
- [ ] **`quick.yml` 的 Python 3.10 没在本地实测**：本机只有 3.14.7。已扫过全仓无 3.11+ 专属语法（无 `tomllib` / `Self` / `StrEnum` / `match` / `except*`），但 CI 会是第一次真跑 3.10。
- [ ] **插图高度按正方形估算**：`_figure_height_mm` 不知道真实宽高比，一律按「正文宽 × 比例」当正方形，偏大。宁可多留白也不让图被切到下一页，所以方向是对的；如果真遇到「图很扁但留了一整页空白」，再考虑引入 Pillow 读尺寸（会多一个依赖，权衡后再定）。
- [ ] **`.tmp/pip-*` 20 个残留目录删不掉**：受 Windows ACL 影响，已 gitignore，不影响运行。已知问题，别纠缠。

## 3. 环境与工具的已知问题

- [!] **`pwsh` 工具起不来**：报 `PTY shell exited during startup`。本机一切命令改走 bash（`ops_bash`），路径写 `/d/workspace/ocr-math` 这种形式。中文输出需加 `PYTHONIOENCODING=utf-8`，否则 bash 侧按 GBK 解码成乱码。
- [!] **`ops_bash` 偶发 `Auto review of tool failed`**：报 `Unexpected token '<', "<｜｜DSML｜｜" ...`，命令体不会被执行。**重试同一条命令即可成功**，不是命令本身有问题，别去改命令。
- **打 wheel 要绕一下**：本机 `.venv` 里没有 pip（`No module named pip`），系统 `C:\Python314` 有 pip 26.2.1 但没有 setuptools。验证发布元数据时用的是
  `PYTHONPATH=".venv/Lib/site-packages" python -m pip wheel . -w .tmp/dist --no-deps --no-build-isolation`
  ——把 venv 的 setuptools 借给系统 python。`--no-build-isolation` 是必须的，否则 pip 会去建隔离环境并联网拉 setuptools。
- 历史记录（已过期）：上一会话曾出现非 `run_code` 工具全部不可用、通道坏死，重启后已恢复。

## 4. 审计发现的不足（2026-10-25，尚未处理）

和第 2 节的区别：第 2 节是代码内部的技术债，这里是安装、CI、数据模型层面的窟窿。每条都写了「真出事时怎么修」，免得下次重新推导一遍。

### 4.1 安装与分发

- [ ] **`pip install --target` / zipapp 装完后找不到数据**：`_installed_root()`（`src/ocrmath/cli.py:95-114`）只查 `sysconfig` 的 `data`/`purelib`/`platlib` 三个 scheme 加 `sys.prefix`；`--target` 装到任意目录时不在这三处，于是回落到当前目录，最后报的是 `src/ocrmath/store.py:51`「找不到知识点词表 {path}：请确认 --root 指向项目根目录」或 `src/ocrmath/cli.py:121-124`「没有找到任何 .yaml：请确认 --root 指向项目根目录」——两句话都把锅甩给用户的 `--root`，真实原因却是「这种安装布局不认识」。
  - 修法：`_installed_root()` 补 `importlib.metadata.distribution("ocrmath").files()` 推导，或以 `Path(__file__)` 往上找 `share/ocrmath`；报错文案拆成「目录里确实没有题库」与「安装布局不受支持，请用 pip install 或显式给 --root」两种。
  - 为什么现在不改：`pip install` 正常装已验证可用（装进干净 venv 后从别的目录跑 `list` 正常），`--target` 是边缘用法。
- [ ] **没有声明开发依赖组**：`pyproject.toml` 里没有 `[project.optional-dependencies] dev`。测试只用标准库 `unittest`，所以不缺依赖，但「新机器上怎么把环境跑起来」只写在 README 里，没有一行可执行的安装命令。

### 4.2 CI 与工具链

- [ ] **CI 只在 ubuntu-latest 上跑**：`.github/workflows/quick.yml:23` 与 `.github/workflows/latex.yml:20` 都是 `runs-on: ubuntu-latest`，而项目实际在 Windows 上开发。`ctexart` 字体、路径分隔符、CRLF 这些平台差异 CI 一点都测不到。
  - 权衡：给 `quick` 加 windows-latest job 便宜（只要 Python 依赖）；`latex` 在 Windows runner 上装 TeX Live 很慢，不值得。
- [ ] **没有 lint / 格式化配置**：`pyproject.toml` 里只有 `[tool.setuptools.*]`，没有 `[tool.ruff]` 之类。代码风格现在靠人盯。
- [ ] **慢速档没覆盖 `pack` 的版式**：`scripts/ci_latex_gate.py` 对五套模板都传 `--group-by tag`，而 `pack` 走的是 `group_by="none"`。页数回归由 `scripts/ci_pack_check.py` 兜着，但 Overfull / Missing character 的扫描只覆盖了「按知识点分组」这一条路径。

### 4.3 数据模型

- [ ] **题库 YAML 没有 `schema_version`**：以后加 `parts` / `answer_lines` 这类字段时没有迁移钩子，也没法对老文件走兼容分支。现在 9 道题全是手写的，加字段等于「全体同时升级」，暂时不痛。

### 4.4 未验证的规模

- [ ] **没做过题库规模测试**：`src/ocrmath/cli.py:118` 的 `_load()` 每次全量读 `data/problems/*.yaml`，没有缓存。9 道题无感，上千题时 `list` / `pack` 的启动开销没测过。

### 4.5 文档口径

- [ ] **历史文档里的数字会继续脱节**：`AUDIT.md` 是批次台账（测试数、行数都是当时的快照），`README.md` 里「本项目在 3.14 上验证」也要等 `quick.yml` 的 3.10 job 结果。处理原则是「历史文档不改写，变化只追加到 `CHANGELOG.md`」——这条原则目前只在对话里说过，没写进文档，下次容易有人去把 `AUDIT.md` 的数字刷一遍。
