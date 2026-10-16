# WSJ 深读 · 设计规范（DESIGN.md）

版本：v2（2026-10-16）。视觉权威是 Issue Artifact 的 Reader：`render/tracer/shell.py`。
`reference/hybrid-v3/` 和 2026-10-13 静态渲染器数值是被取代的起点，不是现行 tokens。
字体、密度和编排需要通过真实文章验证。原型是起点，不能把历史数值当作设计探索的终点。

---

## 1. Design philosophy

- **内容是主体**：保留完整报道的事实、证据、语气、顺序与论证；增强阅读，不把连续叙事改造成摘要或组件集合。
- **AJ × WIRED 是研究起点**：延续 AJ 的新闻层级与结构纪律、WIRED 的字体气质，发展 WSJ 深读自身的编辑身份。
- **正文是主要设计材料**：先治理字体、混排、行宽、行高、段落和章节，再判断图片、边注或对照是否有独立价值。
- **颜色纪律**：颜色标记状态、身份和行动，不代替排版表达。
- **编辑判断包括不干预**：数字、日期、人物数量不决定组件；克制也不意味着所有文章只能采用同一种单栏表达。
- **三档是不同的表面**：Full Editorial Composition、Typographic Editorial Composition、Compact Functional Format 不共用旗舰头。Forensic Dossier 是第一档里一类故事的文法，不是第四档。

### 五个相连的设计尺度

| 尺度 | 要判断的内容 |
|---|---|
| 内容理解 | 叙事如何展开，哪些是场景、证据、背景、转折和限制；读者实际会在哪里理解困难 |
| 微观排版 | 中文与西文字面、标点空距、标题词语完整性与自然断行 |
| 编辑文字 | 连续阅读舒适度、段落节奏、章节准确性与有限的语义强调 |
| 文章编排 | 正文、原始视觉证据和辅助解释的空间关系；每次变化是否帮助理解 |
| 出版物身份 | 不同文章表达各自气质，同时共享字体、网格、色彩与整期阅读逻辑 |

响应式设计贯穿五层。桌面并排的关系到手机仍须可理解；正文稳定呈现，交互只解释状态和支持导航。

## 2. Typography（字体家族）

| 角色 | 中文模式 | 英文模式 | 说明 |
|---|---|---|
| 展示标题 | Noto Serif SC | Playfair Display 800 | Issue Artifact 标题字重 800 |
| 正文 | Noto Serif SC 400 | Lora 400 | 中文混排沿用思源宋体；英文阅读整体切换 |
| 元数据/标签/按钮 | Noto Sans SC | Inter | kicker、byline、模块标签、语言切换 |
| 数据/序号/时间戳 | Noto Sans SC / JetBrains Mono | JetBrains Mono | 关键数字、masthead 日期、section 编号 |

