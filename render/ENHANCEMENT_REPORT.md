# Editorial Reading Enhancement · 验收报告（2026-10-13）

## 建成的系统（render/）
| 模块 | 实现 |
|---|---|
| source_model.py | 稳定段落 ID、原文/译文字符 range、只读源、caption 重复检测、editorial_added |
| text_treatment.py | T01 加粗（T07 限定词保护）/T03 数值/T06 引述归属/T09 拆分（可逆）/T10 分组/T11 小标题/T13 列表/T17 混排；exact match 门禁；接受零处理 |
| layout.py | L02 边注/L03 双栏/L05 图文并置/L08 跨栏图；1440+390 双状态；手机 DOM 顺序校验 |
| orchestrate.py | narrative_outline → 三层候选 → rejected_opportunities → plan_validate 兜底 |
| plan_validate.py | 日期/引文/credit 逐字校验（泛化测试中 2 次拦截编造） |

51 pattern 中实现 13 个 core（T×9 + L×4），9 个 Aid 复用已有组件。

## E1-025 三版本对照
- **Baseline**：原干净正文
- **Text Only**：2 编辑小标题 + 2 处语义加粗，无组件（v2 起内部审计标签不再渲染）
- **Full**：文字层 + 照片 + 引语 + 关键数字 + 时间线；图注重复与引语重复在上游修复
- 桌面/手机各 6 张截图，零溢出，手机阅读顺序正确

## 5 篇盲测（新文章，未参与训练）
| 文章 | 决策 | 评价 |
|---|---|---|
| E2-002 长文38段 | 5 小标题+T01/T03/T06+quote；拒绝 timeline/key_figures[2]（门禁拦截"250+"编造） | 节奏好，无过度强调 |
| E1-010 长文20段 | 20 treatments+key_figures+quote；拒绝 T09（不断因果链） | 克制 |
| E2-018 观点 | T01/T11+quote；拒绝 key_figures（观点无新闻价值数据） | 判断准确 |
| E1-015 短讯2段 | T01/T03+key_figures(35岁/40岁/12次)；拒绝 quote（间接引语） | 干净 |
| E2-012 数据表 | 零处理 + data_table | 正确 |

## 评分（1-5，按 kit 维度）
信息准确性 4（门禁拦截 2 次编造；E1-025 timeline "(p2)" 内部引用已修——渲染层自动剥离 (pN) 锚点）/
连续阅读 5 / 必要的强调 4 / 视觉组织 4 / 无重复 4（E1-025 两处已修）/
移动可读 5 / 编辑品味 4。

## 待办（进 117 篇生产前）
1. turn-to-page 跳页跟随（P1，跨页文章截断）
2. chart 双栏串扰清洗（P1）
3. planner prompt 强化（日期/引文/去重）
4. 批量 Plan 生成 + plan_validate 门禁接入生产管线
5. L02/L03/L08 尚无真实用例验证
