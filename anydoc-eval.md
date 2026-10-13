# anydoc 技术评估：能否用于 WSJ 报纸 PDF 提取

评估日期：2026-10-13。方法：GitHub 源码/README 实读 + **在真实 WSJ PDF（2026-10-12，26 页）上实测**。
测试环境：`pip install firecrawl-anydoc pdf-inspector`（pdf-inspector 1.25.2，最新）。

## 1. 它是什么

- firecrawl/anydoc：Rust 库（MIT，~22.7k stars，2026-08 创建），把 Word/PowerPoint/Excel/OpenDocument/RTF/EPUB/CSV/**PDF** 转成干净的 GitHub-Flavored Markdown。
- Python：`pip install firecrawl-anydoc`（`import anydoc`）；另有 Node.js、WASM、Rust、CLI（npx）。
- **关键架构**：PDF 并不走共享 document model——由 pdf-inspector 直接输出 Markdown（`src/formats/pdf.rs` 注释明示 bypass）。
- 输出只有 **Markdown 字符串**，PDF 没有结构化 JSON 输出。
- 无本地 OCR：扫描页报 `NeedsOcr`；可 opt-in 走 Firecrawl Parse  hosted API（整本发送，无按页选择）。

## 2. 怎么运行 / 部署成本

`pip install` 即可，纯本地、无模型、无外部服务，官方称 <200ms/文档。部署成本**几乎为零**。
但注意：`anydoc.to_document()` 对 PDF 显式拒绝（"PDF converts directly to Markdown"）——拿不到 document model，也拿不到 assets。

## 3. 官方宣称的 PDF 能力（pdf-inspector）

- 位置感知提取（X/Y 坐标、字体信息）、**newspaper-style 多栏自动检测与顺序阅读**
- 表格双模式检测（PDF 绘图矩形 + 文本对齐启发式），自称处理金融表格、跨页续表
- 标题 H1-H4（字号比）、列表、粗斜体、页码标记（`--pages` 插 `<!-- Page N -->`）、按页提取（`extract_pages_markdown`，带页号）
- 自有 benchmark：reading order 0.915、tables 0.814（200 PDF 语料，本地引擎中最优）

## 4. 在真实 WSJ 报纸 PDF 上的实测结果

### 4.1 致命：整本解析失败
- 26 页整本 → `MalformedError: couldn't parse input: invalid content stream`。
- 逐页二分：25/26 页正常，**第 10 页**的 content stream 导致整本失败。pypdf/pdftotext 对该页正常。
- 结论：**一页坏，全本死**。生产用必须按页切分 + fallback，anydoc 不能作为单点引擎。

### 4.2 头版（多栏复杂版面）：灾难
- 整页被误判成巨型 Markdown 表格；各栏文字在单元格内混排（如市场数据条与马拉松图注挤进同一行）。
- 单词被字距拆散："Busin ess & Financ e"、"A ND R OBBIE G RAMER"、"THE WA LL STREET JOURNAL"。
- 阅读顺序错乱：沙特文章正文与芝加哥马拉松图注、俄罗斯文章互相穿插。
- ▲ 被误解码为 À；断字连字符残留（"in- cluding"）。

### 4.3 内页：可用但有硬伤
- 标题识别可用，无巨型表格；但多栏粘连：**"Governmentstack"、"toscrumbling"、"afteraircraft"、"strikereported"**——不同栏的词无空格直接拼接，对新闻文本是灾难性的。
- 图表标题 bleed 进正文（"Probability the U.S. is in a recession…"直接混入段落流），无图表对象识别。

### 4.4 金融数据页（道琼斯验证案例）：表格提取差
- 封闭式基金页：基金名和数字挤进同一单元格（"ReavesUtilityIncome UTG 36.96 36.39 Tortoise Enrgy Infra Crp TYG 43.27 39.52"），列对齐丢失。现有管线（pdftotext + 逐行解析）对此类表格更可靠。

### 4.5 图片：零
- 3 个测试页的 Markdown 中**零图片引用**。PDF bypass document model，`document.assets` 对 PDF 不存在。**图片/图表/信息图提取能力 = 无**。

### 4.6 页码对应：部分可用
- `extract_pages_markdown(pages=[...])` 按页返回（`page` 字段为页号）；CLI `--pages` 插页标记。
- 但单文档输出内无段落↔页码映射；Block 模型本身无页码/坐标字段。做"段落-来源页"追溯需按页切分后自行拼接。

## 5. 与 pdftotext / MinerU 对比

| 维度 | pdftotext -layout（现有管线） | anydoc/pdf-inspector | MinerU（开发机） |
|---|---|---|---|
| 报纸多栏文本质量 | 可用（保留视觉版面，管线已适配） | 差（粘连、错序、拆词） | 好（ML 版面理解）但重 |
| 表格 | 无结构，靠后解析 | 自称强，实测密表差 | 较好 |
| 图片提取 | 无（另用工具） | **无** | 有 |
| 结构化输出 | 无 | 无（纯 Markdown） | 有（JSON） |
| 页码对应 | 行号近似 | 按页 API 可实现 | 有 |
| 速度/成本 | 瞬时、零依赖 | 瞬时、pip | 慢、需 GPU |
| 鲁棒性 | 高（坏页不影响整本） | 低（一页坏全本死） |

## 6. 结论：不能胜任 WSJ 报纸 PDF 的主力提取

**不建议**将 anydoc 作为 Phase 2 的首选提取引擎，理由按严重度：

1. **无图片/图表提取**（PDF）——Phase 2 明确要求原始图片、图注、图表、信息图，anydoc 交白卷。这是硬性缺口。
2. **报纸版面质量不达标**——头版灾难、内页粘连词（"Governmentstack"类错误会污染翻译与编辑分析），不如现有 pdftotext -layout 管线。
3. **单点失败**——一页 content stream 异常则整本报错，生产鲁棒性不如 pdftotext。
4. **无结构化输出**——Phase 4/6 需要 Content Model（文章/段落/图片/表格对象），anydoc 只给扁平 Markdown，还得自己再解析一遍。
5. hosted OCR 整本外发、无按页选择——有数据顾虑且对我们无用（WSJ PDF 是文本型）。

**可用之处（有限）**：
- `pdf-inspector` 的按页提取 + `pages_with_columns/pages_with_tables` 元数据，可作为**辅助信号**（如快速判断某页是否含表格）。
- 对简单单栏文档（报告、论文）它是优秀工具——只是不适合报纸。

**建议路线**：保留 pdftotext -layout 做文本骨干（现有管线已验证）；图片用 pymupdf/pdfplumber 按页提 XObject（需实测）；表格沿用现有逐行解析；anydoc 不引入主流程。如以后要换引擎，MinerU 比 anydoc 更接近需求（有版面模型+JSON+图片），代价是 GPU 与速度。
