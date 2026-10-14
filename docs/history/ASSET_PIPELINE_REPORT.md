# Visual Asset Pipeline 报告（Phase 2，2026-10-13）

## 提取结果

- PDF 图片对象：188 个（含广告碎片）
- 显著图片提取：66 张 → 补提小图 27 张 → 去广告 14 张 → **注册表 79 条**
- 资产文件：`2026-10-12/assets/`（PNG，可追溯到 PDF 页码+区域）

## 四分类统计（117 篇）

| 类别 | 数量 | 说明 |
|---|---|---|
| `extracted` | 45 | 已提取并关联到文章 |
| `no_asset` | 49 | 原文确实无视觉资产 |
| `unrecoverable` | 22 | 6 篇 photo_caption 未找到图；16 篇 B5/B6 数据表（矢量图表未提取为光栅） |
| `needs_review` | 1 | B2 Hood Summit 图（疑似 E3-006，跨页，需人工确认） |

## 广告排除（不进注册表）

- A13：整版 Operation Backpack 公益广告（~60 个图片碎片）
- B4：SailPoint 身份安全广告（9 个 tile）
- A7：NYC Wine & Food Festival 广告（1 张大图）

## 图表缺口（诚实标注）

B5/B6 市场数据页的图表为**矢量图形**（B5 有 3178 个 vector drawings），未提取为独立光栅资产。
标为 `unrecoverable`，原因明确。后续可按文章渲染矢量区域为 PNG。

## Planner 接入

`render/autonomous_planner.py`：
- `call_planner(..., assets=None)`：新增 assets 参数
- `load_assets_for_article(aid)`：从 asset_registry.json 取资产
- prompt 注入资产列表 + 约束："无资产时 L05/L08 不可选；有资产时必须评估是否使用，拒绝需给理由"
- `run_auto_test.py` 已同步传入 assets

资产通过参数传入，不硬编码。L05/L08 现可参与自主选择。

## 文件

- `render/asset_registry.json`：79 条资产登记
- `render/asset_coverage.json`：117 篇四分类
- `2026-10-12/assets/`：79 个 PNG 文件
