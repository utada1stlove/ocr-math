# 项目计划与状态（给下一次会话的自己）

最后更新：2026-10-20。这份文件是“下一步做什么、为什么这么做”的索引；具体用法看 `README.md`。

## 一句话目标

把数学题（自己找的题 / 自己出的题）存成 YAML 题库，一键生成**学生卷 / 答案详解 / 教师版**三份 PDF，版式可调、题号一致，不需要重复排版。

## 当前状态：M1 已完成；M1.5 审计修复与 CI 已完成；M2 起（能力补强）进行中

> 文档分工：`TODO.md` 待办 · `CHANGELOG.md` 变更记录 · `AUDIT.md` 审计台账 · 本文件 = 设计与状态索引。

- 数据层：`data/problems/*.yaml`（9 道示例题：fx-001/002/003、tri-001、seq-001、geo-001/002、prob-001、ineq-001），字段 `statement/choices/answer/solution/steps/pitfalls/hint/teaching/tags/difficulty/workspace_mm/source/figures/figure_width`，中英文键名都认；另有 `extra` 兜住本工具不认识的键（`ocr_from`、教研备注等），`add` 追加写回时原样保留。
- 词表：`data/taxonomy.yaml`（7 个章节、22 个知识点），`--group-by tag` 按词表顺序分组。
- 渲染：5 个模板 `templates/{student,answers,teacher,sheet,card}.tex.j2` + 公共 `_preamble.tex.j2` + `_answer_block.tex.j2`（sheet/card 答案页的分步解析宏）+ `_figures.tex.j2`（插图宏）；公共导言区已加载 `ctexart/amsmath/amssymb/graphicx/tcolorbox(含 breakable)/needspace/fancyhdr/enumitem`。
- CLI：`python -m ocrmath {pack,build,list,validate,add,ocr}`；`pack` 一次出三份并写 `out/<name>/manifest.json`。
- OCR：`ingest/local.py`（pix2tex 公式级）+ `ingest/cloud.py`（占位）。pix2tex 模型权重已下载到 `.venv/Lib/site-packages/pix2tex/model/checkpoints`，离线可用。
- 质量：`python -m ocrmath validate --strict` 0 错 0 警；`python -m unittest discover -s tests` **102 个测试全过**；`pack --strict` 编译通过（student 2 页 / answers 3 页 / teacher 4 页）；`python scripts/gate.py all` 一条命令跑完两档（含插图 fixture 的真编译）。
- 审计修复（2026-10-20）：`AUDIT.md` 里 14 条问题 + 1 条工程补充已全部处理，逐条对照见 `AUDIT.md` 第一之二节和第九节。CI 也已落地（同日），审计项全部清零。

## 关键设计决定（别改回去）

1. **内容与排版分离**：题目只存 LaTeX 片段，版式全在模板里；出问题先改模板，不动题库。
2. **三份文档共用一套编号**：`pack` 里 student 用 `--group-by tag`，answers/teacher 强制 `group_by="none"`——避免分组标题在参考册里把版面切碎、出现孤标题。
3. **不生成内容**：答案/解析/易错点全部来自题库；模型不补答案、不猜条件。
4. **教师版详解框可跨页**（tcolorbox `breakable`），易错点、讲评放在框外并各自 `\needspace`，防止标题落单。
5. **学生版没有草稿区和答案**：`student` 模板忽略 `workspace_mm`（会给一次提示），这是老师的要求，不是 bug。
6. **`add` 是纯文本追加，不重写 YAML**：不引入 `ruamel.yaml` 这类依赖，用「定位列表项缩进 + 文本拼接」保住注释和未知字段。改这里之前先看 `tests/test_store.py::AppendProblemTests`。
7. **不认识的参数明确告警，不静默忽略**：`TEMPLATE_OPTIONS` 是「模板 → 真正会读的参数」的唯一事实来源，加参数时三处要同步（`_parser` 的 `add_argument`、模板里的 `cfg.*`、`TEMPLATE_OPTIONS`）。
8. **显式 `--ids` 不再二次过滤**：点名要的题不被 `--tags`/`--difficulty` 清空，也不被 `--seed` 打乱；只有 `--limit` 仍生效。

## 常用命令

```powershell
$env:PYTHONPATH = "src;.venv\Lib\site-packages"   # 没 pip install -e . 时
python -m ocrmath pack --name demo --title "高一数学 周末练习" --subtitle "函数、三角、数列与概率" --group-by tag --strict
python -m ocrmath validate --strict
python -m unittest discover -s tests -v
python .tmp\preview.py out\demo\student.pdf out\preview\demo-student   # PDF → PNG 预览
```

`--root` 现在可以不写：会从当前目录向上找 `data/taxonomy.yaml`，所以在 `src/`、`out/` 里跑也一样；换到别的机器上直接用 `scripts/build.ps1 <参数>` 也行（它自己处理 `PYTHONPATH` 和 `TMP`）。

> 相对路径的 `PYTHONPATH`（上面那行就是）只对**当前目录**成立。`scripts/gate.py` 与 `scripts/ci_latex_gate.py` 的 `_env()` 会把每一项 `Path.resolve()` 成绝对路径再交给子进程，所以在仓库根目录跑 gate 用相对写法也安全（插图 fixture 会把 cwd 换到临时目录，相对项在那边会失效，症状是子进程 `ModuleNotFoundError: No module named 'yaml'`）。自己写脚本时会 `cd` 到别处的，同样要先绝对化。

