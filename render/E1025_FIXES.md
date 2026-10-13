# E1-025 已知问题修复说明（2026-10-13）

## 问题 1：图注与正文重复同一说明
**上游追查**：OCR 把印刷图注识别为正文段 p2（"上图：金伯利·吉尔福伊尔，上周三在希腊。下图：…"），
而 plan 的 figure 组件又带了相同的 caption_cn → 页面渲染两次。

**修复（上游，非 CSS 隐藏）**：
- `source_model.py` 新增 `caption_duplicate` 角色检测：段落文本与已注册图注相似度 ≥0.85
  且资产清单确认图存在时，标记为 `caption_duplicate`（E1-025 p2 相似度 1.0）。
- 渲染器正文流跳过该段；原文块保留在 source model 中可审计，未删除。
- full.html / text-only.html 中 p2 已消失，图注只在 figure 处出现一次。

## 问题 2：引语在正文与 quote 模块重复
**上游追查**：plan 的 quote 全文 89 字与正文 p11 逐字相同（整个段落就是引语）。

**修复（上游）**：
- `orchestrate.py::dedup_quote`：quote 与正文逐字重复时，缩减为首个直接引语单句
  （"我要和他一起飞往巴黎。"），plan 中记录 `dedup_note` 说明编辑理由。
- 符合已批准的 AJ 引语规范（直接引语一句）与 kit"引用展示需充分编辑理由"。

## 附加发现（plan_validate 门禁实测）
- E1-025 增强 plan：通过（"2026年1月"属合理推断，2026 在源中有据）。
- E1-034 原 plan：拦截 3 处编造年份（"Feb 2024"等）+ 1 处编造 credit（"Social Media Video"，
  agent 之前漏掉的）。
