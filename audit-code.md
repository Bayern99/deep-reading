# WSJ 深读 · Editorial 能力代码审计

日期：2026-10-13。范围：`2026-10-12/cases/` 全部构建脚本、`skills/deep-read/`、`skills/translate/`、`wsj-deep-read/render/`。
方法：逐文件读取实现，区分"代码实现的通用逻辑"与"针对单篇文章手写的内容"。

---

## 核心结论（一句话）

**代码库里从未存在过 Editorial Intelligence。** 所有的"内容理解/编辑决策"（关键数字识别、时间线抽取、引语选择、图表数据提取、组件选择与排布）都是 agent（Juno）在写 `build_r3_1.py` 等脚本时**手工完成**的，决策固化在针对单篇文章的命令式代码里。代码只实现了**渲染原语**（把给定的数据变成 HTML），没有实现任何从正文自动派生编辑内容或做组件选择的逻辑。

---

## 一、

### 1. 渲染原语（build_r3.py / build_r2.py / build_prototype.py）
- 段落/句子切分：`cn_paras`、`en_paras`、`cn_sents`、`en_sents`（纯正则切分，无语义）。
- HTML 组件生成器：`stat_strip`、`timeline`、`pullquote`、`claimevidence`、`bargraph`、`compare_duel`、`em`、`beat`、`P`、`P_html`、`kicker`、`head`。
- **性质**：全部是"给定数据 → HTML"的呈现函数。输入的每一个数字、每一句话、每一个归因都是调用者手写的。
- `em(cn, nums, hot=())`（正文数字高亮）：`nums` 列表由调用者显式传入，无自动数字识别。

### 2. 12%→6% 柱状图（成功）
- `bargraph()`：手写两个数据点（12%、6%）渲染为等比 CSS 柱。数据来自正文第 9 段，由人工识别后硬编码。**成功但不可复用**——换一篇文章就要重写数据。

### 3. PDF 图片裁取（成功，属视觉资产抢救）
- `chart-ev-ports.png`：从原 PDF B1 页直接裁取矢量图嵌入，**没有重绘**（无月度原始数据）。属一次性人工操作，非流程。

### 4. 当前 render/（2026-10-13 新建）
- `components.py` / `article.py` / `issue.py` / `build.py`：类型感知渲染（article/opinion/brief/letter/data_table/photo_caption）、目录/上下篇/进度条、data_table 的 `|` 解析、base64 图片嵌入。
- **性质**：与历史脚本相同的模式——渲染器 + 策展数据（`modules.json`），无新增的内容理解能力。

### 5. 翻译管线（skills/translate）
- baoyu 式流程：术语表先行（`glossary.json` 511 条）、TranslateGemma 引擎、`translate-gemma.py` 脚本、Juno QA。属**生产流程**实现，非 Editorial Intelligence。

---

## 二、（看起来像智能，实为人工）

`build_r3_1.py` 的 `build_e1005()` / `build_e3002()` 是铁证：

| 组件 | 数据来源 | 证据 |
|---|---|---|
| 4 个关键数字 | 手写元组（中英标签/数值/注释） | `stat_strip([...])` 硬编码 |
| 7 条时间线 | 手工挑选的句子 | `cn_sents(cp[21])[0]`——段落号和句子号都是人工指定的 |
| 主张/现实对照 | 手写两句话 | `claimevidence('胡塞武装的情况已经得到控制。',...)` |
| 引语 | 手写引文 + 署名 | `pullquote('任何军事行动……', '克里斯蒂安·库茨·乌尔里克森 / …')` |
| 柱状图数据 | 手写 | `bargraph(..., [('2025 年第三季度 · 峰值',..., '约12%',..., 100, 'verm'),...])` |
| 反差对照 | 手写 4 组 | `compare_duel(...)` 硬编码 |
| 图注 | 手写 | 每张图的 caption 逐字手写 |
| 模块位置 | 手写 | "P2 之后放关键数字、P7 之后放时间线"写在 for 循环的 if 里 |

