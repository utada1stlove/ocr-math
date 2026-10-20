# ocrmath 审计报告与修复计划

- 审计日期：2026-10-20
- 审计对象：`D:\workspace\ocr-math`，分支 `main`，HEAD `c161054`（`feat: 题库驱动的三份 PDF…`）
- 审计方式：通读全部源码/模板/测试/数据，并对 `validate` / `pack` / `build` / `add` / `list` 做边界探针与坏题库对照实验
- 环境：Python 3.14.7（`C:\Python314\python.exe`），TeX Live 2026（`D:\texlive\2026\bin\windows`）
- 状态：**仅审计，未改动任何代码**

> 说明：探针脚本与实验用坏题库都在 `.tmp/` 下（已被 `.gitignore` 忽略），随时可删。本文档中的行号以 `c161054` 为准。

---

## 一、总体结论

**能跑，完成度不低。** `pack` 一次出三份 PDF（student 2 页 / answers 3 页 / teacher 4 页）编译干净；`validate --strict` 0 错 0 警；15 个单元测试全过；三份 `main.log` 无 `Overfull`、`Missing character`、`LaTeX Warning`。选题、分组、模板分层、词表校验的设计方向都是对的。

**但存在一类危险缺陷：数据会静默损坏，而工具不报错。** 严重度排序如下：

| 级别 | 条目 | 一句话 |
|---|---|---|
| P0 | 1 | `answer` 字段完全不做 LaTeX 体检，未转义 `%` 会静默吞掉答案后半句 |
| P0 | 2 | `sheet --answers end` 丢掉 `steps`，只填分步解析的题答案册上是空的 |
| P1 | 3 | 全角逗号 `，` 不切分 `tags`，产生假标签、筛选失败 |
| P1 | 4 | `add` 不拦截同一输入文件内的重复 id |
| P1 | 5 | `add` 重写整个 YAML，注释与未知字段全部丢失 |
| P1 | 6 | `--limit` 负数、`--difficulty 4-2`、显式 `--ids` 被二次过滤：选题静默出错 |
| P2 | 7 | `--skip` 不校验取值，可产出空包并 exit 0 |
| P2 | 8 | `--one-per-page` 对默认模板 `sheet` 静默无效 |
| P2 | 9 | 装完后只能在仓库根目录运行；cwd 不对时假装成功 |
| P3 | 10–14 | 测试脆弱、模块无测试、页数估算偏差、文档数字不一致等 |

---

## 一之二、修复状态（本轮已完成）

审计报告是「发现问题」的快照，下面这张表记录**每个问题的处理结果**，便于回头核对哪条还欠着。逐条验证命令见文末「修复验收记录」。

| # | 问题 | 状态 | 落点 |
|---|---|---|---|
| 1 | `answer` 不做 LaTeX 体检 | ✅ 已修 | `schema.py` `validate()` 末尾对 `answer` 调 `_latex_issues` |
| 2 | `sheet/card` 答案页丢 `steps`/`pitfalls` | ✅ 已修 | 新建 `templates/_answer_block.tex.j2` 宏；`render.py` 的 `answers` 上下文补 `steps`/`pitfalls` |
| 3 | 全角逗号不切分 | ✅ 已修 | `cli._split` 用 `[,，;；]`；`schema` 的 `tags`/`pitfalls` 用同一套分隔符（`choices` 故意不切） |
| 4 | `add` 不拦截批内重复 id | ✅ 已修 | `cmd_add` 先全量查重（库内 + 批内），有冲突整批拒绝、零写入 |
| 5 | `add` 重写整个 YAML | ✅ 已修 | `store.append_problem` 改为纯文本追加；`Problem.extra` 保留未知字段 |
| 6 | 选题参数静默出错 | ✅ 已修 | `_positive_int`、`_difficulty`（含反向区间与全角连字符）、`select` 的 `ids` 短路不再二次过滤 |
| 7 | `--skip` 不校验 | ✅ 已修 | `cmd_pack` 校验取值 ∈ `PACK_KINDS`，全跳过 → exit 2 |
| 8 | 不支持的参数静默无效 | ✅ 已修 | `TEMPLATE_OPTIONS` + `_option_warnings`，stderr 明确告知哪些参数被忽略 |
| 9 | 只能在仓库根目录运行 | ✅ 已修 | `_resolve_root` 向上查找 + `importlib` 兜底（`_installed_root`）；`Taxonomy.load` 缺文件改为报错 |
| 10 | 测试写死 `len == 9` | ✅ 已修 | 改为「非空 + id 唯一」 |
| 11 | CLI/build 无测试 | ✅ 已修 | 新增 `tests/test_cli.py`（含 `_split`/`_difficulty`/`--skip`/`add` 同批重复），测试数 15 → 67 |
| 12 | 页数估算把 CJK 当宽度 1 | ✅ 已修 | `render._display_width` 用 `unicodedata.east_asian_width` |
| 13 | `preview_pdf.py` 不关文档 | ✅ 已修 | `try/finally` 里 `page.close()` / `doc.close()` |
| 14 | 权重体积 70MB vs 116MB | ✅ 已修 | 统一为 70MB（torch 本身另计） |
| — | 无 `.gitattributes` | ✅ 已加 | 固定 LF，`*.ps1`/`*.bat` 保留 CRLF，PDF/图片标 binary |
| — | 无 CI | ✅ 已加（分两档） | `.github/workflows/quick.yml`（push/PR，不装 TeX）+ `.github/workflows/latex.yml`（夜间/手动，真编 PDF）；本地同一条命令 `python scripts/gate.py fast\|slow` |

