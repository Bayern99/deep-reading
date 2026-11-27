# DeepRead（`deepread`）

[English README](README.md) · [宿主 Agent 手册（`SKILL.md`）](SKILL.md) · [ADR 0006](docs/adr/0006-headless-go-deepread-engine.zh-CN.md) · [ADR 0007](docs/adr/0007-dual-face-genui-and-translation-layer.zh-CN.md)

一套无头、纯 Go 单二进制的长文深读能力层与 Agent 技能，面向 Markdown 与 EPUB 长文。专为由 AI Agent（云电脑、Muse、群机器人、Claude Code、Codex、Pi、Antigravity 等）自主安装与调用而设计：交付**一份**离线 HTML 阅读器——正面默认是**去文字墙、全信息量结构化精读画布**（`dual` 默认，保留约 95%+ 原文事实、人物案例、原声金句与原刊图表，结合胶囊标签要点、因果 SVG、可交互滑块/切换、对比表与时间线），背面是逐字节不可变的完整原文与并行翻译层（`中文 / EN / 双语` 一键切换，每幕支持 `查看原文 ↗` / `预览`）；同时提供 `--face inline`（段落级交错互动长文）与 `--face hybrid`（篇首导览画布 + 段落级伴读），保持与 `Mark Go Go` v3 磁盘格式的单向兼容。

> 本仓库自 `v0.2.0` 起采用全新的纯 Go 架构实现，取代早期已退役的 Python 原型；`v0.3.0` 增加翻译层、canvas 画布与整书单文件导出。

---

## 给人类用户：直接把下面这段提示词发给你的 Agent / 云电脑

你不需要手动装环境或敲命令。直接复制下面这段话，发给你的云电脑 Agent 或编程 Agent：

```text
请在这台机器上帮我安装并配置 `deepread`（仓库地址：https://github.com/Bayern99/deep-reading）。
请阅读仓库 README，并严格按「给 Agent 的自安装与自检手册」执行：
1. 从最新 GitHub Release 下载对应系统架构的 `deepread` 静态二进制（校验 SHA-256）并放入 PATH。
2. 把 `SKILL.md` 原样安装到你当前生效的 skills 目录，以便后续会话直接调用。
3. 在临时目录跑通冒烟自检，并在验证通过后清理临时目录。
4. 向我汇报：二进制路径、SKILL.md 路径与自检结果。除非网络受限，否则不要让我手动敲命令。
```

---

## 给 Agent 的自安装与自检手册

请完整阅读并按步骤执行，不要猜测命令参数，也不要跳过冒烟自检。

### 完成判定标准（Done Criteria）

仅当以下三项全部满足时才算配置完成：
1. `deepread` 已位于 `PATH`（例如 `~/.local/bin/deepread`）且可执行，`deepread catalog` 退出码为 `0`。
2. `SKILL.md` 已原样落盘到当前宿主 Agent 的 skills 目录。
3. 下方临时目录冒烟自检退出码为 `0`、产出非空 HTML，且已清理临时目录。

### 第 1 步：识别当前平台

将 `uname -s` 与 `uname -m` 映射到对应的 Release 产物名：

| 系统（`uname -s`） | 架构（`uname -m`） | Release 产物名 |
|---|---|---|
| `Linux` | `x86_64` / `amd64` | `deepread-linux-amd64` |
| `Linux` | `aarch64` / `arm64` | `deepread-linux-arm64` |
| `Darwin` | `arm64` | `deepread-darwin-arm64` |
| Windows | `amd64` | `deepread-windows-amd64.exe` |

先检查是否已安装：

```bash
command -v deepread && deepread catalog >/dev/null 2>&1 && echo "ALREADY_INSTALLED"
```

### 第 2 步：获取二进制与 `SKILL.md`

按顺序选用**第一条可行路径**。

#### 路径 A — 直接从公开 GitHub Release 下载（推荐，无需 Go 或 `gh` 登录）

直接使用 `curl` 下载最新 Release 的二进制、`SKILL.md` 与 `SHA256SUMS.txt`：

