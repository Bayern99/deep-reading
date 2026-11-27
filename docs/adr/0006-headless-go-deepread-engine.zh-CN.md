# ADR 0006：无头 Go 深读能力引擎（`deepread`）

- **状态：** 已采纳
- **日期：** 2026-11-26
- **取代：** [ADR 0001](0001-three-tier-editorial-composition.zh-CN.md)、[ADR 0002](0002-issue-artifact-only-product.zh-CN.md)、[ADR 0003](0003-derived-article-map.zh-CN.md)、[ADR 0004](0004-page-column-grid-not-story-regions.zh-CN.md)、[ADR 0005](0005-paragraph-boundaries-from-printed-indents.zh-CN.md)
- **公开历史重置：** 在仓库公开前，包含私有报刊测试产物的旧版 v1 Python 历史提交已从公开 Git 历史中剥离并离线归档。

## 背景

v1 Python 流水线（约 9,500 行）将绝大部分工程成本消耗在印刷大版面 PDF 的几何切片与续页考古上，并把所有文章硬塞进固定模板与 4 种静态 SVG。与此同时，新一代云电脑 Agent（Muse、群机器人、Coding Agent Harness）本身已具备强大的理解与 Shell 执行能力，读者对数字长文（Markdown、EPUB）的核心需求转向手机浏览器直读与本机 `Mark Go Go` 协同批注。

## 决策

1. **转向无头纯 Go 单二进制能力层（`deepread`）+ `SKILL.md`。**  
   `deepread` 不内置 LLM 编排、不管理模型密钥、零 GUI、零 CGO（`CGO_ENABLED=0`）。宿主 Agent 负责编辑判断与生成，`deepread` 负责确定性吞入、结构检视、严格校验、CAS 局部补丁与零 JS 移动 HTML 导出。
2. **Prose-by-Reference 与确定性反平庸护栏。**  
   原文段落保持原样。`write` 与 `patch` 强制执行收窄的 10 原语静态阅读子集（`Col`、`Source`、`Title`、`Text`、`Caption`、`Quote`、`List`、`ListItem`、`Table`、`Chart` 柱/折线）、零容错校验、顶层单节 `Source` 拓扑、拒绝纯文字摘要与卡片仪表盘；0 模块（`root = Col([])`）合法且受鼓励。
3. **与 `Mark Go Go` v3（`f203c83`）严格单向兼容。**  
   在零修改上游仓库的前提下同步纯 Go 无头包（`openuilang`、`genuikit`、`markdown`，归属见 [UPSTREAM.md](../../UPSTREAM.md)）。侧文件严格遵循 `version: 3`、`language: "openui-lang/1.0"`、`catalogId: "markgogo.dev:genui/v3"`、`.genui.prev.json` 撤销备份、`fnv1a32` 节哈希与属性化行内批注 `<!-- note ... -->`；每次 `patch` 均压实为单条 `createSurface` 以远离 1 MiB 上限。
4. **单目录单文档隔离与 EPUB 两阶段吞入。**  
   每篇文章或 EPUB 章节独占一个目录（`chapters/<NN>-<slug>/chapter.md`、`assets/`、`.deepread/`），配套文件锁、批注账本（`.deepread/ledger.json`）与历史快照（`.deepread/history/`）。`export` 输出零 JS、390px 优先杂志级 HTML 与始终可见短码（`<bundleId>·<statement>@r<rev>`），同时支持带硬体积预算的单文件内联模式与 `--external-assets` 外链目录托管模式。

## 后果

- 仓库彻底移除 Python 运行依赖、印刷 PDF 版面解析器与硬编码 WSJ 模板。
- 历史 ADR 0001–0005 保留在 `docs/adr/` 供架构演进参考，旧版 v1 Python 代码改为离线归档。
- 使用标准 Go 工具链即可静态交叉编译 `darwin/arm64`、`linux/amd64`、`linux/arm64`、`windows/amd64` 单文件二进制。