---

## 二、P0：会静默产出错卷子

### 1. `answer` 字段完全不做 LaTeX 体检

`Problem.validate()` 在 `src/ocrmath/schema.py:170-189` 依次检查 `statement` / `choices` / `steps` / `pitfalls` / `solution` / `hint` / `teaching`，**唯独漏了 `self.answer`**。而答案恰恰是最短、最容易手抖的字段。

复现（`.tmp/badroot2`，题库仅一道题，答案写作 `answer: 及格率 30% 的学生`）：

```
$ python -m ocrmath pack --strict ...
exit 0                                   ← 三份 PDF 全出，无任何提示
```

`out/.../answers/main.tex:41` 实际内容：

```latex
\noindent\textbf{【答案】}及格率 30% 的学生\par
```

用 pdfium 抽取 `answers.pdf` 文本：

```
【答案】及格率 30
• 别忘了乘以 100
```

`%` 之后被 LaTeX 当注释吞掉，同一答案里的易错点也被截断。**卷子印出来学生看到的就是"及格率 30"**，没有任何报错。

对照实验：把同样的文本放进 `statement` 就会被抓：

```
[警告] ... 正文中的 % 未转义，会被 LaTeX 当成注释（写成 \%）
[警告] ... 行内公式 $ 数量为奇数，编译可能失败
```

奇数个 `$` 的情况（`answer="$a \le 1"`，`.tmp/badroot`）：`validate --strict` 仍 exit 0、输出"2 题，0 个错误，0 个警告"，直到 `pack` 时才在编译期炸：

```
./main.tex:56: Missing $ inserted.
l.56 \noindent\textbf{【答案】}$a \le 1\par
```

**修法**（约 1 行）：在 `src/ocrmath/schema.py:188` 后补

```python
if self.answer:
    issues.extend(_latex_issues(self.answer, self.id, "answer"))
```

并同步修正 `README.md:147` 中"validate 会检查未转义 `%`"的说法。

### 2. `sheet --answers end` 丢掉分步解析

- `src/ocrmath/render.py:132` 构造 `answers` 列表时只传了 `{number, answer, solution}`，**没有 `steps`**。
- `templates/sheet.tex.j2:54-65` 的答案块只渲染 `item.answer` 与 `item.solution`。
- 对照 `templates/answers.tex.j2:42-51`：那边是 `{% if p.steps %}…enumerate…{% elif p.solution %}`，优先分步。

复现（`.tmp/stepsdemo`，单题 `stepsonly-001`：`answer: $2$`、两条 `steps`、无 `solution`）：

```
$ python -m ocrmath build --template sheet --answers end
```

答案页文本只有：

```
参考答案与解析
1. 2
```

同一数据换 `answers` 模板则完整：

```
【答案】2
【解析】
（1） 先看个位：1 + 1 = 2。
（2） 再检查进位：本题不需要进位。
```