- 仅覆盖 **2 篇文章**（E1-005、E3-002）。其余 115 条从未有过任何编辑处理。
- `01-analysis.md` / `report.md`：agent 写的 markdown 分析文档，**人可读、机器不可消费**，构建脚本从不读取它们。
- `render/modules.json`：把同一批手写策展数据搬进 JSON，换了容器，没变性质（仍只有 E1-005）。

## 三、（从未有过代码）

1. **Editorial Intelligence**：零代码。文章主题识别、事实/证据判断、引语选择、时间关系分析、图片价值判断、背景需求判断——全部发生在 agent 对话里，无持久化、无复用。
2. **Editorial Plan 数据结构**：不存在。`final.json` → HTML 之间没有任何编辑决策中间层。JSON 清单：extract-*/trans-*/merged/final/glossary——全是管线中间产物，无编辑计划。
3. **组件选择逻辑**："什么文章用什么组件"从未写成规则。`render/issue.py` 的类型分流（article→完整页、brief→紧凑条目）是第一版粗糙的类型规则，由构建 agent 即兴编写，非历史恢复。
4. **道琼斯指数图表**：从未实现。市场数据表（E1-002 等）在所有版本中都只渲染为纯表格。
5. **政治捐款信息图（E1-033）**：**在提取阶段失败**，非渲染失败。原文是带二维码 + 气泡图的信息图（"Scan this code…"），提取只抢救出文字" Michigan $12.7M; Pennsylvania $9.1M（scale markers $10M/$1M）"，视觉信息（气泡大小、二维码、完整图表）永久丢失。当前渲染为纯表格是无奈之举。
6. **时间线/关键数字自动抽取**：从未存在。
7. **系统化视觉资产流程**：不存在。只有零散的 base64 手工嵌入（`b64('b1-000.png')` 等）；`assets/` 下 25KB 的图片与文章无机器可读的映射关系。
8. **主张/现实（duel）组件**：曾作为手写组件存在，后**经设计决策删除**（2026-10-13，内容为 P5+P2 复述）——不是丢失，是主动移除。

## 四、图表个案

| 图表 | 实现方式 | 结果 |
|---|---|---|
| 12%→6% 柱状图 | `bargraph()` 手写数据 + CSS | ✅ 成功（但单篇硬编码） |
| EV 充电桩月度图 | 原 PDF 裁图嵌入 | ✅ 成功（抢救，非重绘） |
| 道琼斯/市场指数图 | 无 | ❌ 从未实现，一直是纯表格 |
| 政治捐款信息图 E1-033 | 提取阶段丢失视觉信息 | ❌ 提取失败，无可渲染之物 |

## 五、当前 render/ 相对历史实现丢失的能力

| 能力 | 历史位置 | render/ 现状 |
|---|---|---|
| 柱状图渲染（bargraph） | build_r3.py | ❌ 未移植——12%→6% 图无法复现 |
| 反差对照（compare_duel） | build_r3.py | ❌ 未移植 |
| 正文数字高亮（em） | build_r3.py | ❌ 未移植 |
| 主张/现实（claimevidence） | build_r3.py | ❌ 已删除（设计决策，非丢失） |
| 单篇任意模块排布 | build_r3_1.py 的命令式代码 | ❌ 固定位置规则替代 |
| 多图/多 figure | build_r3_1.py | ⚠️ images.json 只支持单图映射 |
| stat_strip / timeline / quote / context / figure / data_table | build_r3.py | ✅ 已移植（改名） |

## 六、对 Phase 2–5 的直接含义

1. **没有什么可"恢复"的 Editorial Intelligence**——因为从未写成代码。要的是**新建**：把 Juno 在对话里做的编辑判断（读文章→定模块→选手写数据→定位置）变成持久化的 Editorial Plan 生成流程。
2. **唯一可复用的真实资产**：渲染原语的设计模式、`modules.json` 的数据形状、E1-005/E3-002 两篇的手工策展（可作为 Editorial Plan 的**示例样本**，而非规则）。
3. **真正的断点在提取**：E1-033 证明信息图在 `pdftotext` 阶段就已丢失。AnyDoc/视觉解析要补的是这一环，不是渲染环。
4. **翻译引擎替换不影响编辑层**：翻译管线（术语表→引擎→QA）是独立的，换模型只需换 `translate-gemma.py` 对应的调用层。