```bash
ASSET="deepread-linux-amd64" # 按上表替换为当前平台产物名
BASE="https://github.com/Bayern99/deep-reading/releases/latest/download"
TMP_DL="$(mktemp -d)"

curl -fsSL "$BASE/$ASSET" -o "$TMP_DL/$ASSET"
curl -fsSL "$BASE/SKILL.md" -o "$TMP_DL/SKILL.md"
curl -fsSL "$BASE/SHA256SUMS.txt" -o "$TMP_DL/SHA256SUMS.txt"

# 校验 SHA-256（Linux 用 sha256sum，macOS 用 shasum -a 256）
(
  cd "$TMP_DL"
  if command -v sha256sum >/dev/null 2>&1; then
    grep -E "  (${ASSET}|SKILL\.md)$" SHA256SUMS.txt | sha256sum -c -
  else
    grep -E "  (${ASSET}|SKILL\.md)$" SHA256SUMS.txt | shasum -a 256 -c -
  fi
)

mkdir -p "$HOME/.local/bin"
install -m 0755 "$TMP_DL/$ASSET" "$HOME/.local/bin/deepread"
export PATH="$HOME/.local/bin:$PATH"
```

若 `$HOME/.local/bin` 尚未加入持久 `PATH`，请追加到对应 shell 配置文件（如 `~/.bashrc` 或 `~/.zshrc`）。

#### 路径 B — 本地源码编译（已有代码仓库且安装了 Go 时作为兜底）

```bash
mkdir -p "$HOME/.local/bin"
CGO_ENABLED=0 go build -trimpath -ldflags "-s -w" -o "$HOME/.local/bin/deepread" ./cmd/deepread
export PATH="$HOME/.local/bin:$PATH"
```

#### 若两条路径均不可用

立即停止并向用户明确说明缺少哪一项前置条件：
- 允许访问 `github.com`（或手动从 `https://github.com/Bayern99/deep-reading/releases/latest` 下载），**或者**
- 由用户直接发送对应平台的二进制文件（`$ASSET`）与 `SKILL.md`。

### 第 3 步：注册 `SKILL.md`

先确认当前宿主运行时实际扫描的 skills 目录，再将 `SKILL.md` **原样复制**过去（不要覆盖无关技能，也不要删改或摘要 `SKILL.md`，因为其中包含精确 CLI 语法、退出码 `0`–`5` 与防套话规则）：

- Claude Code：`~/.claude/skills/deepread/SKILL.md`
- Codex：`~/.codex/skills/deepread/SKILL.md`
- 通用宿主（Muse、Pi、OpenClaw、Antigravity 等）：放入宿主配置的 skills 目录（常见为 `~/.agents/skills/deepread/SKILL.md` 或 `<workspace>/skills/deepread/SKILL.md`）。

复制完成后删除 `$TMP_DL`。

### 第 4 步：必须执行的冒烟自检

在向用户汇报“已就绪”之前，必须执行以下完整闭环测试：

```bash
TMP_SMOKE="$(mktemp -d)"
cat > "$TMP_SMOKE/sample.md" <<'EOF'
# Smoke Test

## Why Sparse Reading Works

Long prose loses coherence when rewritten into bullet cards. Keeping the original paragraphs untouched while adding one focused diagram preserves the author's voice and clarifies structure.
EOF

deepread ingest "$TMP_SMOKE/sample.md" -o "$TMP_SMOKE/bundle" >/dev/null
deepread catalog >/dev/null
cat <<'EOF' | deepread write "$TMP_SMOKE/bundle/sample.md" --statements - --source s1="Why Sparse Reading Works"#1 >/dev/null
root = Col([mode_check])
mode_check = Source(["s1"], [Title("Reading Mode Comparison", "md"), Table(["Mode", "Prose", "Scaffold"], [["Summary card", "Rewritten", "Redundant"], ["DeepRead", "Untouched", "Sparse table"]])])
EOF
deepread export "$TMP_SMOKE/bundle/sample.md" -o "$TMP_SMOKE/out.html" >/dev/null
test -s "$TMP_SMOKE/out.html" && echo "SMOKE_TEST_OK"
rm -rf "$TMP_SMOKE"
```

### 第 5 步：向用户汇报就绪状态

