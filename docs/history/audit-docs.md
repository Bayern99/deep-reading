# WSJ 深读 · 文档审计：设计过但未实现的 Editorial 能力

> Historical assessment of earlier design work. Current capabilities and document authority are defined by [ARCHITECTURE.md](../../ARCHITECTURE.md) and [README.md](../../README.md).

审计日期：2026-10-13。范围：`2026-10-12/cases/DELIVERY_*.md`、`DESIGN_NOTE_R3.md`、
`wsj-design-exploration/design-review.md`、`site-study.md`、`~/memory/2026-10-1*.md`、
`~/workspace/skills/deep-read/`。

## 核心发现（先说结论）

**"Editorial Intelligence / Editorial Planning / Component Selection" 作为具名能力，在所有被审计文档中一次都没有出现过。**
文档里的 "editorial" 全部指编辑*设计风格*（Editorial Print / Editorial Experience / Editorial Luxury），
不是内容理解与编辑决策能力。凡是接近"编辑智能"的东西，都以三种形态存在：
① skill style-guide 里的一句话原则；② Jerry brief 里的文字要求；③ agent 对话中一次性手工执行。
**没有一条变成代码，没有一条变成持久化工件。**

---

## 1. 文档里提到过的设想（及停留层次）

| 设想 | 出处 | 形态 | 是否实现 |
|---|---|---|---|
| Component by information shape（按信息形状选组件：timeline→时间线、comparison→并置、raw numbers→附录表） | deep-read skill `style-guide.md`（2026-10-12 加入） | 一句话原则 | ❌ 无代码。生产渲染器零选择逻辑，模块只在人工写入 modules.json 时出现 |
| 按文章类型建立不同的视觉节奏（国际政治长文 / 经济数字 / 市场报道 / CEO 访谈） | R3 brief（Jerry，2026-10-12；memory 有记录） | brief 文字要求 | ❌ 原型中对 E1-005/E3-002 手工做了差异处理，未系统化 |
| 信息图形必须忠实于实际数据与统计口径 | R3 brief | brief 文字要求 | △ 手工执行过一次（12%→6% 柱状图），无管线 |
| market data as charts/diagrams（inline SVG，不用外部库） | Jerry 常设要求（2026-10-11，memory） | 文字要求 | △ 10-11 周末版实现过 inline SVG 图表；R3 重建时**丢失**，生产系统无此能力 |
| embed original PDF images where they matter + image→story mapping | Jerry 常设要求；BUILD-INSTRUCTIONS-V2.md | 文字要求 | △ pdfimages 手工恢复过一次（R3.1），无管线 |
| 跨方案可借鉴的 6 个模式（design-review.md Q5） | design-review.md（2026-10-13） | 评审建议清单 | △ 部分采纳（时间线、引语即锚点、颜色纪律）；行内信源标记、章节留白节奏未实现 |
| site-study 8 条观察（如 #6 行内信源标记、#4 TOC scrollspy） | site-study.md | 一手观察 | △ 部分采纳；#6 从未实现 |

## 2. R2/R3 的"组件规划"决策：手工、逐篇、临时的

- **R2** "去重（additive → integrated）"：E1-005 删 Key Facts、E3-002 删 Stat Row——agent 逐篇手工判断，**没有留下"何时删、何时留"的规则**。
- **R3**：E1-005 和 E3-002 的完整版式硬编码在 `build_r3_1.py` 里（哪段后插什么模块写死在代码里）。
- **证据**：生产 `render/modules.json` 至今只有 **1 篇**文章有策展模块（E1-005）——"组件规划"从未超出手工原型规模。
- **结论**：所谓组件规划 = agent 读文章 → 脑中决定 → 硬编码。没有规划工件，没有可复用的决策记录。

## 3. 成文设计核查

### 图表处理流程
- **有文字要求，无管线**。10-11 周末版有过 inline SVG 图表实现（已丢失，无代码留存）；R3.1 的 12%→6% 柱状图是手工绘制并文档化了数据纪律（"仅用正文第 10 段已有数据，等比，注'编辑绘制'"），但绘制过程不可复用。
- 当前生产系统：数据表只渲染成表格，**零图表生成能力**。

### 视觉资产管线
- **诊断过，手工执行过一次，从未建成管线**。DELIVERY_R3_1 §二 "视觉资产恢复"明确写了病因："管线只用 pdftotext 抽文本，图片从未进入管线"，然后用一张手工表格（资产→来源→处理）+ pdfimages 恢复了 3 张图。
- 当前状态：`render/images.json` 只有 1 张验证图片。图片标准（"宁缺毋滥"）立了，但"从 PDF 到图片清单"的流程不存在。

### 文章级编辑决策
- **零成文设计，零持久化工件**。编辑决策只存在于 agent 对话和硬编码构建器中。没有任何"每篇文章的 Editorial Plan"文档。

## 4. 清单（按重要性排序）

1. **Component Selection（按信息形状选组件）**——skill 里有原则，代码里零实现。这是 Editorial Intelligence 的最小可用形态，缺了它后面都免谈。
2. **按文章类型建立不同视觉节奏**（R3 brief 明确要求）——原型验证过可行，从未系统化。当前生产 116/117 篇文章用同一套模板。
3. **图表生成管线**（inline SVG + 数据口径纪律）——曾经实现过又丢失，是退化最明确的一项。
4. **视觉资产管线**（PDF 图片提取 → image→story mapping → 图片清单）——病因已确诊，手工跑过一次，无自动化。
5. **行内信源标记**（"来源：第 N 段"做成真正的行内标记，site-study #6）——观察记录，从未动手。
6. **文章级 Editorial Plan 持久化**——从未存在；这是本次重建任务的核心缺口。
7. **Q&A 编辑节奏 / 非对称构图 / 边注**（R3 brief ②）——brief 要求，原型未深入，生产无。

### 注：设计过、实现过、后被否决的（不计入上表）
- Oura 式章节留白、背景资料 Note-callout：进过 hybrid v2，被 Jerry 否决改回（折叠菜单 / AJ 尺度）。有记录，不算"未实现"。

## 5. 公平起见：已经实现并保留的

颜色纪律（橙/红分工）、引语直接引语规则、"主张与现实"模块删除、去重原则（additive→integrated）、
数据表沉底附录、背景折叠、图片"宁缺毋滥"标准、中英 1:1 铁律、构建器只做排版。这些是视觉与诚实性纪律，
落实得很好——但它们管的是"怎么画"，不管"画什么、为什么画"。后者正是缺失的 Editorial Intelligence。
