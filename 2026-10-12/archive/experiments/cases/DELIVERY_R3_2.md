# R3.2 交付说明 · 按三 skill 重设计

**Design read**：editorial 数字新闻出版物 redesign（内容保留、视觉 overhaul），双语长读读者，contemporary editorial 语言。
**Dials**：VARIANCE 6 / MOTION 4 / DENSITY 3。Vibe = Editorial Luxury（暖纸、高对比衬线标题、细微纸纹）。

## 按 skill 改动清单
1. **去 Inter**（SKILL-3 禁用、SKILL-4 不鼓励）：英文正文改用 Noto Sans SC 内置拉丁字母；展示层保留 Noto Serif SC + Newsreader（SKILL-4 serif discipline：出版/新闻世家 justified，非 Fraunces 类）
2. **标题**：负字距（-0.015em）+ `text-wrap: balance`（SKILL-2）
3. **对照表边框**：收紧为单分隔体系，不再每行上下框线（SKILL-4 4.7）
4. **数字行**：桌面端改 4 列横向数据条，不再是 2×2 卡片感（SKILL-2 反卡片）
5. **动效**（MOTION 4）：IntersectionObserver 驱动的 gentle fade-up reveal（cubic-bezier(.16,1,.3,1)，transform/opacity only），按钮 hover/active 反馈，平滑滚动；全套 `prefers-reduced-motion` 降级；无 scroll 监听器
6. **纸纹**：fixed SVG 噪点 overlay，opacity 0.03，pointer-events none（SKILL-3 Editorial Luxury）
7. **沙特 airport 实拍**：A7 跳页找到袭击后航站楼视频截图（238×247，原报小图），已嵌入并如实标注"视频截图"，不放大冒充高清
8. **em-dash**：我撰写的所有字符串（图注/标签/页眉/页脚）机械检查零违规；正文中的 —— 是来源内容逐字保留（内容铁律优先，已明确标注）

## 未改（有理由）
- 朱砂+石油青双色：用户 R3 brief 明确要求探索该组合；用法有严格语义分工（朱砂=强调，石油青=结构/对照编码），非随意多 accent
- 正文 em-dash：内容一字不动铁律

完整性/EN/双宽度截图均已验证。

## 图片取舍（2026-10-13 Jerry 决定）
- 撤掉：特斯拉 B2 小图（114×179 模糊人物照，零信息增量）、沙特 A7 机场视频截图（238×247，模糊）
- 保留：充电站实拍（485×314 清晰）+ B1 原青色月度图表（矢量）
- 标准：图片宁缺毋滥——清晰度不够展示尺寸、或无信息增量的图，不用
