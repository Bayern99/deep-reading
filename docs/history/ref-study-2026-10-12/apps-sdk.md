研究完成。三处来源都实际打开了（docs 站是 JS 渲染读不出，改从 GitHub 源码直接取了 token 文件，这是更准的一手来源）。报告如下：

---

# OpenAI Apps SDK UI 设计系统研究报告

## 一、设计 Token 体系（来自源码实测）

**字体层级**（`src/Typography.mdx`，tracking 全部 0em）：
| 级别 | 字号/行高 | 字重 | 对应用途 |
|---|---|---|---|
| heading-xl | 32px / 38px | 600 | 大标题 |
| heading-lg | 24px / 28px | 600 | 卡片标题 |
| heading-md | 20px / 26px | 600 | 小节标题 |
| heading-sm | 18px / 26px | 600 | — |
| heading-xs | 16px / 24px | 600 | — |
| text-lg | 18px / 29px | 400 | 大正文 |
| text-md | 16px / 24px | 400 | 标准正文 |
| text-sm | 14px / 20px | 400 | 辅助说明 |
| text-xs | 12px / 18px | 400 | 标签/元信息 |
| text-2xs | 10px / 14px | 400 | 微标签 |

要点：①标题统一 semibold（600）而非 bold，这是它"精致感"的重要来源；②正文只有 400 一档，层级靠字号和颜色拉，不靠字重乱加；③字体栈是纯系统 sans（`-apple-system, system-ui, "Segoe UI"...`），**serif 在 token 里是 `initial`（未定义）**——整个系统是 sans-first。

**间距**：`--spacing: 0.25rem`（4px 基准，Tailwind 式倍数）；示例卡片内边距 `p-4`（16px），行间距 `gap-3`（12px）。

**圆角 scale**：2xs 2px → xs 4px → sm 6px → md 8px → lg 10px → xl 12px → **2xl 16px** → 3xl 20px → 4xl 24px → full。示例中的 reservation card 用 `rounded-2xl`（16px）。

**边框三档**（全部是 alpha 透明黑，不是实色）：
- `border-subtle`：5% 黑 —— 组件内部分隔
- `border`（default）：10% 黑 —— 卡片外框
- `border-strong`：15% 黑 —— 强调分隔
- 另有 `--hairline: 1px`，高 dpi 屏自动降为 0.5px

**表面四档**：surface（纯白）/ surface-secondary（gray-50）/ surface-tertiary（gray-75）/ surface-elevated。另有 elevation-100~400 四档阴影（alpha 0.08~0.12，极淡）。

**颜色**：灰阶 0~1000 全套 `light-dark()` 自适应；语义色只有 text / text-secondary / text-tertiary / text-inverse 四档正文色；功能色（蓝/绿/红/橙/黄/紫）各有 25~1000 阶 + alpha 变体，**只用于 badge、按钮 accent，不碰正文和背景**。

## 二、Inline Display 原则（`ui-guidelines`，转述）

核心思想：inline 组件是"嵌在对话流里的轻量表面"，第一要求是**不打断阅读流**。具体规则：

1. **单一用途**：一张卡只做一件事（确认一个动作 / 一小块结构化数据 / 一个自包含小部件）。需要多视图、tab、深层导航的，不要塞进卡片，拆成多张卡或走 fullscreen。
2. **动作上限 2 个**：1 个 primary + 1 个 secondary，放在卡片底部。Carousel 里每项最多 1 个 CTA。
3. **Show more 披露**：多条目列表默认收起，用 "Show more" 展开——这正是我们 Context 折叠的官方背书。
4. **禁止嵌套滚动**：卡片高度自适应内容，不许内部滚动条。
5. **排版克制**：继承系统字体；**尽量只用 body 和 body-small 两种字号**；bold/italic 只用在内容区，不用在结构 UI 上；不许自定义字体。
6. **颜色克制**：正文、图标、分隔线一律系统色；品牌色只出现在 badge 和按钮 accent；**不许给文字区上彩色背景**；不许自定义渐变。
7. **信息密度上限**：carousel 3~8 项；每项元信息不超过 2~3 行；跨卡片保持一致的视觉层级。