也就是说 `README.md:70` 推荐的"习题册 + 答案统一放最后"用法，答案册会缺掉全部解析。

为什么 `pack` 现在看不出来：现有 9 道题 `solution` **全部非空**（其中 `fx-001`、`fx-002`、`seq-001`、`prob-001` 这 4 道另有 `steps`），有 `solution` 时模板回退到 `solution`，所以暂时正常。一旦按 `PLAN.md` 第 1 步开始录真题、只填 `steps`，立刻踩中。

另外 `src/ocrmath/cli.py:110-126` 的 `_content_checks` 对 `sheet` 不检查缺解析（只对 `answers`/`teacher` 查），所以连提示都没有。

**修法**：`render.py:132` 补 `"steps": problem.steps`；`sheet.tex.j2` 改成与 `answers.tex.j2:42-51` 同构的 `{% if item.steps %}` 分支。

---

## 三、P1：中文输入必然踩到

### 3. 全角逗号不切分 `tags`

`src/ocrmath/schema.py:50`：

```python
def _as_list(value, sep=r"[;,；\n]") -> ...:
```

有中文分号 `；`，偏偏没有中文逗号 `，`。

```
tags: "函数性质，导数应用"   →   ['函数性质，导数应用']      # 一个假标签
```

CLI 侧同样：`src/ocrmath/cli.py:349` 的 `_split` 只按 `,` 切，

```
$ python -m ocrmath build --tags 函数性质，导数应用
没有题目满足筛选条件。        exit 2
```

本项目面向中文数学老师 + OCR 录入，全角逗号是输入法默认产物，命中率极高。

**注意（待决策 A）**：`choices` 也走同一个 `_as_list`，但 `"A. 1，2"` 这种选项内部本身就带全角逗号，直接切会碎选项。建议只给 `tags` 加分隔符。

### 4. `add` 不拦截同一输入文件内的重复 id

`src/ocrmath/cli.py:292-299`：`existing_ids` 在循环外算一次，循环内只读不写。

喂一个含两条 `id: dup-9` 的 YAML：

```
exit 0
已写入 dup-9 -> ...
已写入 dup-9 -> ...
```

两条都进库。`load_problems` 的重复检测（`src/ocrmath/store.py:99-104`）只在**下次加载**时才报 `[error] id 重复出现 N 次`，也就是要等到运行 `validate` 才发现题库已脏。

**修法**：循环内补 `existing_ids.add(problem.id)`，写库前再跑一次库级重复检查。

### 5. `add` 重写整个 YAML，注释与未知字段全丢

`src/ocrmath/store.py:108-120` 的 `append_problem` 是 `safe_load` → `append` → `safe_dump` 整文件重写。

目标文件：

```yaml
# 高一函数专题：本文件按教学进度维护，请勿删注释
# 负责人：数学组

- id: keep-001
  statement: 已有题目。
  answer: $1$   # 行尾注释
  my_note: 教研组备注
```

追加一题后：

```yaml
- id: keep-001
  statement: 已有题目。
  answer: $1$
- id: new-001
  ...
  difficulty: 3
```

**三条注释全部消失**，未知字段 `my_note` 被 `to_mapping()` 丢弃，未写的题还被补上 `difficulty: 3`。`data/problems/algebra.yaml` 就有头部注释，往它里面 `add` 会直接抹掉。对"题库是唯一真源"的设计原则来说，这是数据层最该修的一条。

**建议修法**：改为「读原始文本 → 确保结尾换行 → 追加新题的 YAML 片段」，零新依赖，注释 100% 保留（待决策 B）。

### 6. 选题参数静默出错（三处）

**(a) `--limit` 负数**：`--limit -1` 会被 argparse 当成选项（报 `unrecognized arguments`），必须写 `--limit=-1`；此时 `result[:-1]`，9 题出 **8 题**、exit 0。`--limit=0` → 空列表。0 与负数都该报错。

**(b) `--difficulty` 反向区间**：`src/ocrmath/cli.py:352-362` 只校验端点各自 ∈1–5，不校验 `low <= high`。`--difficulty 4-2` → 空集，却报"没有题目满足筛选条件"，让人以为题库里真没这题。

**(c) 显式 `--ids` 被二次过滤**：`src/ocrmath/select.py:25-46` 的过滤顺序是 ids → tags → difficulty → seed → limit，点过名之后还要再过一遍：

