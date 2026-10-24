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
- 历史记录（已过期）：上一会话曾出现非 `run_code` 工具全部不可用、通道坏死，重启后已恢复。
