# R3.3 交付（2026-10-13）：Vercel Web Interface Guidelines 重述

Jerry 指定按 https://vercel.com/design/guidelines 重述 R3.2。全文读过后，
筛选出适用于编辑阅读页的 12 条（表单/营销 copy 类 guideline 不适用，已剔除）。

## 改了什么
1. **Clear focus** — 语言切换按钮 + 链接加 `:focus-visible` 朱砂色聚焦环
2. **触摸目标** — 切换按钮 `touch-action:manipulation`、`-webkit-tap-highlight-color`；手机端最小 44px
3. **Skip link + 标题层级** — 新增"跳到正文" skip link（聚焦时才出现）；文章标题 h3→h2，h1→h2 层级连续
4. **CSS 优先于 JS 动画** — 删除 IntersectionObserver，reveals 改用纯 CSS `animation-timeline: view()` scroll-driven（Vercel 首选：CSS > WAAPI > JS 库）
5. **Compositor-friendly** — 只动 transform/opacity；**Never transition:all** — 全站无 `transition:all`
6. **Necessity check** — 动画仅用于入场揭示，无装饰性循环
7. **text-wrap:pretty** — 正文段落防寡行/孤行（标题已有 balance）
8. **Safe areas** — 手机端 padding 计入 `env(safe-area-inset-*)`
9. **theme-color + color-scheme:light** — 浏览器 UI 与纸色对齐
10. **防 CLS** — figure 加 `aspect-ratio` 预留空间（充电站 485/314、图表 410/330）
11. **Non-breaking spaces** — 英文数字+单位间 `&nbsp;`（at least&nbsp;12、about&nbsp;500&nbsp;miles 等 7 处）
12. **Redundant status cues** — 确认：对照表/时间线均有文字标签，不只靠颜色

## 没改（有理由）
- Vercel copy 规范（Title Case、`&` 代 and、第二人称）是 Vercel 品牌偏好，非通用 guideline
- `overscroll-behavior:none` 未加：阅读页保留原生滚动链更合适
- 朱砂+石油青双色保留（R3 brief 点名探索的组合）

## 验证
- 内容完整性：两篇文章正文零漏句；低质图已撤（特斯拉小图、沙特机场截图），只剩充电站实拍 + B1 原图表
- 三种屏幕渲染：桌面 1440 / 手机 390 / 超宽 2560（Vercel 要求 mobile+laptop+ultra-wide 全覆盖）
- 全页长截图的"空白"是 scroll-driven reveals 的正常行为（未滚动到的元素 opacity:0），滚动后内容完整呈现

文件：`~/workspace/wsj-r3-3.html`（构建器 cases/build_shell_r3_3.py + build_r3.py/build_r3_1.py）

## 肉眼审查修复（2026-10-13，Jerry 要求"自己看"）
逐屏看过桌面 1440 / 手机 390 / 超宽 2560 后修了两处：
1. 页脚"12%→6% 柱状图（数据来自正文第 9 段）"——实际数据在**第 10 段**（已对 final.json 核实），改为第 10 段；图注里的"来源：第 9 段"同步改
2. 手机端 "P1 必读" 徽章换行断成两行——加 `white-space:nowrap`