| 调用 | 结果 |
|---|---|
| `SelectOptions(ids=["geo-001","fx-001"])` | `['geo-001', 'fx-001']` ✓ 保序 |
| 同上 + `difficulty_min=4, difficulty_max=5` | `[]` ✗ 静默清空 |
| `ids=["fx-001","fx-001"]` | `['fx-001', 'fx-001']` ✗ 重复出题 |
| 同上 + `seed=7` | `['fx-001']` ✗ seed 打乱显式顺序 |

显式点名了还被筛掉，是最反直觉的一种。建议 `ids` 非空时去重保序直接返回。

---

## 四、P2：参数语义不一致

### 7. `--skip` 不校验取值

`src/ocrmath/cli.py:167`：

```python
kinds = [kind for kind in PACK_KINDS if kind not in _split(args.skip)]
```

| 命令 | 实际结果 |
|---|---|
| `pack --skip foo` | 静默出全三份，exit 0 |
| `pack --skip student,answers,teacher` | 只有 `manifest.json`、`documents: []`、**exit 0** |
| `pack --skip student，answers`（全角） | 三份全出（同问题 3） |

空包 + exit 0 看起来像成功，是最坑的一种。

### 8. `--one-per-page` 对默认模板静默无效

`src/ocrmath/cli.py:392` 对所有模板声明了该参数，但只有 `templates/student.tex.j2:39` 读 `cfg.one_per_page`。

| 命令 | 页数 |
|---|---|
| `build --template sheet` | 2 |
| `build --template sheet --one-per-page` | **2（无变化、无警告）** |
| `build --template student` | 2 |
| `build --template student --one-per-page` | 9 ✓ |

`build` 的 `--template` 默认值正是 `sheet`，所以 `README.md:64` 的"一题一页"示例配上默认模板就是哑弹。同理 `templates/card.tex.j2` 完全不读 `--gap` / `--fill`。

**建议**：模板不支持时在 stderr 明确告警，而不是静默忽略（待决策 D）。

### 9. 装完之后只能在仓库根目录运行

- `--root` 默认 `"."`（`src/ocrmath/cli.py:379`），`build.py` / `render.py` 的模板与数据路径全部相对它解析。
- `pyproject.toml` 没有 `[tool.setuptools] package-data`，`templates/`、`data/` 不会被打进发行包。
- `src/ocrmath/store.py:38-39` 的 `Taxonomy.load` 对不存在的路径返回空对象，于是"找不到项目根"被降级成"题库是空的"。

换到别的目录实测：

```
$ python -m ocrmath list
题库为空。          ← exit 0，不是报错

$ python -m ocrmath build
没有题目满足筛选条件。   ← exit 2
```

装好后从任意目录调用会得到一个"空工具"，而不是一句"找不到 data/taxonomy.yaml"。

**建议**：`Taxonomy.load` 区分"文件不存在"（报错）与"文件为空"（允许）；`--root` 默认改为向上查找含 `data/taxonomy.yaml` 的目录，兜底用 `importlib.resources`。

---

## 五、P3：可维护性

| # | 位置 | 问题 |
|---|---|---|
| 10 | `tests/test_core.py:75` | `assertEqual(len(self.problems), 9)` —— 录第 10 道真题测试就红。应断言 id 集合或 `>=` |
| 11 | `build.py` / `cli.py` / `ingest/*` | 无任何测试，而 P0/P1 的 bug 全在这几处 |
| 12 | `src/ocrmath/render.py:19-20` | `_CHARS_PER_LINE = 42` / `_LINE_MM = 5.7` 把 CJK 当宽度 1 计，`\needspace` 估算偏小，页首孤题保护弱于预期 |
| 13 | `scripts/preview_pdf.py` | 从不 `doc.close()`（轻微泄漏） |
| 14 | `src/ocrmath/ingest/local.py:23` vs `README.md:46` / `pyproject.toml:14` | 权重体积写 70MB vs 116MB，数字不一致 |

另有：无 CI；无 `.gitattributes`（Windows 上 `*.yaml` 换行符易漂）。—— **两项均已补**：`.gitattributes` 见台账；CI 见台账与第九节 9.1。

