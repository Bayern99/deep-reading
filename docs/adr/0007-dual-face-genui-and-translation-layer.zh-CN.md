# ADR 0007：双面 GenUI、并行翻译层与多章节整书导出

- **状态：** 已采纳
- **日期：** 2026-12-10
- **取代：** [ADR 0006](0006-headless-go-deepread-engine.zh-CN.md) 的四条约定——10 原语白名单、零 JavaScript 强制、禁止翻译、仅支持单文档导出。
- **延续：** ADR 0006 的无头 Go 能力层、Prose-by-Reference、与 `Mark Go Go` v3 的单向兼容，以及单目录单文档隔离。

## 背景

ADR 0006 交付的是一个刻意收窄的阅读器：10 个静态原语、无脚本、一次只导出一篇文档、正文永不翻译。真实读者（《WSJ》《经济学人》式长文）很快提出了 v0.2 契约无法表达的三个需求：

1. **用自己的语言读。** 中文读者希望整篇文章是可读的中文（或日文、葡文……），同时原文段落始终作为不可篡改的地面真值随时可对照。"就地翻译正文"会直接摧毁 Prose-by-Reference 不变量——此后所有 diff、批注与引用都无法核对。
2. **真正的阅读画布。** 因果机制、多主体对比、时间线、术语旁注、以及以原文端点为界的"如果……会怎样"控件，都不是 `Table` + `Chart` 能表达的。10 原语白名单把所有文章压成同一种稀疏表格，恰恰是 ADR 0006 想避免的套话。
3. **一份交付，而不是五个文件。** 五章 EPUB 产出五个互不相干的 `chapter.html`，读者不会按顺序打开。

同时，编辑大脑仍是宿主 Agent（而非本二进制），而主要操作者是轻量云电脑模型。因此任何新能力都必须**确定性、离线、且不可能被误用**：运行时不调用翻译 API、不执行 Agent 编写的 JavaScript、更不会静默发布半翻译页面。

## 决策

### 1. 并行、内容寻址的翻译层

正文逐字节不变，译文存放在旁边。

- `.deepread/translations/<lang>.json` 以确定性块 id 为键保存 `{id, sourceHash, text}`。块 id 为 `b` + 空白归一化后正文的 `fnv1a32` 摘要：段落重排或插入读者批注不会让译文失效，真正改写正文才会。
- `deepread blocks` 暴露实时可译单元（`heading`、`paragraph`、`blockquote`、`list_item`、`table_cell`、`image_alt`）及其 id、哈希、小节归属与文本。
- `deepread translate --lang <bcp47> --input <file|->` 合并一批译文（JSON 数组、`{"entries":[...]}` 或 JSONL）。每条记录在落盘前都要对**实时**文档校验：未知 id 或不安全正文（空文本、裸 `<script>`、块级图片 Markdown）是校验拒绝；`sourceHash` 过期则是 CAS 冲突，避免 Agent 用旧译文覆盖新正文。
- `inspect` 报告 `translation.coveragePct`、`translatedBlocks`、`staleBlocks`、`missingIds`、`staleIds`；`export` 在 `translated`/`bilingual` 模式下，若覆盖率未达 100% 或存在过期块，直接拒绝渲染（仅可用显式 `--allow-partial-translation` 放开）。
- 阅读契约（`sourceLang`、`targetLang`、`mode`）记录在 `.deepread/manifest.json`，因此 `ingest --lang zh-CN` 与 `export --lang auto --mode auto` 天然一致，无需重复传参。`prepare` 插入的合成 H2 锚点把可选译名存在 manifest 中，而不成为翻译单元。

### 2. 与 legacy margin 并存的 50 组件 canvas 画布

`view.WriteOptions.Profile` 选择契约，`deepread catalog [--profile canvas|margin]` 打印契约：

- **`canvas`（默认）**：完整的 `Mark Go Go` v3 组件目录（50 个组件：`Col`、`Row`、`Grid`、`Card`、`Svg`、支持 bar/line/area/pie/donut/scatter 的 `Chart`、`Table`、`List`、`Popover`、`Flashcard`、`Slider`、`SegmentedControl`、各类输入控件……）。`Source` 可为真正的跨节综合引用多个小节，页头也可放在 `Source` 之外。
- **`margin`**：与 v0.2 逐字节兼容的 10 原语子集，保留给已有文档包与需要最窄契约的宿主。