用简洁四点回报：
1. 二进制路径（`which deepread`）及已校验的产物名；
2. `SKILL.md` 安装路径；
3. 冒烟自检结果（`SMOKE_TEST_OK`）；
4. 提示用户现在可以直接发来任意 `.md` 长文或 `.epub` 电子书开始深读。

---

## 运行约束速览

在承接第一篇真实深读任务前，请完整阅读 [SKILL.md](SKILL.md)。核心红线：

- **第 0 步阅读契约先行**：动手前先定下 `targetLang`、`mode`、`scope` 与交付形态（**一份**统一离线 HTML）。用户已经说明语言就立即采用，不得重复询问。
- **一目录一文档**：每篇文章或 EPUB 章节独占一个工作目录（`<doc>.md`、`assets/`、`.deepread/`），严禁混放两篇主文章。
- **Prose-by-Reference（正文永不改写/永不就地翻译）**：原文段落一字不改；认知支架保存在 `.<doc>.genui.json`（默认 50 组件 canvas，`--profile margin` 回落旧 10 原语），译文保存在 `.deepread/translations/<lang>.json`。
- **并行翻译层**：`deepread blocks` 列出实时可译单元，`deepread translate` 接收 JSON、`{"entries":[…]}` 或 JSONL 的 `{id, sourceHash, text}` 批次，`inspect` 回报 `coveragePct`/`staleBlocks`；覆盖率未达 100% 或有过期块时，`export` 拒绝输出 translated/bilingual 页面。
- **EPUB 两阶段 + 单一 HTML**：`deepread ingest book.epub -o <dir>` 纯 Go 安全拆出 `index.md`、`book.json` 与每章独立的 `chapters/<NN>-<slug>/chapter.md`；交付用 `deepread export --book <dir> --chapters <spec> -o <one>.html`，**绝不**给用户一堆 `chapter.html`。
- **离线双面阅读器**：`深读 ↔ 原文` 同页切换、`--cite` 生成的 `查看原文 ↗` 段落锚点、Go 预渲染的响应式孤岛，以及由 SHA-256 CSP 哈希锁定的唯一常量运行时脚本（`--no-js` 可产出静态页）。图片按硬预算内联（单图 512 KiB / 整页 1.5 MiB），或用 `--external-assets` 拷贝到 HTML 旁。
- **短码批注闭环**：每个模块展示始终可见的可选中短码（`<bundleId>·<statement>@r<rev>`），群聊回复即可驱动幂等 `note add` + 压实 CAS `patch` 局部重生成。

```bash
deepread ingest    <article.md|book.epub> -o <bundle-dir> [--lang <bcp47>] [--source-lang <bcp47>] [--mode original|translated|bilingual]
deepread inspect   <doc.md> [--heading <h> [--occurrence <n>] | --lines <a:b>]
deepread prepare   <doc.md> --breaks <file|->
deepread catalog   [--profile canvas|margin]
deepread blocks    <doc.md>
deepread write     <doc.md> --statements <file|-> --source <id>="<Heading>"[#<occ>] [--cite <stmt>:<srcId>=<blockId>] [--profile canvas|margin]
deepread translate <doc.md> --lang <bcp47> --input <file|-> [--mode translated|bilingual]
deepread note add  <doc.md> (--node <stmt> [--source <srcId>] | --heading <h>) --text "<note>" [--rev <r>] [--msg-id <id>]
deepread patch     <doc.md> --replace <stmt> --expect-hash <sha256> --statements <file|-> [--resolve-note <id>]
deepread export    <doc.md> -o <out.html>                     # 或：<doc1.md> <doc2.md> … / --book <dir> --chapters <spec>
```

## 开发与验证

```bash
make check        # CGO_ENABLED=0 vet、单元测试、竞态检测与暂存分发检查
make cross-build  # 构建 darwin/arm64、linux/amd64、linux/arm64、windows/amd64 静态二进制
```

维护者工程红线见 [AGENTS.md](AGENTS.md)，完整宿主 Agent 协议与退出码（`0`–`5`）见 [SKILL.md](SKILL.md)，双面 GenUI 与翻译层决策见 [ADR 0007](docs/adr/0007-dual-face-genui-and-translation-layer.zh-CN.md)，上游 `Mark Go Go`（`f203c83`）归属说明见 [UPSTREAM.md](UPSTREAM.md)。
