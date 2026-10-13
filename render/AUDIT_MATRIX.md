# 代码审计矩阵：现有实现 vs 51 Patterns（2026-10-13）

## 已实现（9 个组件，components.py + plan_render.py）
| Pattern | 实现 | 状态 |
|---|---|---|
| A03 核心数字 | key_figures() | ✓ 生产中 |
| A04 时间线 | timeline() | ✓ 生产中 |
| A05 背景说明 | context_box() | ✓ 生产中 |
| A01 照片 | figure() | ✓ 生产中 |
| A18 数据表 | data_table() | ✓ 生产中 |
| A02 图表 | chart() / infographic() | ✓ 生产中 |
| A12 数据图表 | bargraph() | △ 部分（仅柱状） |
| （引语） | quote() | ✓ 生产中（catalog 未单列，属 Reading Aid） |
| 事实门禁 | plan_validate.py | ✓ 日期/引文/credit 逐字校验 |

## 缺失：Text Treatment（0/9 实现）
T01 语义加粗、T03 数值内联强调、T06 引述归属、T07 限定词保护、T09 段落拆分、
T10 段落分组、T11 编辑小标题、T13 并列列表、T17 中英排版——全部缺失。
正文目前是 16px/1.8 统一样式，无任何语义处理。

## 缺失：Layout Grammar（0/4 实现）
L02 边注、L03 平行双栏、L05 图文并置、L08 跨栏图形——全部缺失。
当前所有页面都是单栏连续流。

## 缺失：编排与锚定
- narrative_outline / rejected_opportunities / quality_checks：无
- 稳定段落 ID / 文本 range / editorial_added 标记：无
- kit 的 editorial_plan.schema.json v0.1 vs 项目现有 schema：需版本化迁移

## 实施顺序（按 AGENT_IMPLEMENTATION_PROMPT.md）
1. 源锚定 → 2. Text Treatment → 3. Layout Grammar → 4. Reading Aids 接入 → 5. 联合编排
- 51 个 pattern 不全做：core 优先，已有 9 个复用，新增约 13 个（T×9 + L×4）
- E1-025 已知问题待修：图注与正文重复同一说明；引语在正文与 quote 模块重复
