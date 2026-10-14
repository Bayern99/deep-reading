# B · Product & Contract Definition

状态：2026-10-14 按 Product Convergence 任务收缩第一版范围。下方“第一版实施边界”优先于后面的扩展协议草案；原审计思想保留为参考，不能作为必须一次实现的清单。当前实现与证据见 [本轮交付](../convergence-2026-10-13/DELIVERY.md)，原始差距见 [A](A-ARCHITECTURE-AUDIT.md)。

## 1. 产品边界

> A portable, evidence-grounded Editorial Reading Engine that measurably improves the reading experience of existing content without compromising its integrity.

Engine 输入为结构化文章及来源/资产证据，输出为独立 Editorial Plan、依设计系统实现的阅读页面、可复核的完整性与阅读评测记录。

WSJ 深读是第一个完整实例。MVP 支持当前期刊中的文章、观点、短讯、来信、更正、新闻摘要、图注和可确认的数据表，保留本产品的整期导航、双语切换与编辑身份。不预先实现第二个产品、编辑器、CMS、协同编辑或发布平台。

### 责任

| 属于 Engine | 可替换 Input Adapters | 当前不做 |
|---|---|---|
| 内容/来源/资产关系的统一表达 | PDF、OCR、HTML/JSON 导入 | 通用 CMS、多人编辑器 |
| 理解报道结构与读者困难 | 翻译、术语对齐、图片恢复 | 多 Agent Framework、任务队列服务 |
| 比较保留/强调/组织/辅助方案 | OvisOCR2、Hy-MT2 实现 | 任意主题摘要平台、跨媒体发布平台 |
| 按 WSJ 设计系统排版与编排 | 未来更换模型的同协议输出 | 51 个 Pattern 全实现 |
| 完整性、执行情况与阅读收益证据 | 输入缓存与原始响应归档 | 在无原始数据时生成替代图表 |

OvisOCR2 与 Hy-MT2 是已选定的 WSJ 前置方案；不重新争论该选择，也不假定当前整期定稿已经由它们生成。已经结构化的文章直接进入 Engine，无需 PDF、OCR、翻译 Provider 或 Harness 的私有配置。

“完整”包括输入保管完整、发布范围明确、引用对应正确；不要求把印刷广告/索引全塞进正文。排除、保留但不展示、待审核必须有独立记录。缺失证据不得转换成“完整性通过”。

## 第一版实施边界：Required 与 Deferred

核心只接收 **Structured Content + Source Evidence + Visual Assets**。OvisOCR2／Hy-MT2 保留在 WSJ 输入侧；结构化输入可直接渲染，核心不要求模型服务器、OCR、翻译或 Harness。先复用当前 Python 文件协议和正式 CLI，不实现通用输入 Adapter。

| Required for correctness | 第一版采用的最小办法 |
|---|---|
| 内容与来源可取得、正文不丢失 | 保留原始结构化快照；统一只读正文投影；每个语言独立完整；已确认的续页/合段修复有显式记录 |
| 引用不能悄悄错位 | 内容整体 fingerprint + block 引用；片段逐字且唯一命中；未知/冲突目标明确失败。当前 pN 仅在固定 snapshot 内有效，不声称它是跨更新持久 ID |
| 内容与 Plan 独立复用 | 定稿不嵌排版判断，Plan 单独文件；允许同一内容的 preserve 和探索方案；接受外部生成计划 |
| 编辑操作可复核 | 每个接受的文字/布局/辅助操作有目标、理由及执行回执；仅支持已实现的操作；不以通用 span 冒充未知模式已执行 |
| Preserve 与失败不同 | 无操作调用同一类型 Renderer；正文、导语、署名、资产不变；执行失败记录 failed，不制造 preserve |
| 新增内容和资产有证据 | 每篇实际采用的解释/比较记录原文位置或外部来源；真实图像、图注与署名随同一输入进入两版；不造图表 |
| 可重放与可比较 | 同一 CLI／Renderer／CSS 基础，保存输入与计划；正文完整性结果和具体页面分开评价 |

新增结构化内容需要使用并保存上游 block keys，或在第一次导入一次分配 IDs；未来更新同一内容应沿用这些 IDs。**P0 不迁移整期历史编号**：先用整体 fingerprint 阻止旧计划应用到改过的 snapshot，任何编辑均重新明确绑定。它是安全的当前界限，不是自动跨版本迁移功能。

