# 内容分析（01-analysis.md）— WSJ 2026-10-12（周一）

## 本期核心线

1. **特朗普 vs 俄罗斯能源**（A1 主新闻）：特朗普推动俄乌能源基础设施停火，同时允许俄罗斯石油进入美国及世界市场，国会两党反弹，参议员称其出口计划"非法"。
2. **沙特王储困境**（A1）：胡塞武装打击加重沙特负担，Neom 等大项目承压。
3. **赫格塞斯直播行刑争议**（A5）：国防部长 Hegseth 因直播行刑队画面受抨击。
4. **亚马逊拟约 70 亿美元收购 AI 初创 Decart**（B1，商业头条）。
5. **AI 泡沫论**（A15 Kessler 专栏《How the AI Boom Ends》+ B 版多篇 AI 报道呼应）：token 价格暴跌、数据中心债务风险。
6. **预测市场蔓延到刑事审判**（A1）：Polymarket 对 Lindsay Clancy 谋杀案开盘，冲击司法系统。
7. **私人信贷**（A1/A10）：美国人储蓄助燃私人信贷扩张。

## 文本档位

- **新闻（A/B 版）= 偏硬文本**：准确 > 流畅。数字、归因、职务头衔必须精确；hedge（may/might/could/表示"可能"的措辞）是内容，不得为短句删掉。
- **观点/评论（Opinion/Review/Heard）= 可稍软**：保留作者语气与修辞（如 Kessler 的专栏笔法、社论的讽刺），但事实核查标准不变。
- **Personal Journal/体育/艺术**：生活化文本，流畅优先，但专名数字仍硬。
- **数据表/图片说明/简讯**：只译标题与说明句，数据表本体保留英文原文进附录。

## 翻译难点

1. **分栏重建后的断句**：抽取时已按栏重建，个别 B 版印刷碎片（E3-002、E3-004、E3-009）在 body_en 中如实标注，翻译时照原文译，不脑补缺失成分，必要时 notes 说明。
2. **政治讽刺标题**：如 "Trump's Diesel Insult to Lindsey Graham"（柴油梗），直译保留意象，context 解释。
3. **新词**：fusionism（融合主义）、DebtTok、Sunday Scaries（周日恐慌/周日夜晚焦虑）、Neom。
4. **人名音译**：以冻结术语表 glossary.json 为准；表内标"待查"的，复核阶段核验，音译不一致是重点检查项（如教宗良十四世已冻结，不要出现"利奥十四世"）。
5. **数字**：10 年期国债收益率 5.243%、油价 $91.85 等，中英必须逐数比对（build-checklist 第 2 条）。

## 术语表

已冻结：glossary.md / glossary.json（511 条）。翻译注入时按条目自带 terms 列表取子集传入
`translate-gemma.py --glossary`。复核发现的新实体/别名/冲突记入各 batch 的 notes，
QA 后回流 living glossary（~/workspace/deep-read/glossary-db.md，本期新建播种）。