**明确不算缺陷、不在本轮范围**：`ingest/cloud.py:34-35` 的 `NotImplementedError`（`PLAN.md` 中的待办特性）；插图支持（尚无 `graphicx`）；9 道题本身的数学正确性。

---

## 六、修复计划

每阶段结束的验收闸门一致：
`validate --strict` 0 错 0 警、`unittest` 全绿、`pack --strict` 三份 PDF 页数不变且 `main.log` 无 `Overfull` / `Missing character`。

### 阶段 0：先立回归测试

把每条 bug 写成会失败的用例，红 → 绿。新增：

- `tests/test_schema.py` — `answer` 的 `%` / 奇数 `$` 必须报警；`tags` 全角逗号切分
- `tests/test_select.py` — `ids` 去重、保序、不被 difficulty/seed 二次过滤；`limit<=0` 报错；`difficulty_min > max` 报错
- `tests/test_cli.py` — `_split`、`_difficulty`、`--skip` 校验、`cmd_add` 同批重复 id
- `tests/test_store.py` — `append_problem` 后原注释/未知字段仍在；`Taxonomy.load` 对不存在路径报错
- 改掉 `tests/test_core.py:75` 的 `len == 9`

预计 15 → 约 40 个用例。

### 阶段 1：止血（P0）

1. `schema.py` 补 `answer` 体检（1 行）+ 修 README:147
2. `render.py:132` 补 `steps`；`sheet.tex.j2` 补分步分支
3. `schema.py:50` 与 `cli.py:349` 加全角逗号（仅 `tags`）
4. `cli.py` 循环内补 `existing_ids.add`
5. `--limit` 改为 `positive_int` 类型
6. `_difficulty` 加 `low <= high` 校验
7. `select.py` 显式 `ids` 去重保序短路

### 阶段 2：数据安全

8. `append_problem` 改为文本追加，不重写整文件
9. `Problem` 加 `extra` 字段，`from_mapping` 收集未知键、`to_mapping` 原样写回（待决策 C）

### 阶段 3：参数语义一致性

10. `--one-per-page` / `--gap` / `--fill` 在不支持的模板上给出 stderr 告警；修 `README.md:64` 示例
11. `--skip` 校验取值 ∈ `PACK_KINDS`，且不允许全部 skip（exit 2）
12. `Taxonomy.load` 区分"不存在"与"为空"
13. `card` 的 `--gap`/`--fill` 同上处理

### 阶段 4：可移植性

14. `pyproject.toml` 补 `package-data`，打包 `templates/`、`data/`
15. `--root` 默认改为向上查找 + `importlib.resources` 兜底
16. `scripts/build.ps1:11` 去掉硬编码 `.venv\Lib\site-packages`

### 阶段 5：可选清理

17. `preview_pdf.py` 加 `doc.close()`
18. `render.py:19-20` 改 CJK 感知的行宽/行高估算
19. 统一 70MB / 116MB 的文档数字
20. 加 `.gitattributes` 固定 LF
21. （若用 GitHub）加 CI 跑 `unittest` + `validate --strict`，跳过 TeX 编译那步

---

## 七、待决策（4 点）

| # | 决策 | 倾向 |
|---|---|---|
| A | `choices` 是否也按全角逗号切分 | **只给 `tags` 加**。`"A. 1，2"` 切了会碎选项 |
| B | `append_problem` 用纯文本追加 vs 引入 `ruamel.yaml` | **纯文本追加**，零依赖，注释 100% 保留 |
| C | 未知字段：保留 vs 报错拒绝 | **保留**（加 `extra` 字段） |
| D | `--one-per-page` / `--gap` 对不支持模板：告警 vs 实现 | **告警**，实现留到真有人要 |

---

## 八、复现附录

所有探针脚本在 `.tmp/`（已被 `.gitignore` 忽略）。常用环境准备：

```powershell
$env:PYTHONPATH="D:\workspace\ocr-math\src;D:\workspace\ocr-math\.venv\Lib\site-packages"
$env:PYTHONIOENCODING="utf-8"
cd D:\workspace\ocr-math
```