本轮允许的小型阅读处理只表达实际需要的字体角色和语义停顿，使用固定设计 profile 与已存在的正文锚点；不新增一套 Renderer 或组件目录。不同语言的节奏目标可分别记录，不通过等段数假造对齐。

**Deferred / 参考草案**：完整 semantic version 治理、严格跨语言 JCS、逐块 revision 层、自动 plan rebasing、split/merge lineage、迁移框架、所有输入类型的 Adapter、完整操作词汇、CMS 与多层 Validator。下面原有 `reading.content/plan/render` 字段表、MVP 操作表与更新迁移流程属于这些参考，不是本轮交付要求。

当前 fingerprint 只需 Python 明确 JSON 序列化规则和 SHA-256；不新增签名库。持久身份、整体 snapshot 与执行结果承担不同责任，但不必为每个责任创建服务。

## 2. 当前契约的六个断点

1. `final.json` 为长字符串，没有持久块 ID、来源 revision、媒体关系或双语 alignment。
2. SourceModel 是渲染时重新创建的视图；`p1` 在某实验是标题，在正式路径是正文首段。
3. 现有 Schema、六段式 Planner、`0.2-enh`、`enhanced-v1` 语义不一致。
4. `analysis` 与 `reason` 多为文字解释，缺少类型化的证据绑定；辅助事实来源经常未记录。
5. 计划中 L05/L08 可以携带 `img_html`、`inner_html`；AI 决策仍可进入 HTML 层。
6. 同一 content + 空计划会改变 metadata、英语修复和部分内容行为；没有忠实且公平的共同底稿。

要建立一个“小而稳定”的契约，先把这些断点接起来，不另造一个更丰富的模型系统。

## 3. 协议设计原则

- JSON、UTF-8；协议字段为英语，locale 使用 BCP 47（`en`、`zh-CN`），不继续把 `cn` 与语言代码混用。
- 内容、编辑判断、设计实现分别版本化；不把 CSS、类名、HTML、固定断行或文章 ID 分支写进 Plan。
- 原始文本保持输入中的 Unicode 字符、标点、空白和顺序；Adapter 若做修复，另存修复结果与来源关系，不覆盖原始快照。
- 稳定 ID 表示身份，hash 表示当前内容；两者不能互相替代。
- 允许一对多/多对一双语映射，也允许未翻译；不强求同段数，不默默丢弃较长的一方。
- 未支持的协议版本或操作明确失败。缺失计划、主动不干预、Planner 失败、计划过期是不同状态。
- Source 数据与 Content 放在一个 ArticlePackage 中，共享本地文件清单；不新增 Source 服务。

MVP 只需三个外部契约：`ArticlePackage`、`EditorialPlan`、`RenderResult`。运行日志和整期 selection 是出版/工作流记录，不能混进正文与模型判断。

## 4. ArticlePackage：`reading.content/1.0`

### 顶层与来源

| 字段 | 类型/约束 | 目的 |
|---|---|---|
| `schema_version` | 固定字符串 `reading.content/1.0` | 明确兼容范围 |
| `article_id` | 持久字符串；本地 import map 保留原 E-ID 与本期作用域 | 不因重排、改字或模型更换改变 |
| `revision` | 完整 SHA-256 标识 | 绑定可重放快照 |
| `metadata` | 标题/导语的 locale→block_id，byline 原字串及 source_refs；publisher、issue、section、type | 元数据同样保持来源与无干预等价 |
| `sources[]` | 下表 SourceRecord | 保存来源与可验证程度 |
| `blocks[]` | 下表 ContentBlock | 定稿与结构，不承载新编辑意见 |
| `body_order` | locale→有序 block_id 数组 | 两个语言各自完整的阅读顺序 |
| `alignments[]` | 下表 Alignment | 双语对应关系 |
| `assets[]` | 下表 AssetRecord | 原始视觉证据与状态 |
| `input_issues[]` | code、目标 ID、severity、证据、处置状态 | 原稿缺失、续文未确认等事实 |

