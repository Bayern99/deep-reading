# OvisOCR2 vs AnyDoc 实测对照（2026-10-13）

测试对象：WSJ 2026-10-12 真实 PDF 三页 —— page-0（A1 沙特长文）、page-22（B5 金融数据）、page-5（A6 新左翼捐款信息图）。
OvisOCR2-MLX-BF16 经 oMLX chat/completions 调用（temperature 0，150dpi PNG）；AnyDoc 为 `pip install firecrawl-anydoc` 后 `to_markdown`。

## 逐页结果

### A. page-0 普通长文
| | OvisOCR2 | AnyDoc |
|---|---|---|
| 正文完整性 | 6/6 关键句命中，阅读顺序正确 | 跨栏粘连（"Kenyan, Ethiopian Win Chicago Marathon" 并入行情条）、顺序错乱 |
| 断词 | 无 | 严重（"Busin ess & Financ e"、"in- cluding"） |
| **数值** | **DJIA 51654.95 → 1654.95（误读！与之前测试同一错误，2/2 复现）** | 51654.95 正确 |
| 速度 | 14.7s | 0.1s |

### B. page-22 金融数据页
| | OvisOCR2 | AnyDoc |
|---|---|---|
| 表格结构 | 好：markdown/HTML 表格，行列对齐 | 差：全塞进扁平表格 cell，无结构 |
| **数值准确率** | **多处掉数字**：77317.47→7731.47、1004.50→37.045.00、-1.03→1.031 | 图表头数字正确（51654.95/7811.54/54349.12） |
| 图表注释文字 | 未转录（只留 `<img bbox>` 占位，且 bbox 字符串损坏） | 碎片混入正文 |
| 坐标轴/图例/来源 | 丢失 | 丢失 |
| 速度 | 21.8s | 0.1s |

### C. page-5 复杂信息图（新左翼捐款）
| | OvisOCR2 | AnyDoc |
|---|---|---|
| 标题/副题 | 正确转录 | 正确转录 |
| 地图数据（$12.7M/$9.1M/图例） | **全部丢失**（img 占位） | 碎片捕获（"$12. 7m ill ion"、"Mic hi ga n"），无结构 |
| Note/Source（24 PACs/AdImpact） | 丢失 | 部分捕获（AdImpact） |
| QR 说明文字 | 丢失 | 捕获 "Scan this code" |

## 视觉资产
两引擎均不输出可用图片。已用 pymupdf 按区域 200dpi 裁图存 `visual-assets/`：
- `chart-dow-jones.png`（918×751，道琼斯 K 线+均线，清晰可用）
- `chart-sp500.png`（917×751）
- `infographic-newleft-donors.png`（1293×945，气泡地图+图例+Note/Source/QR，清晰可用）

**原则：图表文字 ≠ 图表本身。裁图是第一资产，文字转录只做索引，不许把图表文字混入正文。**

## 结论与推荐：组合路线，Ovis 为主

1. **正文主力 = OvisOCR2**：阅读顺序和版面结构明显更好，长文可直接用。
2. **数值必须过 QA**：Ovis 在小字号数字上有系统性掉字（DJIA 误读 2/2 复现；密表掉位）。**所有数字用 pdftotext 做交叉校验**，不一致的人工核对——这是硬门槛，不可跳过。
3. **AnyDoc 不进主流程**：数字虽准但结构全毁、断词严重；可留作数字交叉核对的第二意见。
4. **图表/信息图 = pymupdf 裁图 + 独立数据转录**：视觉资产单独保存，数据值人工或二次模型转录后进结构化字段，不进正文流。
5. Ovis 不遵循 `[HEADLINE]/[TABLE]` 等 tag 指令（输出 markdown+img 占位）：接受其原生输出格式，后处理解析，不要在 prompt 上死磕。

## 遗留风险
- Ovis 的数值错误是静默的（不报错），QA 交叉校验是唯一的防线。
- 信息图内的数据值（如各州气泡金额）目前只能靠人工从裁图读取，没有自动化方案。
- Ovis 21s/页 → 整本 26 页约 9 分钟，可接受。
