# ocrmath

数学题 → 结构化题库 → LaTeX → PDF。

一句话：把题目（手工敲、OCR 识、或从别处粘）存进 YAML 题库，然后用一条命令生成**学生卷 / 答案详解 / 教师版**三份 PDF，版式、间距、留白、答案放哪儿都由参数控制，不满意就改参数重出一遍，不用动题目数据。

## 设计原则

- **内容与排版分离**：题目里只存正文 + 行内公式（LaTeX 片段），`\documentclass`、页边距、页眉页脚全在模板里。换版式不动数据。
- **题库是唯一真源**：学生卷、答案详解、教师版都是同一份数据的查询结果 + 不同模板，三份文档题号一致、顺序一致，不存在「复制一份再改」的副本。
- **不让模型补题**：识别环节只做「图 → 文字/公式」，缺的条件、错的符号由人核对，模型不替你想「这题应该问什么」。答案与解析也只来自题库，不现场生成。
- **可插拔**：OCR 引擎是接口（本地/云端可换），模板是目录下的 Jinja2 文件（想改版式直接改 `.tex.j2`）。

## 三种产物

| 模板 | 内容 | 给谁 |
| --- | --- | --- |
| `student` | 只有题目（选择题带选项），无草稿区、无答案 | 直接发给学生 |
| `answers` | 编号 + 答案框 + 详解（分步、易错点），默认不重复题干 | 学生自批 / 家长对照 |
| `teacher` | 题干 + 答案 + 思路 + 详解 + 易错点 + 讲评建议 | 老师备课与讲评 |

`pack` 一次生成三份，并写 `manifest.json`（题目清单、每份页数、警告）。

## 目录结构

```
data/taxonomy.yaml          知识点受控词表（分组 + 组内细目）
data/problems/*.yaml        题库（一题一条，可拆成多个文件）
templates/student.tex.j2    学生卷（只有题目）
templates/answers.tex.j2    答案详解
templates/teacher.tex.j2    教师版
templates/sheet.tex.j2      习题册（题目 + 可选留白/答案）
templates/card.tex.j2       单题卡（一页一题或几题，可带草稿框）
templates/_preamble.tex.j2  公共导言区（页面/字体/宏）
src/ocrmath/                代码
scripts/preview_pdf.py      PDF 每页渲染成 PNG，方便肉眼检查
scripts/build.ps1           Windows 包装脚本（自动设 PYTHONPATH/临时目录）
out/                        产物（PDF / .tex / .build 中间文件，已被 git 忽略）
```

## 环境要求

- Python 3.10+（本项目在 3.14 上验证）
- TeX Live（或 MiKTeX），需要 `xelatex` 与 `latexmk` 在 PATH 中；中文排版用 `ctexart`
- 可选：`pypdfium2`（把 PDF 转 PNG 预览）
- 可选：`pix2tex` + PyTorch（本地公式 OCR）

安装：

```powershell
pip install -e .
pip install pypdfium2          # 预览用
pip install "pix2tex>=0.1.4" "transformers<5"   # 本地 OCR（会自动拉 torch）
```

## 快速上手

```powershell
# 一次出三份：学生卷 + 答案详解 + 教师版，产物在 out/demo/
python -m ocrmath pack --name demo --title "高一数学 周末练习" `
    --subtitle "函数、三角、数列与概率" --group-by tag

# 只给学生卷（学生卷默认按知识点分组；--one-per-page 是「一题一页」）
python -m ocrmath pack --name demo --title "高一数学 周末练习" --skip answers,teacher --one-per-page

# 看看题库里有什么
python -m ocrmath list

# 出习题册（题目 + 每题 30mm 草稿留白，答案统一放最后）
python -m ocrmath build --title "高一数学 周末练习" --group-by tag --answers end --gap 8 --workspace 30

# 只出某几题的单题卡，答案跟题后
python -m ocrmath build --template card --ids fx-001,prob-001 --workspace 45 --answers inline