| 现象 | 复现命令 |
|---|---|
| answer 不体检 | `python -m ocrmath validate --strict`（题库中含 `answer: 占比 30%` 时仍 exit 0） |
| 静默丢字 | `python -m ocrmath pack --strict --name pct ...` 后用 `scripts/preview_pdf.py` 或 pdfium 抽文本 |
| sheet 丢 steps | `python -m ocrmath build --template sheet --answers end --root .tmp/stepsdemo` |
| 全角逗号 | `python -m ocrmath build --tags 函数性质，导数应用` |
| --limit 负数 | `python -m ocrmath build --limit=-1` |
| 反向难度 | `python -m ocrmath build --difficulty 4-2` |
| 空包假成功 | `python -m ocrmath pack --skip student,answers,teacher` |
| one-per-page 哑弹 | `python -m ocrmath build --template sheet --one-per-page` |
| 错误 cwd | 在任意其他目录执行 `python -m ocrmath list` |

---

## 九、修复验收记录

这一段是**修完之后**的实测证据，与上面「修复前」的复现表一一对应。环境与第八节相同，另加 TeX Live：

```powershell
$env:PATH="$env:PATH;D:\texlive\2026\bin\windows"
```

| # | 修复后行为 | 实测 |
|---|---|---|
| 1 | `answer` 里的 `%` / 奇数 `$` 现在会报 warning | `validate` 对 `answer: $a \le 1`（缺右 `$`）输出 `[警告] … 行内公式 $ 数量为奇数`，`--strict` 下 exit 1 |
| 2 | `sheet --answers end` 的答案页出现分步解析 | `build --template sheet --answers end --ids fx-001` 生成的 `main.tex` 含 `【解析】` + 4 条 `\item` + `【易错点】` 2 条；PDF 2 页 |
| 3 | 全角逗号可切分 | `tags: "函数性质，导数应用"` → 2 个 tag（`tests/test_schema.py`）；`--tags a，b` 同样生效 |
| 4 | 批内重复 id 整批拒绝 | `add` 同一文件两个 `d-1` → exit 1，`data/problems/inbox.yaml` **未被创建** |
| 5 | 追加写回不丢注释 | `tests/test_store.py::AppendProblemTests` —— 文件头注释、行尾注释、`my_note` 未知字段全部保留 |
| 6 | 选题参数报错 | `--limit 0` / `--limit -1` / `--difficulty 4-2` / `--difficulty abc` 全部 exit 2 且给出中文原因；`--difficulty 1－3`（全角）可用 |
| 7 | `--skip` 校验 | `--skip foo` → `不认识这些值：foo`，exit 2；三份全跳过 → `至少要留一份`，exit 2 |
| 8 | 无效参数告警 | `sheet --one-per-page` → `[提示] --one-per-page 对 sheet（习题册）模板无效，已忽略`；`card --gap 9 --fill` 各自告警；`pack --one-per-page` 不刷假警告（学生卷真的会读它） |
| 9 | cwd 无关 | 在 `out/`、`src/` 内执行 `list` 均找到根；在 `C:\Windows` 下执行 → `错误：找不到知识点词表 …`，exit 2 |
| 10–14 | 测试 / 估算 / 泄漏 / 数字 | `unittest` 15 → **67 个用例全过**；`_display_width("汉字") == 4`；预览脚本 finally 关闭；70MB 统一 |

**阶段闸门（每阶段跑一遍，最后一轮结果）**

```
python -m unittest discover -s tests          → Ran 67 tests, OK
python -m ocrmath validate --strict           → 9 题，0 个错误，0 个警告，0 题缺解析，exit 0
python -m ocrmath pack --group-by tag --strict → student 2 页 / answers 3 页 / teacher 4 页，exit 0
五模板 build 回归（sheet/card/student/answers/teacher + inline + fill）
                                              → 全部 exit 0，main.log 中 Overfull=0 MissingChar=0 Errors=0
```

页数与修复前完全一致（student 2 / answers 3 / teacher 4），说明本轮改动没有把版面挤变形。

### 9.1 CI 两档（本轮补做）

审计里唯一没落地的项是 CI。落地时把它拆成两档，理由是两边成本差一个数量级：

