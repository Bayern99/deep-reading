# 泛化能力测试报告（2026-10-13）

## 范围
11 篇此前未用于设计/调试的文章：长文 4（E1-004/E2-010/E1-025/E1-034）、观点 2（E2-017/E3-032）、
短讯 2（E3-034/E1-014）、数据表 1（E1-002）、图注 1（E1-003）、读者来信 1（E2-024）。
Pipeline：PDF → OvisOCR2 → 数字交叉校验 → Hy-MT2 → 通用 Planner（同一 prompt，零硬编码）→ plan_render。
产物：`gen-test/<ID>/`（ocr.json / translation.json / assets+manifest / plan.json / article.html / shot-d.png / shot-m.png）。

## 结果：11/11 跑通，编辑表达各不相同
| 文章 | Plan 组件 | 评价 |
|---|---|---|
| E1-025 达沃斯 | figure+quote+key_figures+timeline | 富编辑页，照片/引语/数字/时间线齐全且位置合理 |
| E3-032 建商 | figure+6数字+quote+chart+timeline | 最复杂，图表恢复成功 |
| E2-017 AI 观点 | quote+key_figures | 干净的观点页 |
| E1-004/E2-010/E1-034 | quote（+数字/时间线） | 标准长文页 |
| E1-002 | data_table | 纯表 |
| E1-003 | figure+key_figures | 图+数字 |
| E1-014/E2-024 | 0 组件 | 干净页（规则未触发，合法） |

Planner 的正面行为：E3-034 归属存疑的折线图被正确拒绝；E2-017 书封图因无 img 标记被排除。

## 发现的问题（初次生成，未经修饰）

**P0（事实错误）：**
1. E1-034 timeline 编造年份：原文 "February" → Plan 写 "2024年2月"。已修：`render/plan_validate.py`
   自动校验（日期/引文必须原文逐字出现），实测连 agent 漏掉的另一处编造 credit 也抓出。

**P1（内容缺失/串扰）：**
2. 跨页文章被截断：E1-004 5/24 段、E2-010 5/16 段（"turn to page" 跳页未跟随）。待实现：OCR 阶段识别跳页标记并提取后续页。
3. E3-032 图表后混入双栏 OCR 乱码英文段。待修：chart caption 清洗 + 双栏串扰检测。

**P2（质量瑕疵，已修）：**
4. figure credit 编造（E1-003 "AJ Photo"）：credit 改为可选，为空不渲染。`plan_validate.py` 同步拦截。
5. chart "数据来源：Source:" 重复：`components.py` 去重逻辑。
6. E1-034 quote 标点被改：校验器拦截（引文逐字规则）。
7. E2-010 quote 取两句、E1-025 图注与正文重复：planner prompt 待强化。
8. OCR 人名错误传播（Jutreson/Jevens）：QA 拦截待加强。
9. 模板与 schema 5 处不一致：归一化层待沉淀为正式逻辑。

## 模型结论
- OvisOCR2：正文主力可用，但数字静默掉字是硬伤，pdftotext 交叉校验是强制门槛。
- Hy-MT2：翻译质量通过（8 段抽查，人名数字引语忠实，约 2 秒/段）。
- Planner（Qwen3.8）：组件选择逻辑正确率高，但事实层会编造——必须配 `plan_validate.py` 做门禁。

## 待办
1. turn-to-page 跳页跟随（P1）
2. chart 双栏串扰清洗（P1）
3. 批量 Plan 生成流程（117 篇规模化）
4. planner prompt 强化（日期/引文/去重规则）
