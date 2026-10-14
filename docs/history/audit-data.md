# 数据审计：WSJ 深读项目的 Editorial 相关数据

> Historical input-data assessment. Preserve source findings; current editorial plans and artifacts are described in [ARCHITECTURE.md](../../ARCHITECTURE.md).

审计日期：2026-10-13。范围：`2026-10-12/` 下 final.json、merged.json、extract-E*.json、trans-T*.json、report.md、glossary.json、01-analysis.md、ref-study/，以及生产用的 `wsj-design-exploration/article-e1005.json`。

---

## 核心结论

1. **final.json 里唯一的"编辑元数据"是 `context_cn` + `context_attr`**（12/117 篇有）。它是翻译/QA 阶段人工（agent）判断 condensed 的背景摘要，不是提取产物。
2. **数据层没有任何文章级编辑计划、组件规划、图表数据结构**。组件决策只存在于构建脚本的硬编码（build_r3_1.py）和 agent 对话里，从未持久化为数据——直到今天才收进 `render/modules.json`。
3. **道琼斯图表（E3-014）和政治捐款信息图（E1-033）的视觉数据在提取阶段就丢失了**：pdftotext 只抓到图表的描述文字，52 周 OHLC 序列、各州数值、二维码从未被捕获。body_cn 为空。
4. **article-e1005.json 的时间线/关键数字/引语，最早来源是 build_r3_1.py 的手写 Python**（10-12 晚 R3 构建时 agent 的编辑判断），不是任何结构化数据源。

---

## 一、final.json 的编辑元数据（除正文外）

| 字段 | 覆盖 | 来源 | 性质 |
|---|---|---|---|
| `context_cn` | 12/117（article 10 + opinion 2） | 翻译终稿阶段新增（trans-T*-draft 无，trans-T* 有） | **编辑判断**：从正文 condensed 的背景摘要 |
| `context_attr` | 38/117（"原文有"12 / "无"26） | 同上 | **编辑判断**：标记原文是否有背景材料；"原文有"的 12 篇 = 恰好有 context_cn 的 12 篇 |
| `terms` | 大部分 | glossary.json（511 条冻结表）的按篇子集 | 半机械：术语表人工冻结，子集按篇注入 |
| `turn_to` | 8/38 article | 版面提取（"转 A7 版"） | **机械**：报纸转版标记 |
| `merged_from` | 3/38 | merge.py | **机械**：合并溯源 |
| `title_cn/dek_cn/body_cn` | 全 | TranslateGemma + QA 修订 | 机器翻译 + 人工修订（trans-T2-revisions.json 存 63 条 [chunk,字段,旧,新] 修订） |
| `priority/type/page/section` | 全 | 提取阶段 | 机械为主（P1/P2/P3 分级有模型参与，见 01-analysis.md） |

`context_cn` 实例（E1-005）："王储 2015 年主导沙特介入也门内战……沙特财政部预计 2026 年 GDP 将收缩 3.6%。"——所有事实均可在 body_en 中找到对应句，是**编辑 condensed**，不是原文独立边栏。

## 二、文章级编辑计划 / 组件规划 / 图表数据：

数据层**不存在**以下任何结构：
- ❌ Editorial Plan（每篇文章的编辑计划）
- ❌ Component Selection（组件选择记录）
- ❌ 图表数据结构（chart data series）
- ❌ Key Figures / Timeline 的结构化策展数据（在 final.json 之前）

实际存在过的相关物（均非数据层）：
- `01-analysis.md`：**整期**主题分析（7 条核心线）+ 翻译档位指导，不是 per-article 计划。
- `ref-study/`：UI 组件研究报告（assistant-ui / chatkit / apps-sdk）——设计研究，不是内容规划。
- `build_r3.py` / `build_r3_1.py`：组件决策以**硬编码 Python** 存在（只覆盖 E1-005、E3-002 等少数文章）。
- `interior-prototype-delivery.zip`：原型 HTML + 截图，无数据。
- `trans-T2-notes.json`：QA 批注（翻译质量），不是编辑计划。

**结论**："Editorial Intelligence / Planning / Component Selection" 在数据层从未实现过。存在的是：构建脚本里的个案硬编码 + agent 对话中的临时判断。

## 三、道琼斯图表与政治捐款信息图：数据层原始记录