# 混错题本：按知识点筛、限难度、限数量
python -m ocrmath build --tags 导数应用,概率 --difficulty 2-4 --limit 10 --seed 7
```

`pack` 产物：

```
out/demo/student.pdf   只有题目
out/demo/answers.pdf   参考答案与详解
out/demo/teacher.pdf   教师版
out/demo/manifest.json 题目清单 / 页数 / 警告
```

`build` 的产物默认在 `out/<模板>.pdf`，中间 `.tex` 在 `out/.build/<名字>/main.tex`（编译失败时直接看它）。预览：

```powershell
python scripts/preview_pdf.py out/demo/student.pdf
# 每页 PNG 在 out/demo/student/page-1.png ...
```

> 如果本机 Python 环境不是用 `pip install -e .` 装的，可以用 `scripts/build.ps1` 包装脚本：它会设置好 `PYTHONPATH`（`src` + `.venv`）和临时目录再转发参数。

## 题库格式

`data/problems/*.yaml`，一个文件可以是题目列表，也可以是 `{problems: [...]}`。字段（中英文键名都认）：

| 字段 | 说明 | 中文别名 |
| --- | --- | --- |
| `id` | 唯一编号，字母/数字/`.`/`_`/`-` | 编号 |
| `statement` | 题干，LaTeX 片段（正文 + `$...$`） | 题干 |
| `choices` | 选项列表，`\Alph*` 自动编号 | 选项 |
| `answer` | 答案（可含公式），一句话 | 答案 |
| `solution` | 解析（整段文字，适合一步到位的题） | 解析 |
| `steps` | 分步解析，每条一行；有它时详解优先用它 | 分步 / 步骤 / 解析步骤 |
| `pitfalls` | 易错点列表 | 易错点 / 易错 |
| `hint` | 思路提示（教师版显示「【思路】」） | 提示 / 思路提示 |
| `teaching` | 讲评建议（教师版显示「【讲评】」） | 教学提示 / 讲评建议 |
| `tags` | 知识点列表，建议取自 `taxonomy.yaml` | 知识点 |
| `difficulty` | 1–5 | 难度 |
| `workspace_mm` | 草稿留白高度（mm），`0` 表示不留白；`student` 模板会忽略它 | 留白 |
| `source` | 来源 | 来源 |
| `title` | 题目标题（可选，页面上不显示，仅方便检索） | 标题 |

示例（详解题）：

```yaml
- id: fx-001
  statement: 已知函数 $f(x)=x^{2}-2ax+3$ 在区间 $[1,2]$ 上单调递增，求实数 $a$ 的取值范围。
  answer: $a \le 1$
  hint: 单调递增的充要条件是导数在区间上非负，把参数分离出来更直观。
  steps:
    - '求导：$f''(x)=2x-2a$。'
    - '单调递增要求 $f''(x)\ge 0$ 在 $[1,2]$ 上恒成立，即 $a\le x$ 对一切 $x\in[1,2]$ 成立。'
    - '右端的最小值是 $1$（在 $x=1$ 处取到），因此 $a\le 1$。'
  pitfalls:
    - '把「单调递增」直接当成 $f''(x)>0$，漏掉 $a=1$ 这个端点。'
    - '只代入 $x=1$ 求 $a$，没有说明对区间内所有 $x$ 都成立。'
  teaching: 讲评时强调「恒成立」与「存在」的区别，并让学生验证端点 $a=1$ 是否可取。
  tags: [函数性质, 导数应用]
  difficulty: 2
```

> 在 YAML 单引号串里写导数的撇号要写两个：`$f''(x)$` 表示 `$f'(x)$`。

## 校验与测试

```powershell
python -m ocrmath validate           # 有错误返回 1
python -m ocrmath validate --strict  # 警告也算失败
python -m ocrmath pack --strict ...  # 缺答案/解析就不打包
```

校验会查：id 合法且不重复、题干非空、选择题至少 2 个选项、难度 1–5、留白 0–250mm、`{}` 配对、`$` 成对、未转义的 `%`（这些都会让 LaTeX 编译失败或悄悄吃掉半行字），以及 `steps`/`pitfalls`/`hint`/`teaching` 的空项与公式配对。`answer` 与题干同等对待——答案里的 `%`、奇数个 `$` 一样会被查出来（以前只查题干，答案写错要到编译时才炸）。

```powershell
python -m unittest discover -s tests -v
```

覆盖数据模型（含中文键名与详解字段）、词表、选题/分组、CLI 参数校验、追加写回、五种模板渲染（不编译 LaTeX，秒级返回）。

## 版式参数

`build`：

| 参数 | 默认 | 作用 |
| --- | --- | --- |
| `--template` | `sheet` | `sheet` 习题册 / `card` 单题卡 / `student` / `answers` / `teacher` |
| `--title` `--subtitle` | 空 | 标题与副标题 |
| `--gap` | 6 | 题与题之间的固定间距（mm） |
| `--workspace` | 40 | 每题默认草稿留白（mm），题目里的 `workspace_mm` 会覆盖它 |
| `--fill` | 关 | 用 `\vfill` 把每页平均撑满（适合少量题的一页练习） |
| `--answers` | `none` | `none` 无答案 / `end` 答案统一放最后 / `inline` 跟在题后 |
| `--one-per-page` | 关 | 每题一页 |
| `--echo` | 关 | 详解/教师版重复题干 |
| `--group-by tag` | `none` | 按知识点分组，顺序跟 `taxonomy.yaml` 一致 |
| `--show-tags` `--show-difficulty` | 关 | 题后灰字显示知识点/难度 |
| `--font-size` `--margin` | 11pt / 20 | 字号与页边距（mm） |
| `--ids` `--tags` `--tag-mode` `--difficulty` `--limit` `--seed` | — | 选题：按编号、按知识点（any/all）、按难度区间、限量、随机种子 |

`pack`：与上面同名参数含义一致（`--gap`/`--workspace`/`--one-per-page` 只作用于学生卷）；另有 `--name`（输出目录名）、`--out`（自定义输出目录）、`--group-by`、`--skip student,answers,teacher`、`--strict`。

参数校验（都是「说清楚为什么错」，不是静默忽略）：

- `--ids` / `--tags` / `--skip` 的分隔符认半角逗号、全角逗号、分号（中文输入法直接打 `，` 也可以）。`--ids` 点名的题目不再被 `--tags`/`--difficulty` 二次过滤，也不会被 `--seed` 打乱顺序。
- `--limit` 必须是正整数，`0` 和负数直接报错（以前 `--limit -1` 会静默选空）。
- `--difficulty` 支持 `2`、`2-4`，全角连字符 `2－4` 也认；区间写反（`4-2`）直接报错。
- `--skip` 只接受 `student`/`answers`/`teacher`，写错或三份全跳过都会报错退出（以前会只留一个 `manifest.json` 却报成功）。
- 某个模板不读的参数（例如 `sheet --one-per-page`、`card --gap`）会在 stderr 明确提示「对 X 模板无效，已忽略」。
- 不写 `--root` 时，会从当前目录向上找 `data/taxonomy.yaml`，所以在 `src/`、`out/` 子目录里跑命令一样能用；找不到就报错，不会假装题库是空的。

排版约定：

- 学生卷按 `--group-by` 分组（默认按知识点）；答案与教师版**连续编号、不插分组标题**，避免标题把版面切碎。
- 题块用 `\needspace` 保护「标题 + 答案框」不被拆开；详解很长时允许跨页续排，这是参考书的正常做法。
- 选项里的分数用 `\frac`（行内小号）；`\dfrac` 会把整行撑高、题号与选项对不齐。

## 知识点

两层：

1. **受控词表** `data/taxonomy.yaml`：一级是章节，二级是具体知识点，用于分组排序和 `--tags` 筛选；
2. **自由 tag**：题库里可以写词表外的知识点，只给警告、不阻断。等某个自由 tag 用顺了就提拔进词表。

## OCR

### 本地（pix2tex）

```powershell
python -m ocrmath ocr examples/formula.png                 # 打印 YAML
python -m ocrmath ocr examples/formula.png --out out/ocr.yaml
python -m ocrmath add out/ocr.yaml                          # 校验后入库
```

pix2tex 是**公式级**识别：它擅长把一行公式转成 LaTeX，不擅长整页中文题干、不擅长题号/选项版式。所以它产出的是一条 `statement` 草稿，**必须人工核对数字、上下标、正负号**——这类错误 LaTeX 不会报，只有人会看。整页题目 + 结构化字段（题干/选项/答案）建议走云端多模态模型。

### 云端（占位）

`src/ocrmath/ingest/cloud.py` 是适配器骨架：配好

```
OCRMATH_OCR_BASE_URL=...
OCRMATH_OCR_API_KEY=...
OCRMATH_OCR_MODEL=...
```

后把 `recognize()` 换成你的服务商调用（多模态模型直接返回 `{"problems": [...]}` 结构化 JSON）。注意图片会离开本机。

## 注意

- 题干里的 `%`、`#`、`&`、`_` 都是 LaTeX 特殊字符，需要转义（`\%`、`\#` 等），`validate` 会提示 `%` 的问题。
- 模板里 `\noindent` 这类控制词后面紧跟中文会被当成更长的控制序列（`\noindent已知` 直接报 Undefined control sequence），所以 `\noindent` 后要留一个空格；改模板时留意这一点。
- 中文字体走 `ctexart` 默认（Windows 上是宋体/黑体），需要别的字体加 `fontset=` 选项即可。
- 详解里一条 `steps` 不要太长（两三行以内），跨页时更容易保持「一步一段」的阅读节奏。
- `data/problems/*.yaml` 可以随便加注释和自定义字段（比如 `ocr_from`、教研备注）：`ocrmath add` 是**文本追加**，不会重写整个文件，注释和本工具不认识的键都会原样留在原处。