SourceRecord：`source_id`、`kind`（structured_snapshot/ocr_snapshot/original_document/external_reference）、`uri`（包内相对路径或原始 URL）、`sha256`（可取得快照时）、`publisher`、`locator`（可选页码/区域/段落标识）、`verification`（verified/unverified/missing）。

PDF 页码与 bbox 仅为可选 locator；若存在 bbox，必须带单位、坐标原点和参照页/图尺寸。纯结构化输入可引用自己的快照和 block key，不需要假造 PDF 定位。URL 不是事实认证；被引用新增事实应保存可读摘录、取得日期与快照位置。

源 PDF 不在仓库时，旧数据只声明 `raw.txt → merged.json → final.json` 等可取得的链及其快照 hash；不得补一个虚构的原报 verified 标签。

### 文本块与双语

ContentBlock 的最小结构：

| 字段 | 约束 |
|---|---|
| `block_id` | 导入时一次分配/沿用可信上游 key，以后持久保存；禁止按当次数组序号重建 |
| `locale` | `en` / `zh-CN` |
| `kind` | title、dek、paragraph、source_heading、caption、list_item、table |
| `text` | 文本块的精确原字符串；table 使用显式 cells/列头结构，不能把扁平 OCR 当作已恢复真表 |
| `revision` | 文本/类型/可用表格结构的完整 SHA-256 |
| `source_refs` | source_id + 可选 locator/range；至少指向已保存的输入快照 |

英文块与中文块是分别持久的对象。`Alignment` 包含 `alignment_id`、`source_block_ids[]`、`target_block_ids[]`、`status`（verified/unverified/untranslated）、可选 `method` 与验证记录；允许多个 block 组成一个映射。标题/导语也可使用同一映射机制。

未对齐不自动隐藏正文：两边仍按自己的 body_order 输出。需要同步定位时仅使用 verified alignment。双语引语必须有同一对应片段的证据，长度比例只可提示异常，不能认证同源。

原始小标题的 kind 来自结构化来源或显式修复记录；Renderer 不再用“短、无句号”推断它。原文图注保留为 caption，与 asset 绑定；重复 OCR 的非正文投影由 importer 记录，不在 Renderer 里凭相似度删除。

### 视觉资产

AssetRecord：`asset_id`、`kind`（photo/chart/infographic/table）、`file`（包内相对路径）、`media_type`、`sha256`、`width/height`、`source_refs`、`caption_refs`、`credit`、`verification`、`unavailable_reason`（缺失时）。

- 提取成功与 verified 分开，分别记录归属、完整裁切、图注/credit 是否确认。
- 缺 credit 用 unknown 状态和问题记录，不自动编造摄影师；是否可发布由 WSJ policy 明示。
- 保存图表轴、单位、时间区间和相关来源说明；不把“数据图”统一标 photo。
- 只保留已经确认的文章关系。几何近邻关联是待审核候选。
- 资产未知或丢失时，可忠实呈现“缺失”状态，不能静默用 LLM 图形代替。

### Revision 与兼容规则

