# WSJ 深读：受控预生产与 Editorial Selection 校准报告（2026-10-13）

## 1. 117 篇内容状态与预生产结果

**integrity_gate 最终状态**：PASS 113 / WARN 4 / BLOCK 0

| 状态 | 数量 | 说明 |
|---|---|---|
| PASS | 113 | 进入批量草稿生成与视觉 QA |
| WARN | 4 | E1-004/E1-007/E3-002/E3-005：turn_to 未确认（B版复杂版面，需人工确认续文） |
| BLOCK | 0 | 8 篇已全部修复验证 |

**40 警告分类**（已处理）：
- 36× `too_few_paras` → 全是正常内容类型（图注23/数据表7/来信5/更正1），门禁 `BRIEF_TYPES` 已补豁免，误报消除
- 4× `turn_to_unconfirmed` → 保留警告，需人工确认

**E2-010 截断问题最终状态**：**未截断，可发布**。中英结尾完整（"我周日晚上睡得更好。"/"I sleep better on Sunday nights."）。早前"而不是认为"系误读（完整句子的开头）。英文内部有小片段瑕疵（"approach Monday wi"后接完整句），不影响发布。

**8 篇拦截修复证据**：
- E1-005：EN p6 "scheduled for"悬空系导航标记隔断，删 `[Continued on page A7]` 标记，写 `continuation_merged`
- E2-001/E2-017/E2-033/E3-007：declutter 清理完成
- E3-003/E3-004/E3-006：turn_to 续文确认合并，写标记

## 2. Editorial Opportunity Benchmark

独立评审先定机会与标准，再跑 Planner。详见 `render/OPPORTUNITY_BENCHMARK.md`。

| Pattern | TP | FP | TN | 状态 |
|---|---|---|---|---|
| L02 边注 | 2 (E1-023/E2-021) | 0 | 18篇 | ✅ 已验证 |
| L03 平行双栏 | 1 (E1-010 p5-p6) | 0 | 4 | ✅ 已验证 |
| L05 图文并置 | — | — | — | ⚠️ 未验证（缺资产管线） |
| L08 跨栏图形 | — | — | — | ⚠️ 未验证（缺资产管线） |

**关键正例**：E1-010 新 Planner 选中 L03（10月vs7月调查，3维度：5.1%/4.4%、4.96%/4.3%、4.78%/4.26%），同时拒绝 p14 的 L03（分析师数值 vs CBO上限 vs OMB范围，维度不对等）。**同一篇内区分真伪平行结构**——这是选择能力而非仅拒绝能力的证据。

## 3. Planner → Renderer 契约

- `render/plan_adapter.py`：六段式 → renderer schema 适配层
- 结构验证：空 entries/缺文本/中英不同源 → **抛异常 loud fail**，不许空白渲染静默通过
- 已修复 2 处 schema 不匹配（timeline events/entries、quote_cn/text_cn）
- 双语同源检查：timeline 中英长度比 0.2–4.0 超出则拦截

## 4. 编辑质量 vs 工程测试

**工程门禁**（保留）：integrity_gate、plan_validate、quote 三层校验、render_leak 检查

**阅读质量评估**（独立）：
- Text Treatment：18篇 0–11项/篇，T01 克制（E1-007 仅2处加粗），无为加粗而加粗
- Layout：L02 两处均为真需求；L03 一处真平行；16篇 L01 是恰当保守
- Reading Aids：timeline/quote 数据逐字来自正文，无编造

**未用组件数量/零溢出/构建成功率代替质量**。质量证据是具体的编辑判断记录（见 Benchmark）。

## 5. 交付物

1. ✅ 117篇状态：113 PASS / 4 WARN / 0 BLOCK
2. ✅ 40警告分类：36误报消除，4保留人工确认
3. ✅ 8篇拦截修复证据（本报告 §1）
4. ✅ OPPORTUNITY_BENCHMARK.md
5. ✅ L02/L03 正反例（本报告 §2），L05/L08 诚实标未验证
6. ✅ 页面与截图：`2026-10-12/auto-test/`（18篇）、`2026-10-12/layout-test/`（5篇）

## 6. 下一步

1. 人工确认 4 篇 turn_to（E1-004/E1-007/E3-002/E3-005）
2. 建 photo/chart 资产关联管线，补 L05/L08 benchmark
3. 进 117 篇全量生产