铁律：
- 中文连续正文**禁用** `text-wrap: pretty` / `text-wrap: balance`；自然折行。`balance` 只用于标题与头版短导语。
- 中文**禁用**首字下沉。
- 正文不许伪粗体；不许为视觉随意加小标题。
- 双语模式只配对主叙事散文。SVG 内部标签和微控件保持单语言，避免几何溢出。
- 参考：[Apple 官网排版细节鉴赏](https://skywt.cn/blog/apple-typography-details)、[W3C 中文排版需求](https://w3c.github.io/clreq/)。学习光学协调与工艺，不复制 Apple 私有字体。

## 3. Typography scale（Issue Artifact）

权威实现：`render/tracer/shell.py` 的 `CSS`。

### 桌面

| 元素 | 字号 | 字重 | 行高 | 颜色 |
|---|---|---|---|---|
| 阅读单元 h1 | 42px | 800 衬线 | 1.25 | --ink |
| 概览页标题 | 32px | 800 衬线 | 1.3 | --ink |
| deck / 头版 dek | 18px | 400 | 1.7 | --mut |
| kicker | 13px | 700 无衬线，字距 0.14em | — | --mut（+ accent 方块） |
| byline | 13px | 700 无衬线 | — | --ink |
| 正文 | 17px | 400 衬线 | 1.85 | --body |
| 引语 | 19px | 700 衬线 | 1.6 | --ink |
| 论点盒 | 18px | 700 | 1.7 | --ink |
| 要点 | 15.5px | 400 | 1.7 | --body |

### 移动（≤430px）

| 元素 | 字号 |
|---|---|
| 阅读单元 h1 | 28px |
| 概览页标题 | 26px |
| 正文 | 17px / 1.85 |

768px 以下阅读单元 h1 为 30px。

## 4. Layout

- 外壳最大宽 1120px，左右 20px。
- Compact Functional Format 单元头和正文收至 680px。
- 非对称旗舰：正文列约 650px + sticky 右栏 280–380px；≤980px 单栏。
- 段落间距 1.05em。
- 概览与阅读是同一份 Issue Artifact 里的两种视图，不是两个站点。
- 禁止：整页大边框卡片；为填满栏位造模块；把印刷广告收成读者图。

## 5. Tokens

```css
--paper:#faf8f4; --paper-card:#f3efe6; --paper-deep:#ebe5d8;
--ink:#141413; --body:#242220; --mut:#646059; --line:#dcd6c8;
--accent:#b85d19; --accent-soft:rgba(184,93,25,0.14);
--navy-bg:#0f1d2b; --navy-card:#16283b; --gold:#c99738;
--orange:#b85d19; --red:#9e2a2b;
```

- accent：masthead 方块、kicker 方点、强调边、部分数值。不是交互色。
- navy / gold：仅 Forensic Dossier 的 defense 面板。
- 黑底 accent 左边：仅卷宗收束 verdict。
- 语言切换：黑 pill。
- 圆角：新闻模块 0；pill 9999px；defense 面板 3px。
- 结构线：masthead 底 2px --ink；章节底 2px --ink。

被取代的 hybrid-v3 色板（`--paper:#fdfbf8`、`--orange:#fa9000`）不再约束 Issue Artifact。

## 6. Article hierarchy

masthead（accent 方块 + wordmark + 黑 pill 中文/EN/双语）→ 七个 canonical section 导航 → 概览或阅读视图切换 →
单元：kicker → h1 → dek → byline → 按档位嵌入的模块（要点 / 论点盒 / Forensic Dossier / 图与 Chart Companion / `<wsj-chart>`）→ 正文流。

印刷图锚在 `after pK`，不堆在第一段前。

## 7. Composition surfaces

### Full Editorial Composition
叙事节奏、原图按印刷顺序入文、Declarative Visual Primitive、或 Forensic Dossier（hero ledger、rail metric、defense 面板、verdict）。数字必须段落锚定。

### Typographic Editorial Composition
按体裁：分析要点（不引用 lede）、意见论点盒 + 直接引语、书评作品元数据卡、sidebar 链到父篇。

### Compact Functional Format
What's News（深链）、Composite Column、短讯、更正、只读行情表。不要旗舰头。

### Chart Companion 与印刷图
原图 WebP + 双语伴读卡，标签来自 `Retina*`，不来自 OCR 表。

### 已删除
- 「主张与现实」对照模块。
- Studio 操作台、队列、版本浏览器出现在 Reader 表面。

## 8. Mobile behavior

- 390px：单栏；正文 17px / 1.85；左右 20px。
- Certification Oracle 7 在 1440×900 与 390×844、三种语言、概览与阅读视图上要求 `scrollWidth <= clientWidth`、无破图、SVG 字不裁切。
- 零溢出不能代替整篇实读。

## 9. Content presentation

| 内容 | 表面 |
|---|---|
| 头版/机制/调查旗舰 | Full Editorial Composition，必要时 Forensic Dossier |
| 标准稿 / 分析 / 意见 / 书评 | Typographic Editorial Composition |
| 短讯、摘要、来信、更正、行情表 | Compact Functional Format / Composite Column |

不同类型不许机械套用全部组件。模型写原语，编译器出 SVG；不许为填满页面编造数据。

## 10. 可访问性与验收

- 语义结构、键盘可操作、语言切换可见状态。
- 对比度按 --ink / --body / --mut 落在 --paper 上验收。
- 每次发布：叙事守恒、段落数字锚定、印刷图向量、无管道字符串、桌面与 390px 双语可读。

## 11. 生产流程

数据流与剩余风险见 `ARCHITECTURE.md`；命令见 `render/BUILD.md`。Primary Vector Signals 加已审双语单元是内容依据，格式化不改写正文。

下文是有时点的实施／探索证据，不代替当前运行验证。

## 12. Historical notes (not current tokens)

- v1.1（2026-10-13）静态渲染器：h1 40px/700，`--paper:#fdfbf8`，`--orange:#fa9000`。证据见 `2026-10-12/archive/historical-outputs/reboot-proof/`。
- v1.2（2026-10-14）阅读节奏探索从未并入生产页。
- Studio 生成提示的另一套色板已随 ADR 0002 退出产品。
