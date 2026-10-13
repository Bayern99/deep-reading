# R3.4 交付（2026-10-13）：oil-ui 存量润色轮

## 方向（沿用，不重探）
朱砂印刷风（方向 A）+ Vercel guideline 合规。北极星：中文报纸的印刷质感，
朱砂作批注——像一份被编辑用红笔圈点过的深度阅读样张。

## 改了什么（独立评审 4 条，全修）
1. byline 大小写统一为全大写（CSS text-transform，内容不动）
2. 徽章语法写入规范：实心黑=必读级（P1），石油青描边=重点级（P2）
3. 桌面端"关键数字"四列底部对齐（说明文字底边齐）
4. 手机端 kicker byline 不折行
5. 页顶三层标识注明为"评审稿标识"，最终产品替换为真实刊头（不进最终版）

## 没改（有理由）
- 评审"保留"项：朱砂单侧批注语言 + "只给最关键一处朱砂"的克制
- 评审观察"石油青未进数字条"：维持克制，不为用色而用色
- 动效：评审只有静态截图，scroll-driven reveals 留待可操作环境复验

## 动效
CSS `animation-timeline: view()` scroll-driven 入场（R3.3 起），无 JS。

## 评审
1 轮，存量润色评审（不打分），独立评审者执行，主 Agent 按清单修改。

## 删掉的文字
无（正文一字不动为铁律；原型标识暂留，注明不进最终版）。

## 证据
- 成品：`~/workspace/wsj-r3-4.html`
- 设计说明：`cases/DESIGN_NOTE_R3.md`
- 基线截图：`cases/review/base-*.png`
- 修复后截图：`cases/shots/r34-d1.png`、`r34-m1.png`
- 构建器：`cases/build_shell_r3_3.py`（R3.4 输出）、`build_r3.py`、`build_r3_1.py`
