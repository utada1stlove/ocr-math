# 项目计划与状态（给下一次会话的自己）

最后更新：2026-10-20。这份文件是“下一步做什么、为什么这么做”的索引；具体用法看 `README.md`。

## 一句话目标

把数学题（自己找的题 / 自己出的题）存成 YAML 题库，一键生成**学生卷 / 答案详解 / 教师版**三份 PDF，版式可调、题号一致，不需要重复排版。

## 当前状态：M1 已完成，可以日常用了

- 数据层：`data/problems/*.yaml`（9 道示例题：fx-001/002/003、tri-001、seq-001、geo-001/002、prob-001、ineq-001），字段 `statement/choices/answer/solution/steps/pitfalls/hint/teaching/tags/difficulty/workspace_mm/source`，中英文键名都认。
- 词表：`data/taxonomy.yaml`（7 个章节、22 个知识点），`--group-by tag` 按词表顺序分组。
- 渲染：5 个模板 `templates/{student,answers,teacher,sheet,card}.tex.j2` + 公共 `_preamble.tex.j2`；公共导言区已加载 `ctexart/amsmath/amssymb/tcolorbox(含 breakable)/needspace/fancyhdr/enumitem`。
- CLI：`python -m ocrmath {pack,build,list,validate,add,ocr}`；`pack` 一次出三份并写 `out/<name>/manifest.json`。
- OCR：`ingest/local.py`（pix2tex 公式级）+ `ingest/cloud.py`（占位）。pix2tex 模型权重已下载到 `.venv/Lib/site-packages/pix2tex/model/checkpoints`，离线可用。
- 质量：`python -m ocrmath validate --strict` 0 错 0 警；`python -m unittest discover -s tests` 15 个测试全过；`pack --strict` 编译通过（student 2 页 / answers 3 页 / teacher 4 页）。

## 关键设计决定（别改回去）

1. **内容与排版分离**：题目只存 LaTeX 片段，版式全在模板里；出问题先改模板，不动题库。
2. **三份文档共用一套编号**：`pack` 里 student 用 `--group-by tag`，answers/teacher 强制 `group_by="none"`——避免分组标题在参考册里把版面切碎、出现孤标题。
3. **不生成内容**：答案/解析/易错点全部来自题库；模型不补答案、不猜条件。
4. **教师版详解框可跨页**（tcolorbox `breakable`），易错点、讲评放在框外并各自 `\needspace`，防止标题落单。
5. **学生版没有草稿区和答案**：`student` 模板忽略 `workspace_mm`（会给一次提示），这是老师的要求，不是 bug。

## 常用命令

```powershell
$env:PYTHONPATH = "src;.venv\Lib\site-packages"   # 没 pip install -e . 时
python -m ocrmath pack --name demo --title "高一数学 周末练习" --subtitle "函数、三角、数列与概率" --group-by tag --strict
python -m ocrmath validate --strict
python -m unittest discover -s tests -v
python .tmp\preview.py out\demo\student.pdf out\preview\demo-student   # PDF → PNG 预览
```

## 下一步（按优先级）

1. **真实题目入库**：先把老师最近要布置的 10–20 道题录进 `data/problems/`，验证题型覆盖（解答题、多小问、含图）。
2. **含图题**：`Problem` 加 `figures: list[str]`（相对 `data/` 的图片路径），模板里 `\includegraphics`；`validate` 检查文件存在。
3. **多小问**：题干里的 `(1)(2)` 现在是纯文本；若需要自动编号，加 `parts` 字段并在模板里排。
4. **答题横线 / 网格**：学生卷可选 `--ruled` 或每题 `answer_lines: 3`，对应模板里画 `\dotfill` 或方格。
5. **答案册单独装订**：`pack` 加 `--booklet`，answers 用 A5 或双栏、可对折。
6. **题库导入**：从 Markdown/Word 粘贴格式批量转 YAML（比 OCR 更实用，因为题源是老师自己找的）。
7. **CI**：GitHub Actions 里跑 `validate` + `unittest`（不装 TeX，编译测试放本地）。

## 环境与坑（新会话必读）

- Windows + DSH 沙箱 `workspace-write`：`tempfile.mkdtemp()` 的 0o700 目录会触发 ACL 拒绝，pip 安装/venv 会失败。绕法：`TMP`/`TEMP` 指到 `D:\workspace\ocr-math\.tmp`，用 `.tmp\pipshim.py`（monkeypatch `os.mkdir` 为 0o777 后再调 pip）装到 `.venv\Lib\site-packages`。
- Git push 走 SSH（`git@github.com:utada1stlove/ocr-math.git`）：直接 `git ls-remote`/`git push` 在沙箱里会报 `sh.exe ... couldn't create signal pipe, Win32 error 5`，需要用更宽的沙箱权限重试同一条命令。
- LaTeX 坑：`\noindent` 后紧跟中文会被并进控制序列（`\noindent已知` → Undefined control sequence），必须留空格；Jinja 里 `{#` 是注释，别在模板写 `{#1}`；tcolorbox 的 `dash pattern` 键不存在（用实线框）。
- YAML 里导数撇号写两个：`$f''(x)$` 表示 `$f'(x)$`。
- 选选项里的分数用 `\frac`，`\dfrac` 会把行撑高、A/B/C/D 对不齐。

## 仓库约定

- 不上传：`out/`、`.venv/`、`.tmp/`、`.cache/`（已写进 `.gitignore`）；`ocr-math.txt` 是会话附件副本，暂不入库。
- 提交信息用中文或英文都行，建议 `feat: ...` / `fix: ...` 前缀。