## 三、轻量化设计方法：省略什么 / 保留什么

| 省略 | 保留 |
|---|---|
| 卡片内的 tab、多视图、深层导航 | 标题（仅当内容是文档型时才要） |
| 嵌套滚动 | 单一信息层级：标题 → 辅助文字 → 动作，顺序固定 |
| 每卡超过 2 个按钮 | "Show more" 式披露 |
| 自定义字体、渐变、彩色文字背景 | 系统间距网格，padding 一致、不挤 |
| 超过 3 行的元信息 | 跨组件一致的层级语言 |

一句话：**组件的"轻"不是元素少，而是每种元素只出现一次、只做一件事。**

## 四、四个可直接借鉴的参数/模式

1. **标题 semibold 化**：SDK 所有标题统一 600 而非 700。我们的衬线标题现在是 700，在中文衬线里 700 容易发闷；标题降到 600 是成本最低的精致度提升。
   链接：https://github.com/openai/apps-sdk-ui/blob/main/src/Typography.mdx

2. **Reservation card 的 dl 模式**（README 示例）：小灰 label（`text-secondary text-sm`）+ 右对齐 value + hairline 行分隔，图标+label 左、值右。这是现成的 "Key Facts / Compact Stat" 版式，可直接用于文章内的关键事实模块。
   链接：https://github.com/openai/apps-sdk-ui

3. **边框三档语义**（subtle 5% / default 10% / strong 15%）：我们现在的 1.5px 实黑线只有"一档"，所有分隔一样重。借鉴它的分级思想：结构分隔（版块线）保持 1.5px 黑，组件内部分隔降为 hairline 灰——我们 v6 的 context 1px 灰线已经暗合了这条，可以系统化。
   链接：https://github.com/openai/apps-sdk-ui/blob/main/src/styles/variables-semantic.css

4. **字号克制原则**（"prefer body and body-small"）：我们条目内部现在有 kicker 11px / 标题 20~34px / 导语 15.5px / 正文 14.5~16.5px / context 14px / 表格 13px——6 档。按 SDK 的思路可收敛到 4 档，层级反而更清晰。
   链接：https://developers.openai.com/apps-sdk/concepts/ui-guidelines

## 五、映射到我们现有视觉系统（含圆角取舍）

| SDK 做法 | 我们的现状 | 取舍结论 |
|---|---|---|
| 圆角 2xl（16px）卡片 | 圆角 0 | **保留 0**。SDK 的圆角服务于"对话亲和感"，我们的零圆角服务于"报纸印刷权威感"——brief 不同。但借鉴它的**圆角纪律**：全站只用一个值，不混用（我们已做到，继续保持） |
| sans-first，无 serif token | 衬线标题 + 无衬线正文 + mono 标签 | 保留。SDK 不许自定义字体是因为"像 ChatGPT 原生"；我们的 brief 是 WSJ 纸媒，衬线标题是内容基因。但收敛：**标题只用 600 weight**（借鉴 1） |
| 边框 alpha 三档 | 1.5px 实黑单档 | 引入分级：1.5px 黑 = 结构线（版块/刊头）；1px `--line-2` = 组件内部分隔。v6 已部分做到，推广到 key facts/timeline 等新组件 |
| surface 四档 + 淡阴影 | 暖纸 `#f6f6f3` + 纯白卡片，无阴影 | 保留无阴影（印刷感）。表面分级可用：暖纸底 / 白卡片 / `--fill` 浅灰（已用于 context 旧版、表格隔行），三档够用 |
| text 三档灰阶 | ink / ink-2 / ink-3 | 已对齐，无需改。原则同样：颜色只编码信息层级，不装饰 |
| 4px 间距基准 | 混用（26px/30px/18px…） | 组件内部统一向 4px 倍数收敛（12/16/20/24），外部留白保持现有呼吸感 |

**最关键的一条映射**：SDK 的 Inline Display 本质上回答的是"小组件如何不打断正文流"——答案是*小、单用途、有明确的标题→内容→（动作）顺序*。我们的文章内组件（stat、comparison、key facts、timeline）应该逐个按这个标准验收：放进正文里，读者视线是滑过去而不是绊一下。