### E3-014「道琼斯工业平均指数 / 标准普尔 500 指数」（data_table，B5 版）
- `body_en`（732 字符）：**图表描述文字**，不是图表数据——
`"Dow Jones Industrial Average | 51654.95, up 477.99, or 0.93% last week | High, low, open and close for each of the past 52 weeks | Trailing P/E ratio 21.03; …"`
只有当周收盘/涨跌/P/E 等标注值；**52 周 OHLC 序列从未被提取**。
- `body_cn`：空（数据表未翻译）。
- raw.txt（pdftotext）只有同样的描述文字（分栏交错）；图表的视觉数据在提取阶段即丢失，从未恢复。
- 无任何构建器特殊处理过它；当前生产将其渲染为通用数据表。

### E1-033「推动新左翼势力崛起的捐助者」（data_table，A6 版）
- `body_en`（568 字符）：导语 + **仅 2 个州**的数据点（Michigan $12.7M；Pennsylvania $9.1M；scale markers $10M/$1M）+ 注（24 个进步派 PAC，2025-01-01 至 10-07）+ 来源 AdImpact。
- 这是一张**州级地图信息图**（含二维码 "Scan this code"）——其余各州数值、地图视觉、二维码**从未被捕获**。
- `body_cn`：空；但 `dek_cn` 已译（"各个进步派团体在每个州和华盛顿特区投入了多少资金？"）；`terms` 含 AdImpact/PAC。
- raw.txt 只有标题/导语/比例尺/Michigan 数值（分栏交错）；地图数据丢失。
- 无构建器特殊处理；当前生产渲染为通用数据表（信息大幅缩水）。

**共同根因**：pdftotext 只能提取文本层；图表/信息图的视觉数据层在 `raw.txt` 这一步就丢失，后续流程没有任何视觉解析补救。

## 四、编辑判断 vs 机械提取

**机械提取**（pdftotext + 版面解析）：
`id / page / section / title / dek / byline / body_en / turn_to`，以及 `priority / type` 的初分。

**编辑判断**（翻译/QA/构建阶段，人工或 agent）：
1. `context_cn` 的 condensed + `context_attr` 的"原文有/无"标记（12 篇）
2. 术语表冻结（511 条）与按篇 terms 子集
3. 翻译修订（trans-T2-revisions.json 63 条；trans-T2-notes.json QA 批注）
4. 构建期个案决策：E1-005 的 stats/timeline/quote 选题与 condensed、claim/evidence 配对、图片取舍（EV 照保留、特斯拉/沙特图因模糊/无信息增量被撤）——**只存在于代码与对话，未持久化**

## 五、article-e1005.json 的时间线/关键数字/引语：最早来源

- 文件创建：2026-10-12 18:17，parent agent 从 `build_r3_1.py`（R3.5 组件构建器）+ `final.json` 抽取。
- stats（4 个关键数字）/ timeline（7 条）/ pullquote：**最早来源是 `build_r3_1.py` 中的手写 Python 字面量**（10-12 晚 R3 构建）。extract/merged/report/trans 任一文件中都不存在这些结构。
- 数值本身逐字来自 final.json 正文（铁律），但**选哪 4 个数字、选哪 7 个时间点、引哪一句**是构建 agent 的编辑判断。
- timeline 的 `text_en`：2026-10-13 上午由 parent agent 从 body_en 逐句对齐补入（此前只有中文）。
- 当前正式位置：`render/modules.json`（今日生产时收录）。

---

## 分类汇总

****
- `context_cn` + `context_attr`（12 篇，翻译阶段 condensed）
- `terms` 按篇子集 + 冻结术语表（511 条）
- 翻译修订记录（trans-T2-revisions.json / trans-T2-notes.json）
- `render/modules.json`（今日收录：E1-005 的 key_figures/timeline/quote）
- `render/images.json`（今日收录：E3-002 图片清单）

****
- extract-E*.json（英文全文 + 版面元数据 + turn_to）
- raw.txt（pdftotext 原始文本，含图表描述但无视觉数据）
- report.md（117 条中文结构化底稿）
- final.json 的 title/dek/byline/body_en 层

****
- 文章级 Editorial Plan：无
- 组件选择的持久化记录（除今日 modules.json 的 E1-005 外）：无
- 图表底层数据（52 周 OHLC、各州捐款数值、二维码目标）：**在提取阶段丢失，从未恢复**
- data_table 的 body_cn（25 张表均未翻译）
- E1-033/E3-014 的任何视觉资产