| 档位 | 触发 | 耗时 | 内容 | 为什么这么切 |
|---|---|---|---|---|
| 快速 | push / PR | < 1 分钟 | 单测（落地时 67 个，现 102 个）+ `validate --strict` + 五套模板 Jinja 渲染冒烟 | 不需要 TeX，覆盖审计 12 个逻辑修复中的绝大多数；每次提交都拦得住 |
| 慢速 | 每日 02:00 + 手动 | ~10 分钟 | 五模板真编译 + `main.log` 机检（Overfull / Missing character / `!`）+ `pack --strict` 页数核对 | 需要 xelatex + ctex + 中文字体（约 1–2GB），只有它抓得住版面回归 |

快速档刻意**不跑 `pack`**：`pack` 会调 latexmk 编 PDF，没有 TeX Live 必然 exit 1，属于慢速档的职责。快速档改成直接调 `render()`，在 `StrictUndefined` 下把五套模板各渲染一遍——上下文少一个变量就红，正好覆盖审计问题 2（`_answer_block` 宏要拿到 `steps`/`pitfalls`）。

**实测（本机，2026-10-20）**

```
python scripts/gate.py fast   → exit 0（102 tests OK / 9 题 0 错 0 警 / 5 套模板渲染通过）
python scripts/gate.py slow   → exit 0（5 套 build exit 0、日志无 Overfull·MissingChar·错误；
                                插图 fixture 5 套 build exit 0 且日志读到 png；pack 2/3/4 页）
```

两档都做了负向验证，确认不是摆设：

- 渲染冒烟：注入 `{{ nonexistent_variable }}` → exit 1，报 `UndefinedError: 'nonexistent_variable' is undefined`；换成空题库目录 → exit 1，报「找不到模板目录」。
- 编译机检：往模板里塞 `\hbox to 1pt{\hskip 500pt}` → exit 1，报 `sheet: Overfull \hbox × 1，例：Overfull \hbox (499.0pt too wide) detected at line 28`。
- 页数核对：把期望页数改成 student 99 → exit 1，报 `student 页数 2，期望 99（版面可能漂了）`。
- 日志正则本身也单测过：干净日志三项全 0，混入 Overfull / Missing character / `!` 的日志三项各命中 1。

`EXPECTED_PAGES = {"student": 2, "answers": 3, "teacher": 4}` 是写死的——改题库或改版面后要同步更新，否则慢速档会红。这是有意的：页数是版面回归最灵敏的信号。

### 9.2 能力补强（M2 第一批，2026-10-20）

审计没覆盖、但用真实题型一撞就露的两处缺口，本轮补上：

| 缺口 | 修法 | 验证 |
|---|---|---|
| 含图题无法排版（导言区没有 `graphicx`） | `Problem.figures`（相对 `data/`）+ `figure_width`；`templates/_figures.tex.j2` 统一出 `\includegraphics`；编译前把图拷进 `out/.build/<名字>/` | `tests/fixtures/figures/` 五模板真编译，日志确认读到 png；CI 慢速档每轮都跑 |
| 校验只认 `%` 和 `$`，`&` `#` 数学模式外的 `_` 全放过 | `_latex_issues` 改为环境跟踪：认 `$...$`、`\(...\)`、`\[...\]`、`\begin{}...\end{}`；表格/矩阵里的 `&`、数学环境里的 `_` 不误报 | `tests/test_schema.py::LaTeXSpecialCharTests` 9 个用例 |

另两处顺手修的：

- **列表写法里的全角逗号**：`tags: [函数性质，导数应用]`（YAML list）以前不切分，整个串变成一个 tag，`validate` 报「知识点不在词表中」——看起来像词表漏了条目，实则笔误。现在 `_as_list(..., split_items=True)` 对 tags/pitfalls 生效；**choices 明确不开**（`A. 1，2` 里的逗号属于选项内容，审计决策 A 不变）。
- **`}` 多余时的处理**：原来 `break` 掉整段扫描，后面的 `%`、`$` 检查全部跳过；现在 `depth = 0` 继续扫，剩下的问题仍会报出来。

**为何没动真实题库**：本轮加的是能力，不是内容。`data/problems/` 仍是 9 道示例题——页数基线 2/3/4 页因此保持不变，`ci_pack_check.py` 的 `EXPECTED_PAGES` 不用改。真实题目要老师提供素材，属于下一轮的事（`PLAN.md` 下一步第 1 条）。

**回归**：`python scripts/gate.py all` → exit 0；`unittest` 67 → **102** 个用例全过。


