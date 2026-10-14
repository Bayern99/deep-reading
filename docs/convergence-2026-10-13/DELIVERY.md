# Product Convergence 交付 · 2026-10-14

范围：Engineering Baseline（A）、Editorial Research & Art Direction（B）、Real Editorial Exploration（C）。全部通过同一生产 renderer 与 `2026-10-12/final.json`（SHA-256 `00fa35e8…5782`，未改动）。

## A · Engineering Baseline（P0 完成）

修复的真实缺陷（均有回归锁）：

| 缺陷 | 修复 | 证据 |
|---|---|---|
| EN 段数 > CN 时尾部丢失（E2-010 CN14/EN16） | `alignment_overrides.json` 确认型修复：剔除 `[Continued on page A12.]` 提取残件并缝合断句；两条原始 EN 尾段在 ordinary/enhanced/baseline 三条路径全部保留 | `test_p0_render.py`、`dist/render-receipts.json` |
| Preserve 计划改变普通文章（type head/dek/byline） | preserve/空计划逐字节委托 ordinary 渲染 | E1-014 回归 + CLI 断言 |
| 对齐修复只在部分路径生效 | ordinary/enhanced/baseline 共用 `source_model.source_from_final()` | 同上 |
| Baseline 不公正（丢已验证图片） | `_baseline_plans` 保留 figure/chart/infographic 资产与 L05/L08 视觉；构建比对两页每篇嵌入图 src 相等 | `check_body_copy` 前后比对 |
| 已接受操作被静默跳过 | 未知 pattern/动作/组件/类型、缺锚点/槽位、stale exact、T09/split 一律显式失败；未知 plan/操作/params 键显式失败；receipt 区分 preserved/applied/failed，异常写失败 sidecar | CLI 失败注入回归 |
| 计划与正文脱钩 | 可选 `content_digest` = sha256(article entry + 适用 alignment 修复)；不符在执行前失败 | 五份现有计划已钉 |
| 逐页正文核对缺失 | `check_body_copy` 解析**已写出的 HTML**：每篇发布文章 `[data-block]` 的 k-cn/k-en 内容与顺序等于 source 投影（enhanced 与 baseline 双页），不通过不写文件 | 本次 index+baseline+exploration 构建通过 |
| 策展摘要静默丢数字（评审后新发现的真缺陷） | `check_digest_copy`：live 表必须含每个源小数；suppress_body 的双语 insight 数字集合必须相等（新不变量 11）。E1-002 英文摘要漏 `477.99`/`0.74` 已补，E3-023 补 `insight_en` | CLI 回归注入「EN 漏 477.99 → 构建红」；修后两页通过 |

CLI：`python3 build.py --issue 2026-10-12 [--plans-dir DIR] [--output name.html] [--no-baseline]`。`--plans-dir` 叠加覆盖计划；`--output` 限 dist 内文件名（拒绝路径逃逸与保留名 baseline.html）；`--no-baseline` 供探索输出，对照页不被重写（mtime 前后验证）。探索页与生产页**同一 renderer**，无 demo 分支。

已知限制：`data_table`/`index_digest` 做数字保真而非逐字核对（投影不同；记录于 `benchmark.json publication_note`）；legacy 无 schema 计划（E1-033/E3-014）仍被 loader 排除，其历史资产不自动进入输出。

### Profiling（实测，非语言偏好）

`python-profile.json`：整期 core 构建（index+baseline+exploration，含 cProfile 开销）**2.10 s**。分布：integrity gate 1.90 s（瓶颈，declutter 正则在 117 篇全文上）；HTML 全文 copy 解析 0.16 s；两页 render 0.02 s；base64/JSON <0.01 s。Planning 模型调用（smol，8.2k 字符）**25.0 s**（`planning-proposal.json`）；保存的 proposal 读取 22 µs；legacy 完整性缓存命中 2 ms 但只回 manifest，不能证明结果等价。

**结论：瓶颈在 integrity gate 的正则扫描，比渲染大两个数量级；模型规划是主要延迟源。无迁移语言的证据。**

## B · Editorial Research & Art Direction

- 外部案例研究（AJ/WIRED/Guardian/FT 四篇真实长文，22 张实页截图，访问限制声明）：`PUBLISHING-CASES.md`。
- 证据综述与三条处理方向：`EDITORIAL-EVIDENCE.md`。
- 独立 Art Direction Review（平的主因、Restraint vs Inaction、三假设实页读数、不满意清单）：`ART-DIRECTION-REVIEW.md`。

核心判断：**平的主因是编辑文字层（正文内部角色、节奏、停顿、收束）缺位，不是组件不足。**

## C · Real Editorial Exploration

同一 `final.json`、同一 renderer，三页对照：`dist/baseline.html`（忠实基线，含资产）、`dist/index.html`（现行五计划，无 reading_profile）、`dist/exploration.html`（+E2-010 narrative、+E1-019 analysis、E1-010 改 evidence profile）。计划数据在 `2026-10-12/editorial-explorations/`，每个 `reading_treatment` 带 reason、逐块 evidence 与被拒机会。偏离 canonical 的数值全部登记 `DESIGN.md §13`，裁决前 §3 仍是生产标准。

实测（Chromium 1440/1080/900/390，双语 data-block 全量核对通过）：

| 篇目 | 干预 | 结果 |
|---|---|---|
| E2-010（narrative） | lead 23px、正文 18.5px/1.95、p7/p12 章节停顿、收束段、撤右栏 | 14 段全保留、0 溢出；场景连续性明显好于 17px 均匀流 |
| E1-019（analysis） | lead 20.5px 无衬线、正文 17.5px、4 处原句内口径强调、两处论证停顿 | 11 段全保留、0 溢出；`$1 billion`/`房地产除外` 在原文内可见 |
| E1-010（evidence） | 撤回与正文重复的加粗/小标题，仅保留三对同口径预测的放大比较场 + 两个源小标题 | 20 段全保留、0 溢出；比较块右缘 801@900、891@1080，边界视口无溢出 |

## 独立评审与处置

Standards（Reviewer-G/cursor-grok-4.7）+ Spec（cursor-grok-4.6；codex/gpt-5.4 与 kimi-code/k3 当日周配额耗尽，评审改由两个不同 Grok 会话承担并在评审词中声明）。逐条接受/驳回见 `REVIEW-DISPOSITION.md`。接受项全部落地（--no-baseline、digest 保真、strict keys、不变量 10/11 成文、`components.paras` 死代码删除、`raw_en` 更名）；驳回项附实测证据（溢出计算与实际几何不符；profile CSS 属探索本体且隔离在 exploration 输出）。

## Benchmark

`benchmark.json`：15 项真实内容（4 回归 + 2 新主设计样本 + 7 新对照 + 2 源边界），绑定 input SHA、逐篇 content_digest、publication 状态、评价要点（渲染探索**之前**落盘）。评价方式=个人实读 + 截图对照；**不招募读者、不做问卷/显著性、不建 Eval 平台**。限制已声明：全部文章经过历史生成，不构成未见盲测。

## 下一步（不扩大范围）

1. 按 `ART-DIRECTION-REVIEW.md` 的"仍不满意"迭代 profile 系统（限定句处理、手机端章节锚、lead 与 deck 关系），以真实文章判断。
2. integrity gate 提速（declutter 全量正则改单遍预筛）——仅在成为日常负担时做。
3. 第二期真实日期跑同一 foundation，验证不读旧资产。