> **待办清单已独立到 `TODO.md`**（含「只能人工做」的阻塞项与技术债）。这一节只保留路线图视角的说明；具体勾选进度看 `TODO.md`，别再往这里加条目。

## 下一步（按优先级）

1. **真实题目入库**：先把老师最近要布置的 10–20 道题录进 `data/problems/`，验证题型覆盖（解答题、多小问、含图）。这是唯一能暴露新问题的一步，优先做。
2. ~~**含图题**~~ ✅ 已完成（2026-10-20）：`figures: list[str]`（相对 `data/`）+ `figure_width`（0.1–1.0，默认 0.6）；`templates/_figures.tex.j2` 里统一出 `\includegraphics[width=..\linewidth,keepaspectratio]`；图在编译前被拷进 `out/.build/<名字>/`，`main.tex` 只写文件名；`validate` 查文件是否存在、`build` 缺图直接失败指名文件。fixture 见 `tests/fixtures/figures/`，CI 慢速档会单独跑一轮并确认日志里真读到了 png。
3. **多小问**：题干里的 `(1)(2)` 现在是纯文本；若需要自动编号，加 `parts` 字段并在模板里排。
4. **答题横线 / 网格**：学生卷可选 `--ruled` 或每题 `answer_lines: 3`，对应模板里画 `\dotfill` 或方格。
5. **答案册单独装订**：`pack` 加 `--booklet`，answers 用 A5 或双栏、可对折。
6. **题库导入**：从 Markdown/Word 粘贴格式批量转 YAML（比 OCR 更实用，因为题源是老师自己找的）。
7. ~~**CI**~~ ✅ 已完成（2026-10-20）：`.github/workflows/quick.yml`（push/PR，不装 TeX）+ `latex.yml`（每日 02:00 + 手动，真编 PDF）。本地复现用 `python scripts/gate.py fast|slow|all`。**已验证**（2026-10-24）：`latex` workflow 在 GitHub runner 上手动 `workflow_dispatch` 跑通，Debian TeX 包清单够用（含此前补的 pgf/tikz）。以后改模板或加宏包仍要留意缺包，失败时 workflow 会上传 `out/.build/**/main.log` 作 artifact。

> 加新字段/新参数的顺序（踩过坑）：改 `Problem` → 改 `validate` → 改模板 → 在 `TEMPLATE_OPTIONS` 登记该参数归哪个模板 → 补 `tests/` → 跑 `validate --strict` 与全模板 `build`。漏掉 `TEMPLATE_OPTIONS` 那步，新参数就会静默无效（这正是审计问题 8）。

## 环境与坑（新会话必读）

- Windows + DSH 沙箱 `workspace-write`：`tempfile.mkdtemp()` 的 0o700 目录会触发 ACL 拒绝，pip 安装/venv 会失败。绕法：`TMP`/`TEMP` 指到 `D:\workspace\ocr-math\.tmp`，用 `.tmp\pipshim.py`（monkeypatch `os.mkdir` 为 0o777 后再调 pip）装到 `.venv\Lib\site-packages`。
- Git push 走 SSH（`git@github.com:utada1stlove/ocr-math.git`）：直接 `git ls-remote`/`git push` 在沙箱里会报 `sh.exe ... couldn't create signal pipe, Win32 error 5`，需要用更宽的沙箱权限重试同一条命令。
- LaTeX 坑：`\noindent` 后紧跟中文会被并进控制序列（`\noindent已知` → Undefined control sequence），必须留空格；Jinja 里 `{#` 是注释，别在模板写 `{#1}`；tcolorbox 的 `dash pattern` 键不存在（用实线框）。
- **临时题库必须自带 `templates/`**：`render()` 只认 `<root>/templates`，不会回落到仓库里的模板。想用 `.tmp/xxx` 当 `--root` 试东西，先把 `templates/` 复制进去，否则报 `'sheet.tex.j2' not found in search path`。
- LaTeX 编译中间产物在 **`out/.build/<名字>/`**（不是 `out/<包名>/.build/`），要看 `main.log` 里有没有 `Overfull`/`Missing character` 去那里翻。
- **插图 fixture 要像个项目根**：`tests/fixtures/figures/` 下必须有 `data/taxonomy.yaml` + `data/problems/` + `data/figs/`，因为 `--root` 认的是「有 data/taxonomy.yaml 的目录」；只放 problems/ 会报「找不到知识点词表」。
- `python -m unittest` 也需要把 `.venv\Lib\site-packages` 放进 `PYTHONPATH`，否则 `ModuleNotFoundError: No module named 'yaml'`。
- YAML 里导数撇号写两个：`$f''(x)$` 表示 `$f'(x)$`。
- 选选项里的分数用 `\frac`，`\dfrac` 会把行撑高、A/B/C/D 对不齐。

## 仓库约定

- 不上传：`out/`、`.venv/`、`.tmp/`、`.cache/`（已写进 `.gitignore`）；`ocr-math.txt` 是会话附件副本，暂不入库。
- `AUDIT.md` 是审计报告兼修复台账（第一之二节是「修到哪了」，第九节是验收证据），别删；新发现的问题往里面加，修完把状态改成 ✅。
- `.gitattributes` 固定 LF（`*.ps1`/`*.bat` 保留 CRLF），避免 Windows 上编辑后整文件 diff。
- 提交信息用中文或英文都行，建议 `feat: ...` / `fix: ...` 前缀。