- Source/asset 的 `sha256` 为原始文件字节 hash；内容 revision 由 importer/Engine 计算，模型只引用收到的值。
- Block revision = SHA-256(JCS({locale, kind, text 或 cells}))；ArticlePackage revision = SHA-256(JCS(去除顶层 revision 的完整协议对象))。使用 [RFC 8785 JCS](https://www.rfc-editor.org/rfc/rfc8785) 的 UTF-8 字节；原文本字符串不做 Unicode/空白 normalize，数组顺序保留。运行时间、绝对缓存根目录、Provider 日志放在包外，避免无关变动失效。
- 数字事实仍保存源字串（包括单位），精确小数/大整数不经浮点改写。坐标和 Selector 的整数约束在协议边界明确检查。
- v1.0 顶层及操作对象拒绝未知字段与未知 type；空 decisions 是合法 preserve，不是缺字段。扩展必须使用明确的新协议版本，由 importer 显式转换，不靠默认值悄悄解释。
- 同一 ArticlePackage 内 block/asset/source/alignment ID 唯一；所有 body_order、metadata、alignment 和 Plan 引用解析到对应对象。结构校验与引用解析各做一次，后续执行消费解析结果。
- 身份不由 revision 推导；从另一目录搬移同一包时内部相对 URI 不改变，内容 revision 不变。文件格式化/JSON 对象键顺序变化也不改变 JCS revision。

## 5. EditorialPlan：`reading.plan/1.0`

| 字段 | 约束 |
|---|---|
| `schema_version` | 固定 `reading.plan/1.0` |
| `plan_id` | 唯一 ID；不同编辑方案可并存 |
| `article_id`、`content_revision` | 绑定 ArticlePackage 快照 |
| `producer` | human / model；可记录 model/provider、prompt hash、参数、原始输出引用；Harness 仅为运行元数据 |
| `policy_version` | 编辑规则/知识卡版本；不绑定 CSS |
| `outcome` | `intervene` / `preserve`，必须明确 |
| `understanding` | topic、reader_need、叙事单元 block_refs 与功能、重要限制；可简短，不要求长篇“思考报告” |
| `decisions[]` | 类型化操作，每项含目标、证据、阅读目标与代价 |
| `declined[]` | 真正评估过的候选与拒绝理由；不要求对全部 Pattern 填表 |

`preserve` 要求 decisions 为空，并说明为什么原文已足够。Planner 调用失败不生成 preserve Plan；运行状态记 failed，若出版策略允许忠实 Baseline，则另记 fallback，没有“AI 已审核”标记。

### Selector：所有引用的共同规则

`block_id` + `block_revision`；若选择片段，再加 `locale`、`start`、`end`、`exact`。

- `[start,end)` 为原始字符串中的 Unicode code point 偏移，不是 UTF-8 字节、JS UTF-16 索引或转义后 HTML 的偏移。
- `text[start:end] == exact`，不得 normalize 或模糊匹配；重复文本靠范围消歧。
- 验证后按原字符切片，再逐片 escape。跨越冲突的强调范围应拒绝；允许的嵌套关系由固定 renderer 规则定义。
- 所有 block/asset/source 引用必须解析；不能把找不到目标当作成功执行。

### MVP 操作词汇

| `type` | 数据 | 模型/编辑判断 | Renderer 责任 |
|---|---|---|---|
| `emphasis` | Selector，role=claim/number/attribution | 哪一句/数字/归属真正有用，保留限定与否定 | 固定字体与有限强调样式 |
| `headline_phrase` | 标题 Selector | 哪个短词组值得保护 | 响应式保护，窄屏允许自然回流 |
| `group` | 连续 block_refs | 哪些段落属于同一叙事单元 | 留白，不重排、不改字 |
| `section_label` | before_block_id，localized added_text，evidence | 是否缺路标、标题是否忠实 | 固定层级；区分新增与源 heading |
| `note` | anchor block、localized added_text、外部或原文 evidence | 是否有理解困难、事实能否验证 | 边注/手机 inline，顺序固定 |
| `comparison` | 同维度 rows、两个具名对象、各值 evidence，after block | 是否真是可比关系，单位/范围是否一致 | 桌面并排，手机逐维度；EN 标签也完整 |
| `asset_placement` | asset_id，相关 block，relationship=evidence/explanation，prominence=body/wide | 原始资产为何有用、放哪里 | 生成图/图注/横滑；不接收 HTML |
| `reading_aid` | kind=figures/timeline/quote；类型化 items，每个事实带 evidence，position | 新视角是否抵得上重复/打断成本 | 固定组件，输出来源关系与新增标记 |

T09 段落拆分与 T13 列表化暂 DEFER。若未来启用，必须定义保留空白/标点的双语分片语义并证明可逆，不能把当前未执行操作当作已支持。

每条 decision 需要 `decision_id`、`reason`（具体 reader_need）、`evidence[]`、`benefit`、`cost`。新增文字用 `added_text` 保存，永不写回 ContentBlock。逐字 excerpt 用 Selector，不能用 copied string 假装新增事实有来源。

comparison 中对象要有名称（如 10 月调查/7 月调查），不能仅把 A/B 图形标签当作对象身份。单位与预测区间来自证据；原文没有的数据不得补齐。

计划禁止 `html`、`css`、`img_html`、`inner_html`、className、像素坐标、固定 `<br>` 和任意 `params`。编辑协议表达阅读关系；设计 profile 决定实现。新增事实无来源时，draft 可以记录待核验，accepted Plan 必须拒绝。

## 6. RenderResult：`reading.render/1.0`

字段：`schema_version`、`article_id`、`content_revision`、`plan_id`（Baseline 为 null）、`renderer_version`、`design_profile_version`、`output_files` 与 hash、`operation_receipts[]`、`integrity_result`、`issues[]`、`status`。

operation_receipt：decision_id、resolved_targets、applied/failed、具体诊断。对 accepted Plan 不允许 silent skipped；不支持操作整体不发布增强产物。若允许退回 Baseline，记录明确失败与 fallback 来源。

完整性结果至少列：

- 各语言原文块实际输出一次、顺序与精确字符串一致；独立附加 excerpt 不混入正文计数。
- 元数据、数字/单位、双语关联、源标题与资产身份保持正确。
- 被排除/未展示项及理由、已知上游问题，没有用输出存在替代来源认证。
- Plan 全部引用解析、全部 accepted 操作生效、新文字有证据、正文未被改写。

RenderResult 只能报告呈现与完整性事实，不能自动声称 reading_quality improved。阅读评测是独立结果，按内容/计划/Renderer/设计版本关联，见 D。

## 7. 内容更新与映射稳定性

1. 初次导入保存原快照，分配 ID，保存 legacy→persistent 的 import map。
2. 标题、段落插入/重排不会重编已有 block_id；重复段落也有独立身份，不能只靠文字 hash。
3. 改字保留 block_id，更新 block revision；明确 split/merge 的 replacement 关系，不静默复用原范围。
4. Plan 绑定旧 content_revision。变化后先找目标块 revision 是否仍相同；不改动的引用可作为复用候选，受影响目标必须重判。
5. 自动精确重定位只对唯一匹配并经过 review 的迁移候选生效，产生新 plan_id 和迁移记录；旧 Plan 不覆盖。
6. 内容变化即使在未引用段落，也可能改变整体结论。稳定锚点只减少机械重建，不能证明原编辑判断仍正确。

一次迁移允许给旧 pN 分配持久 ID；此后禁止重新编号。修改正文与布局变化必须分清，避免改变翻译后无故使全部编辑关系漂移。

## 8. 与成熟结构化内容方案比较

| 方案 | 可借鉴 | 本项目缺口与成本 | 决定 |
|---|---|---|---|
| [Portable Text](https://github.com/portabletext/portabletext) | block/span、独立 markDefs、custom asset objects、与 HTML 无关的序列化 | 仍需额外双语 alignment、来源、revision、独立 Plan；完整格式引入 children/marks 重写与依赖 | 借思想，暂不全量采用 |
| [ProseMirror](https://prosemirror.net/docs/guide/#doc) | 受 Schema 限制的节点/marks、不可变文档、transaction/position mapping | 核心用途为编辑器；位置变化需要 transform mappings，不能自然替代持久来源 ID；目前无在线编辑需求 | 不引入编辑器运行时 |
| [Sanity keyed arrays](https://www.sanity.io/docs/studio/array-type) | 持久 `_key` 可在重排时仍引用原对象；来源与资产引用 | CMS 存储、Studio、协同/查询对当前文件出版无必要收益 | 使用持久 key 原则，暂不引入 CMS |
| 最小 JSON ArticlePackage + 独立 Plan | 与现有 Python/文件交付吻合；无需 UI 编辑平台 | 需定义引用规则、一次 legacy 迁移、语义测试 | 当前推荐 |

Portable Text 官方规范目前 README 自称 working draft；不能因名字 Portable 就假定它已解决本文的证据与双语问题。ProseMirror 可参考的 position mapping 同样不等于来源身份稳定。

## 9. WSJ 整期出版与成功定义

每期独立 edition manifest 保留 date/front/ordered article refs、显式 exclude 与 unresolved 状态、WSJ profile。图片、数据策展和 plans 属于该期；Engine 不再读取上一期全局 article_id 数据。

一个结构化文章不带 edition manifest 也能产生忠实阅读页。多文章整期包装复用同一 Renderer，只增加头版、栏目和导航。

契约成功不以 Schema PASS 定义，而以这些行为定义：同内容可并存多个 Plan；空 Plan 与 Baseline 同正文同元数据同来源；同 Plan 能被符合能力的其他 Renderer 理解；其他 Provider/Harness 输出同协议可进入相同流程；更新不重编号；所有已执行决策有回执；最终阅读收益能被单独测量。