编辑质量改为由**内容**把关而非 10 原语白名单：`PROSE_WRAPPER_REJECTED` 拒绝把原始段落套进 `Card([Title(...), Text(...), Badge(...)])`，同时放行带 `title + description` 的多条结构化可扫读 `ListItem`、`Quote`、原刊 `Image`、`Svg`、`Chart`、`Table`、`Timeline`、`Popover`/`Flashcard` 及交互孤岛；`GENERIC_KV_TABLE` 拒绝两列键值堆砌（`指标|数值`、`项目|事实`、`metric|value`），`MONOTONE_VIEW` 拒绝超过三分之二 `Source` 模块共用同一种主导载体（表格或纯文本）的画布，`CLICHE_TITLE_REJECTED` 拒绝"总结/要点"式标题，`UNTRANSLATED_GENUI` 拒绝在中文契约下仍是英文的 GenUI 文本。默认 `dual` 阅读面首屏呈现「去文字墙、全信息量结构化精读画布」（保留约 95%+ 报道信息量），完整逐字译文/原文/双语对照始终一键可达；同时也支持 `--face inline`（按 `--cite` 段落级交错）与 `--face hybrid`（篇首核心导览画布 + 段落级伴读）。

### 3. Go 预计算的响应式孤岛与唯一常量运行时

图表、时间线、示意图不需要脚本；"如果……会怎样"控件则需要。DeepRead 在不引入任何 Agent 编写的 JavaScript 的前提下解决这一张力：

- Go 导出器枚举每个 `$variable` 控件的有界状态空间，把**每一个**状态预渲染为静态 `<template data-island=… data-state=…>` 片段。状态组合超过 64 种时降级为默认状态并给出 `REACTIVE_STATE_EXPLOSION` 警告，而不是把页面撑爆。
- 唯一一段**常量**运行时脚本负责切换阅读面（`GenUI ↔ 原文`）、章节、语言模式、孤岛状态，以及 `查看原文 ↗` 锚点跳转。它从不用文档数据做模板插值，并由页面 CSP 的 SHA-256 `script-src` 哈希锁定，任何被改动或注入的脚本都无法执行。
- `--no-js` 仍产出完整的双面页面（控件禁用）；无视图的单文档 `read` 导出保持原有零脚本形态。
- 每个模块保留始终可见的短码（`<bundleId>·<statement>@r<rev>`），并新增 `查看原文 ↗` 芯片，依据 `--cite <stmt>:<srcId>=<blockId>` 写入的 `.deepread/citations.json` 跳到被引用的具体段落。

### 4. 多章节聚合为单个离线 HTML

磁盘隔离不变：每章一个目录（`chapters/<NN>-<slug>/chapter.md`，各自带 `.deepread/` 与 `assets/`）。交付方式改变：

- `deepread export --book <book-dir> [--chapters 1,3,5-7|<slug>|all] -o <out.html>` 通过 `os.OpenRoot` 解析 `book.json`，校验每章仍在书籍目录内，渲染**一个**带目录、章节导航与统一资产预算的离线 HTML 阅读器。
- `deepread export <doc1.md> <doc2.md> … -o <out.html>` 按给定顺序聚合已导入的文档包。
- 单文档导出与从前完全一致（`deepread export <doc.md> -o <out.html>`）；逐章中间 HTML 不再是交付契约的一部分。

## 后果

- **正向**：读者得到母语正文且原文一键可回；宿主得到基于规则、确定性的画布契约，无法退化为摘要表格；页面始终离线、无外部依赖、CSP 加固；整本书只产出一个文件。
- **正向**：翻译工作可增量、可审计：`blocks` → `translate` → `inspect`（`coveragePct`、`staleIds`）→ `export` 构成闭环，退出码能区分"缺失"（`3` `TRANSLATION_INCOMPLETE`）与"过期"（`5` `CONFLICT`）。
- **负向**：`SKILL.md` 必须承载完整的第 0 步阅读契约（目标语言、模式、范围、交付形态），因为轻量模型不会自己推断；手册因此更长，并成为权威规范。
- **负向**：canvas 模式把更多重量放在编辑护栏上：弱 Agent 仍可能产出合法但平庸的页面。`MONOTONE_VIEW` 与 `GENERIC_KV_TABLE` 约束的是失败下限，而不是雄心上限。
- **迁移**：`version: 3`、`language: "openui-lang/1.0"`、`catalogId: "markgogo.dev:genui/v3"`、`.genui.prev.json`、`fnv1a32` 哈希、属性化 `<!-- note ... -->` 批注全部不变。既有 v0.2 margin 文档包通过 `--profile margin` 继续可用，`margin` 导出面保持字节兼容。
- ADR 0006 仍是"转向无头 Go"的历史记录；本次仅替换上述四条被取代的约定。
