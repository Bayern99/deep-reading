# 复审处置记录 · 2026-10-14

对 Standards（Reviewer-G, grok-4.7）与 Spec（grok-4.6，Kimi 配额不可用）两轮独立审查逐条处置。Quota：codex/gpt-5.4 与 kimi-code/k3 当日均达周限额，Spec 轴由 cursor/grok-4.6 承担；两轴评审模型不同、互相独立。

## 修复（评审有效项）

| 项 | 处置 | 证据 |
|---|---|---|
| Spec-blocker：`--output` 探索输出仍重写保留的 `baseline.html` | 新增 `--no-baseline`，探索构建不再触碰对照页；写入 FOUNDATION § Daily build | `build.py` main；exploration 重建通过且 baseline.html mtime 不变 |
| Spec：策展摘要静默丢数字（真实缺陷：E1-002 英文摘要漏 477.99/0.74，E3-023 英文摘要缺失） | 新增不变量 11「摘要双语数字同集合」+ 构建期 `check_digest_copy`：live 表必须含全部源数字；suppress_body 的 insight 双语数字集合必须相等 | E1-002 `insight_en` 补回两点变化；E3-023 增加 `insight_en`；CLI 回归注入「EN 漏 477.99」必须红 |
| Spec/Standards：digest 类型完全不做正文核对 | 数字保真检查覆盖全部 `data_table`/`index_digest`（含未suppress条目 E1-001），HTML 表格单元格解析修复（旧解析把单元格粘连成 `0.180.613.63`，检查本身不可靠） | `_RenderedCopy` 表内文本以空格定界；两页构建通过 |
| Standards：修复逻辑更像逐篇 hack、与不变量 1 冲突 | FOUNDATION 增补不变量 10：修复只允许来自声明式 `alignment_overrides.json`、精确匹配、三路一致、计入 digest；未确认的对齐失败必须红而不是截断 | `test_repairs_are_independent_of_plan_and_do_not_mutate_final` 断言 final.json 逐字节不变 |
| Spec：未知计划字段静默忽略 | `_strict_plan_keys`：plan/操作/params/component 白名单，未知键显式失败（`cut` 保留给执行层报 T09/split 专用错误） | test_p0 全套通过 |
| Spec：receipt 失败 sidecar 只覆盖渲染+正文核对 | 维持现状并声明：门禁/资源失败在写出任何文件之前，dist 中不会出现半成品页面；receipt 语义是「已执行操作」，不适用于渲染前失败 | `build_issue` 顺序：gate→assets→render→copy checks→write |

## 驳回（有实测证据）

- **「evidence 比较块在 ~900–1080px 溢出约 24px」**：实测 Chromium 900/1080/1440 视口，`.ly-compare` 右缘分别为 801/891/无溢出，`scrollWidth ≤ viewport`。比较块以居中 620px 栏为基准放大 96px，距视口边缘恒有余量；该计算假设了全宽 padding，与实际几何不符。
- **「profile CSS 改了组件可见性，超出排印探索」**：`reading_treatment` 撤右栏/扩比较场是本批探索的设计假设本体（计划数据里逐条带 evidence），且只作用于 exploration 输出（`--output exploration.html`），`index.html` 不引用任何 `reading_profile`。canonical §3 数值仍是生产页标准；偏离值（narrative 手机 17.5/1.9、measure 620/610、analysis lead 无衬线）已在 `DESIGN.md §13` 登记为待 Jerry 实读裁决的假设，不是对 §3 的隐性改写。
- **「空 plan 仍可能插 modules.json 模块」**：不变量 4 的定义就是模块来自策展数据；当前 `modules.json` 为空（数据已迁入计划），且 preserve/空计划逐字节等同 ordinary 有回归锁。`_render_article` 的插入位代码是 ordinary 路径本体，删除它会改变无计划文章的既有行为，不在本次范围。

## 接受的低优先项（未改，记录）

- `headliner_phrases_cn`/`dim_labels_en` 等属上一轮已验收能力，非本轮范围蔓延；`_baseline_plans` L05→L08 是保资产的对照定义（基线不用增强版式但必须见同一张图），语义已在函数 docstring 与 DELIVERY 写明。
- 重复代码（receipt try/except 两处、`_RenderedCopy` vs 测试 `LocaleText`）：留待 P3 渲染层整合时一并处理；`source_from_final` 的 `g` 已更名 `raw_en`；无调用者 `components.paras` 已删除。
