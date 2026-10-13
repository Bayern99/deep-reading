# Architecture Recovery Audit（2026-10-13）

## 核心结论（先说最重要的）

1. **"Editorial Intelligence" 作为具名能力从未存在过**——代码、数据、文档三路审计一致：所有内容理解/编辑决策都是 Juno 在写 `build_r3_1.py` 时手工完成的（仅 E1-005、E3-002 两篇），决策固化在单篇硬编码里。Phase 4/5 是**新建**，不是恢复。
2. **真正丢失、可恢复的是渲染原语**：`bargraph`（12%→6% 柱状图）、`em()` 正文数字高亮、单篇任意模块排布——都在 `cases/build_r3*.py` 里，代码完好。
3. **真正的断点在提取**：政治捐款信息图（E1-033）在 `pdftotext` 阶段已永久丢失视觉信息；道琼斯图表从未实现过（一直是纯表格）。
4. **AnyDoc 不可用**：在真实 WSJ PDF 上实测，四个硬伤（见下）。Phase 2 必须换路线。
5. **Hy-MT2 未部署**：oMLX 12 个模型中没有它，无模型管理接口。Phase 3 阻塞，需 Jerry 在 Mac Studio 部署。

## 分项审计

### 曾实际实现（可恢复）
| 能力 | 位置 | 状态 |
|---|---|---|
| 17 个渲染组件生成器（stat_strip/timeline/pullquote/bargraph/compare_duel 等） | cases/build_r3.py, build_r3_1.py | 代码完好，未移植到 render/ |
| 12%→6% CSS 柱状图 | build_r3_1.py::bargraph | 单篇硬编码，可泛化 |
| EV 充电桩月度图 | PDF 裁图嵌入 | 一次性人工操作，有记录 |
| 术语表→翻译→QA 管线 | skills/translate, translate-gemma.py | 生产中，非编辑智能 |
| context_cn/context_attr（12 篇） | final.json | 唯一的编辑元数据，翻译/QA 阶段 condensed |

### 手写单篇策展（非系统）
- build_r3_1.py：4 个关键数字、7 条时间线（段落号句子号人工指定）、主张/现实、引语+署名、柱状图数据——全硬编码，仅 E1-005/E3-002。
- `render/modules.json` 只是把同一批手写数据换了容器（仍只有 E1-005）。

### 从未实现（只讨论过）
- Editorial Intelligence / Editorial Plan JSON / 组件选择逻辑：零代码。
- 道琼斯图表：从未实现。
- 系统化视觉资产流程：不存在；assets/ 图片与文章无机器可读映射。

### 主动删除（非丢失）
- `compare_duel`（"主张与现实"）：经设计决策删除，不恢复。

## AnyDoc 实测结论（anydoc-eval.md）

在真实 WSJ PDF（26 页）上 `pip install firecrawl-anydoc` 实测：
1. **PDF 不提图片/图表**：源码注释明示 PDF bypass document model，直接输出 Markdown，`document.assets` 对 PDF 不存在——零图片引用。
2. **报纸版面质量差**：头版整页被误判成表格；"Governmentstack" 类跨栏粘连词；不如现有 pdftotext。
3. **鲁棒性差**：第 10 页一个坏 content stream 导致整本 26 页解析失败。
4. **无结构化输出**：只有扁平 Markdown，没有 Content Model。

**建议路线**：pdftotext -layout 继续做文本骨干（已验证）+ pymupdf 按页提图片 XObject + 针对验证案例做视觉恢复。MinerU 是更接近的备选（有版面模型+JSON+图片），代价是 GPU 与速度。

## 对 Phase 2–7 的含义

- Phase 2：AnyDoc 出局 → 改走"pdftotext + pymupdf 视觉资产恢复"路线；两个验证案例（道琼斯图表、捐款信息图）从 PDF 页面直接恢复。
- Phase 3：阻塞，等 Hy-MT2 部署。
- Phase 4/5：新建 Editorial Plan schema + 组件注册表；E1-005/E3-002 手工策展作为种子样本。
- Phase 6/7：按原计划，AJ×WIRED 设计基准不动。
