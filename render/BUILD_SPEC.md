# 渲染器构建规格（render/）

## 输入输出
- 输入：`/home/hatch/workspace/wsj-deep-read/2026-10-12/final.json`（117 条，已定稿）
- 输出：`/home/hatch/workspace/wsj-deep-read/2026-10-12/dist/index.html`（单文件；Google Fonts CDN 外无依赖）
- 构建命令：`cd /home/hatch/workspace/wsj-deep-read/render && python build.py --issue 2026-10-12`

## 设计依据（必读）
1. `/home/hatch/workspace/wsj-deep-read/DESIGN.md`（v1.0，全部真实数值）
2. `/home/hatch/workspace/wsj-deep-read/reference/hybrid-v3/build_hybrid.py`（验收页面的实际 CSS，直接复用其 token 与组件样式，泛化为多文章）
3. `/home/hatch/workspace/wsj-deep-read/render/tokens.css`（已提取，直接用）

## render/ 包结构
- `tokens.css`（已有）
- `components.py`：`article_header(e)` / `body_paras(e)` / `key_figures(m)` / `timeline(m)` / `quote(m)` / `context_box(e)` / `figure(img)` / `data_table(e)`
- `article.py`：`render_article(e, modules, images)`，按 type 分流
- `issue.py`：整期组装（目录/导航/上下篇/进度条）
- `build.py`：CLI
- `modules.json` / `images.json`（已有；只读不写）

## 文章类型渲染（DESIGN.md §9）
- article/opinion：完整 hybrid 文章页（kicker/标题/导语/byline/正文 + 策展模块 + 底部背景折叠）。opinion 的 kicker 标注"观点"。
- brief/letter：紧凑条目（小标题 + 导语 + 正文，无模块；letter 标注"读者来信"）。
- data_table：真表格（body_cn/body_en 按 `|` 切分行列）+ caption，沉底附录。
- photo_caption：图注条目；images.json 有图才配图（base64 嵌入），无图则纯文字图注。
- index_digest/correction：极简条目。

## 模块规则（铁律）
- key_figures/timeline/quote 只在 modules.json 有该文章 key 时渲染；**绝不自动生成**。
- quote 只取直接引语一句（DESIGN.md §7），人物介绍/叙述留在正文。
- context 统一用底部折叠 `<details>`（AJ 式），有 context_cn 才渲染。
- **"主张与现实"对照模块在任何文章中都不许出现**（已删除的组件）。
- 正文逐字来自 final.json（`body_cn`/`body_en` 按 `\n\n` 分段），一字不改。

## 整期组织
- 分组：P1 必读 → P2 → P3 → 数据附录（data_table 全部沉底）。组内按 final.json 原顺序。
- 目录：分组标题 + 每条（标题 + 版面 + 页码感），锚点跳转。
- 每篇文章：id 锚点 + 上一篇/下一篇（阅读顺序）+ 返回目录。
- 顶部：masthead + 全局中英切换 + 2px 阅读进度条。

## 自查（构建者必须跑完再汇报）
1. 117 条全在，无遗漏/重复/错序；每篇段落数与 final.json 一致（脚本断言）
2. 中英切换全局正常
3. 1440/768/390 截图：目录 + 至少 3 种文章类型，0 横向溢出
4. 引语模块只在 E1-005 出现且为直接引语；无 duel 残留（grep）
5. 图片只来自 images.json；表格正常渲染
6. 汇报：测试结果 + 截图路径 + 已知问题
