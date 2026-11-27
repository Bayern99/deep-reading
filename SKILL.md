---
name: deepread
description: Add sparse, non-summarizing reading scaffolds (table, chart, quote, timeline) to a Markdown article or to one chapter of a supplied EPUB book, and export a zero-JS mobile reading page. Use when an article or EPUB needs structured cognitive support grounded in its own sections, when a reader note must be answered or resolved, or when a deep-read HTML page must be produced from the ingested document and its `.<doc>.genui.json` sidecar.
---

# deepread — sparse reading scaffolds for one Markdown document

`deepread` is a single static Go binary. `ingest` turns one local Markdown file or one EPUB book into
this layout; keep **one Markdown article per bundle directory** so `.deepread/` metadata never
collides across documents. Existing prose paragraphs stay byte-for-byte
untouched (`prepare` inserts only synthetic `## §n · Title` heading lines; `note add` inserts only
inline `<!-- note ... -->` comments), and all GenUI scaffolds live in the Mark Go Go v3 sidecar
(`.<doc>.genui.json`). Every command except `catalog` (plain Markdown text) prints deterministic
JSON on stdout; errors are always written to stderr as `{"error": {"code", "message", "hint", ...}}`
with a stable exit code.

`deepread` 是一个静态 Go 单文件工具：`ingest` 将一个本地 Markdown 文件或一本 EPUB 转成该目录布局，
每个工作目录只放一篇主文章（避免 `.deepread/` 元数据串用）：
正文段落本身保持逐字节不变（`prepare` 仅插入合成 H2 标题行，`note add` 仅插入行内 `<!-- note ... -->` 批注），
所有认知支架保存在 Mark Go Go v3 侧文件（`.<doc>.genui.json`）。除 `catalog` 输出纯 Markdown 文本外，
所有命令成功时在 stdout 输出确定性 JSON；失败时仅在 stderr 输出 `{"error": {...}}` 结构化 JSON 与稳定退出码。

**Build once for a cloud shell (no cgo, no runtime deps):**

```bash
cd <tool-checkout> && CGO_ENABLED=0 go build -o ~/bin/deepread ./cmd/deepread
```

## Non-negotiables / 硬性约束

1. Existing article prose paragraphs are the source of truth. Never rewrite, shorten, translate,
   or reorder prose paragraphs (`ingest` copies prose and only rewrites local image links to
   `assets/<name>`; `prepare` inserts only synthetic `## §n · Title` heading lines; `note add`
   inserts only inline `<!-- note ... -->` comments). All cognitive scaffolds live in the sidecar
   (`.<doc>.genui.json`).
2. **0 modules is a valid answer.** Sparse Cognitive Intervention means 0–4 modules (max 6 for
   articles over 6,000 words, max 1 per section). Only intervene where structural support
   removes real cognitive cost.
3. Every module cites exactly one non-H1 section and must contain at least one structural
   primitive — `Table`, `Chart` (bar/line only), `Quote`, or `List(..., timeline=true)`.
4. Every figure, date, unit, entity, and quote must appear verbatim in the cited section.
5. Output is Mark Go Go v3 compatible; keep `language: "openui-lang/1.0"` and
   `catalogId: "markgogo.dev:genui/v3"`. Never hand-edit the JSON; use the commands.

原文段落是唯一事实来源：不得改写、缩写、翻译或重排正文段落（`prepare` 仅插入合成 H2 标题行，
`note add` 仅插入行内 `<!-- note ... -->` 批注），所有认知支架保存在侧文件。**0 个模块也是合格答案**，
稀疏认知干预为 0–4 个模块（正文超过 6,000 词最多 6 个，每节最多 1 个）。每个模块只引用一个小节
（不能是 H1），且必须含至少一个结构性组件：`Table`、`Chart`（仅 bar/line）、`Quote` 或
`List(..., timeline=true)`。所有数字、日期、单位、主体与引文必须逐字出现在被引用小节中。
侧文件必须保持 Mark Go Go v3 兼容；不要手工改 JSON。

## The 8-command workflow / 八步工作流

```bash
deepread ingest    <src.md|book.epub> -o <dir>                  # 1. import a source into bundle layout
deepread inspect   <doc.md>                                    # 2. read state
deepread prepare   <doc.md> --breaks <file|->                  # 3. add H2 anchors if needed
deepread catalog                                               # 4. read the whitelist
deepread write     <doc.md> --statements <file|-> --source id="Heading"#occ   # 5. author
deepread export    <doc.md> -o <out.html> [--external-assets]   # 6. render
deepread note add  <doc.md> ... --text "<note>"                # 7. record a reader note
deepread patch     <doc.md> --replace <stmt> --expect-hash <sha256> --statements <file|->  # 8. revise
```

`ingest` is the only command that creates a bundle; every later command works on exactly one
`<doc.md>` at a time. For a book, ingest once and then run steps 2–8 on the one chapter the human
asked for. `ingest` 是唯一创建文档包的命令；其后每条命令只处理一篇 `<doc.md>`。
整本书只导入一次，之后按用户请求的单个章节执行第 2–8 步。

### 1. `deepread ingest <src.md|book.epub> -o <out-dir>`

Imports one local Markdown file (`.md`, `.markdown`) or one EPUB (`.epub`). No network access and no
external converter: any other extension exits `2` with `INVALID_ARGS`. `-o` / `--out` names the bundle
root and may appear before or after the positional source. The command prints the usual JSON:
`kind` (`markdown` / `epub`), `title`, `author`, `outDir`, `docPath`, `indexPath`, `bookJson`,
`bundleId`, `imageCount`, and `chapters[]` for books.

`ingest` 将本地 Markdown 或 EPUB 导入文档包布局；仅支持 `.md`、`.markdown`、`.epub`，其余扩展名以退出码
`2`（`INVALID_ARGS`）拒绝。`-o`/`--out` 指定文档包根目录，可放在源文件参数前后。

**Markdown.** Copies the file to `<out-dir>/<name>.md`, copies every referenced local raster image
(PNG/JPEG/GIF/WebP/AVIF) to `<out-dir>/assets/`, rewrites those links to `assets/<name>`, and creates
`<out-dir>/.deepread/manifest.json`. Prose lines other than the image links are copied untouched.

```bash
deepread ingest essay.md -o bundles/essay
```

**EPUB (two phases / 两阶段).** One book produces:

- `index.md` — a human-readable table of contents for the whole book.
- `book.json` — the chapter list (`index`, `slug`, `title`, `wordCount`, `imageCount`, `bundleId`, `docPath`).
- `chapters/<NN>-<slug>/chapter.md` — one **isolated single-document bundle** per chapter, with its own
  `.deepread/` metadata, own `bundleId`, own revision counter, and own `assets/` directory.

Phase 1, once per book: run `deepread ingest book.epub -o <dir>`, then show the human `index.md` and the
chapter list from `book.json` (title + `docPath`), and confirm which chapter they want.

Phase 2, on demand: run every later command against **one** chapter path — `inspect`, `prepare`, `write`,
`export`, `note add`, `patch`. Each chapter is a separate bundle, so `inspect` on it reports only that
chapter's sections, revision, and sidecar; there is no cross-chapter state. Never overwrite or mix
files across chapter directories (re-ingesting into a non-empty directory or an existing bundle exits
`5` with `CONFLICT`). Render per chapter (`chapters/02-the-grid/chapter.html`) and link those pages
from the book index if a book page is wanted.

第一阶段：`deepread ingest book.epub -o <dir>` 导入整本书，把 `index.md` 与 `book.json` 的章节清单
（标题 + `docPath`）给用户看，确认要处理哪一章。第二阶段：仅对那一章的
`chapters/<NN>-<slug>/chapter.md` 按需执行 `inspect`/`prepare`/`write`/`export`/`note add`/`patch`。
每章都是独立的单文档文档包（独立 `bundleId`、独立版本号、独立 `assets/`）；不要向非空或已有文档包目录重复导入（以退出码 `5` 拒绝），也不要跨章混放文件。

```bash
deepread ingest book.epub -o books/example
deepread inspect books/example/chapters/02-the-grid/chapter.md
deepread export books/example/chapters/02-the-grid/chapter.md \
  -o books/example/chapters/02-the-grid/chapter.html
```

**Input safety (exit `3`).** Images must be real raster bytes located strictly inside the source
document directory. `UNSAFE_ARCHIVE` covers path traversal, symlink escapes, duplicate or non-raster
archive entries and invalid local image references; `ARCHIVE_LIMIT_EXCEEDED` covers the entry count,
the 16 MiB per-file limit and the 64 MiB total decompressed limit. 输入必须安全：只接受文档目录内真实的
位图文件；路径穿越、符号链接逃逸、非位图条目以 `UNSAFE_ARCHIVE` 拒绝，条目数或解压总量超限以
`ARCHIVE_LIMIT_EXCEEDED` 拒绝。Ingest stages atomically so a failed ingest leaves `<out-dir>` untouched.

### 2. `deepread inspect <doc.md>`

Start here for every document (`ingest` output or an existing bundle), and re-run it after any failure
that returns exit code 5.
It returns `bundleId`, `revision`, `viewExists`, `viewHash`, `lineCount`, every section
(`heading`, `level`, `occurrence`, `startLine`, `endLine`, `hash`, `synthetic`), current
`modules` with their `shortCode`s, `openNotes` (pending reader notes), `staleSources` and
`missingSources` (headings changed after the sidecar was written), and `affectedStatements`.

```bash
deepread inspect article.md
deepread inspect article.md --heading "Grid Queues" --occurrence 1   # excerpt = that section
deepread inspect article.md --lines 120:180                           # excerpt = numbered lines
```

Read the excerpt (or the section) before citing it: `inspect --heading` is the exact prose a
module may quote. Never write a module for a section you have not read.

### 3. `deepread prepare <doc.md> --breaks <file|->`

Only when the article has no usable H2 sections (one long body). It inserts synthetic
`## §n · Title` headings before the given paragraph starts and records them as `synthetic`,
without changing any existing prose line. Breaks must be strictly ascending, point at a
non-blank line, and never land inside a fenced code block.

```bash
echo '[{"beforeLine": 41, "title": "Interconnection queues"}, {"beforeLine": 96, "title": "Capex"}]' \
  | deepread prepare article.md --breaks -
```

Use a specific, analytical title — it becomes a citation anchor in the article.

### 4. `deepread catalog`

Prints the 10-primitive static reading whitelist (`Col`, `Source`, `Title`, `Text`, `Caption`,
`Quote`, `List`, `ListItem`, `Table`, `Chart`) with signatures, the hard rules, and two sparse
examples. Dashboard and form components (`Card`, `Grid`, `Row`, `Badge`, `Box`, `Carousel`,
`Input`, …) are out of scope even though Mark Go Go renders them.

### 5. `deepread write <doc.md> --statements <file|-> --source <id>="<Heading>"#<occ> [--model <m>] [--request <r>]`

Write **bare openui-lang**, one statement per line, exactly as `catalog` shows it — no JSON,
no escaping. `--statements -` reads stdin. `--source` is repeatable and maps each `Source([...])`
id to an exact heading (omit `#occ` for occurrence 1; `inspect` prints the exact heading bytes).
Optional `--model` and `--request` stamp provenance metadata in the v3 envelope.

```bash
cat <<'OPENUI' | deepread write article.md --statements - \
  --source s1="§2 · Grid Queues"#1 --source s2="§3 · Capex"#1
root = Col([queue_mod, capex_mod])
queue_mod = Source(["s1"], [Title("并网排队容量（GW）", "md"), Chart("bar", qdata, "year", ["queued"], "number", false, 200), Caption("数据取自原文 §2")])
qdata = [{year: "2020", queued: 750}, {year: "2024", queued: 2600}]
capex_mod = Source(["s2"], [Title("资本开支统计口径不可直接相加", "md"), Table(["主体", "口径", "原文数值"], [["甲公司", "2024 单年实付", "$18B"], ["乙公司", "三年累计承诺", "$42B"]]), Caption("依据原文 §3 口径注释")])
OPENUI
```

Topology: `root = Col([mod1, mod2])` may only list names of top-level `Source(...)`
statements. No nested `Source`, no inline expressions in `root`, no title/intro outside a
`Source`. `root = Col([])` writes a valid zero-module view.

On success it returns `revision`, `viewHash`, `moduleCount`, and one `shortCode` per module
(`<bundleId>·<statement>@r<revision>`, e.g. `K7·capex_mod@r2`). Quote short codes when
discussing a module with a human; never re-derive them.

### 6. `deepread export <doc.md> -o <out.html> [--title <t>] [--external-assets] [--max-bytes <n>] [--max-image-bytes <n>]`

Renders one zero-JS, 390px-first reading page: original prose with each module interleaved at its
cited section, plus its visible short code and source heading. No network assets, no scripts, no
sidecar contents beyond the modules. Optional `--title` overrides the HTML `<title>`. The output path
must not collide with `<doc.md>`, its sidecars, or protected `.deepread/` metadata (that is a runtime
error, exit `1`). Re-run `export` after every accepted `write`/`patch` so the HTML matches `viewHash`.

Two asset modes / 两种资产模式 (stdout JSON reports `assetMode` as `"inline"` or `"external"`, plus `imageCount` and `bytes`):

- **Inline (default).** Every local image is embedded as a `data:` URI (and pre-existing `data:image/...;base64,...` URIs are decoded, magic-byte verified, and counted against the same limits), so the page is a single portable file whose CSP is `img-src data:`. Inline budgets are 1.5 MiB of total HTML and 512 KiB per raw image; tighten them with `--max-bytes <n>` and `--max-image-bytes <n>`. Exceeding a budget exits `3` with `ASSET_BUDGET_EXCEEDED` and writes no HTML file.
- **`--external-assets`.** Each local image keeps its clean relative path (typically `assets/<name>` after `ingest`) and is copied to the matching relative path beside `<out.html>` when exporting to another directory; the CSP relaxes to `img-src 'self' data:`. Use this when the page is too large to inline or is served from a directory over HTTPS (the 16 MiB per-image external cap still applies).

默认内联：本地图片转成 `data:` URI（已内联的 `data:image/` 同样校验实际位图魔数与体积），整页单文件、CSP 为 `img-src data:`；内联预算为整页 HTML 1.5 MiB、单张原图 512 KiB，可用 `--max-bytes` / `--max-image-bytes` 收紧，超限以退出码 `3`（`ASSET_BUDGET_EXCEEDED`）拒绝且不写出 HTML。加 `--external-assets` 时保留原相对路径（经 `ingest` 后即 `assets/<name>`）并复制到 HTML 所在目录，CSP 放宽为 `img-src 'self' data:`，适合目录方式经 HTTPS 托管大页面；stdout JSON 会返回 `assetMode`（`"inline"`/`"external"`）与 `imageCount`。`--max-bytes` 与 `--max-image-bytes` 必须是正整数，否则是用法错误（退出码 `2`）。`export` 从不修改文档、侧文件或 `.deepread/`。

Active/disallowed URL schemes (`javascript:`, `vbscript:`, `data:text/html`, `data:image/svg+xml`, etc.) on hyperlinks or images are stripped/neutralized; local image paths that escape the document directory, touch `.deepread/` or sidecars, decode into an active URI scheme, or fail raster MIME sniffing exit `3` with `UNSAFE_ASSET_PATH`. 链接与图片中的活动/危险协议会被自动清空；本地图片若越出文档目录、访问 `.deepread/`/侧文件、解码后成活动协议或位图魔数校验失败，均以 `UNSAFE_ASSET_PATH`（退出码 `3`）拒绝。

### 7. `deepread note add <doc.md> (--node <stmt> | --heading <h> [--occurrence <n>]) --text "<note>"`

Records a reader note in `.deepread/ledger.json` and answers it through `patch`, never by
editing prose. `--node` targets one module statement; `--heading` targets a section (used when
the note is about missing/incorrect scaffolding). `--rev <r>` records the revision the reader
saw; `--msg-id <id>` makes the command idempotent for a chat-platform message, and a repeated
`--msg-id` returns the existing note instead of duplicating it.

```bash
deepread note add article.md --node capex_mod --rev 2 \
  --msg-id "tg:44118" --text "这两家公司口径不同，不能直接比大小"
```

Only record notes a human actually wrote, verbatim in their language. Do not invent requests.

### 8. `deepread patch <doc.md> --replace <stmt> --expect-hash <sha256> --statements <file|-> [--expect-source-hash <id>=<hash>] [--source <id>="<Heading>"#<occ>] [--resolve-note <id>] [--model <m>] [--request <r>]`

Replaces ONLY the target top-level `Source` statement(s) named in `--replace` (plus any brand-new
private helper statements they reference) while leaving `root` and every untouched module
byte-for-byte intact, and compacts the sidecar to a single `createSurface` message:
- `--replace` (repeatable or comma-separated) names the module statement(s) being replaced.
- `--expect-hash` is the exact `viewHash` reported by `inspect` (prevents lost updates; stale hash exits 5).
- `--expect-source-hash <id>=<hash>` (repeatable) is **required whenever the target section's prose changed since the sidecar was written** (`staleSources` non-empty); inspect the updated section first and pass its live `hash` to confirm you reviewed the new prose.
- `--statements` contains **ONLY** the replacement statement(s) and optional new private helpers — do **NOT** include `root` or untouched modules (modifying them is rejected with exit 3).
- `--source` (optional, repeatable) adds any newly introduced source id mapping if needed.
- `--resolve-note` (optional, repeatable) marks the answered ledger note id(s) as `resolved`.
- `--model` and `--request` (optional) stamp provenance metadata in the v3 envelope.
Mark Go Go's undo file (`.<doc>.genui.prev.json`) is updated automatically; revision snapshots land in
`.deepread/history/r<rev>.genui.json`.

```bash
deepread inspect article.md                     # read viewHash + openNotes
deepread patch article.md --replace capex_mod --expect-hash <viewHash> \
  --statements - --resolve-note n3 <<'OPENUI'
capex_mod = Source(["s2"], [Title("资本开支统计口径：并置而不可相加", "md"), Table(["主体", "披露口径", "原文数值", "年均参考"], [["甲公司", "2024 单年实付", "$18B", "当年一次性"], ["乙公司", "三年累计承诺（2024–2026）", "$42B", "约 $14B"]]), Caption("依据原文 §3 口径注释")])
OPENUI
```

## Exit codes / 退出码

| Code | Meaning | Agent action |
| --- | --- | --- |
| `0` | Success | Read the JSON, then continue the workflow. |
| `1` | Runtime error (I/O, lock, missing binary input) | Diagnose the environment; do not retry blindly. |
| `2` | Usage error (unknown flag, bad argument shape, unsupported ingest format) | Fix the invocation; re-read this manual. |
| `3` | Validation / guardrail rejection (statements, assets, archive input) | Read the JSON `code` + `hint` and **self-repair** the input. Never bypass the guardrail. |
| `4` | Not found (doc, section, statement, note id) | Re-run `inspect`, correct the heading/occurrence/id. |
| `5` | Hash or revision conflict (stale `--expect-hash`, doc changed) | Re-run `inspect`, rebase your edit on the current `viewHash`, retry once. |

Exit code `3` includes stable codes: `DISALLOWED_COMPONENT`, `PROSE_ONLY_SUMMARY_REJECTED`,
`CLICHE_TITLE_REJECTED`, `TOO_MANY_MODULES`, `H1_SOURCE_FORBIDDEN`, `DUPLICATE_SECTION_MODULE`,
`SINGLE_SOURCE_REQUIRED`, `NESTED_SOURCE_FORBIDDEN`, `DISALLOWED_CHART_TYPE`, `UNKNOWN_SECTION`,
`MISSING_SOURCE_MAPPING`, `OPENUI_ERROR`, `UNRESOLVED_IDENTIFIER`, `VIEW_TOO_LARGE`.
Fix the statement that the JSON names; never relax the check, never edit `.genui.json` by hand.

Asset and archive guardrails also use exit code `3`: `ASSET_BUDGET_EXCEEDED`, `UNSAFE_ASSET_PATH`,
`UNSAFE_ARCHIVE`, `ARCHIVE_LIMIT_EXCEEDED`. Repair the input (compress images, re-run with
`--external-assets`, or remove the unsafe/oversized source entry) instead of raising a limit.
资产与压缩包护栏同样使用退出码 `3`（`ASSET_BUDGET_EXCEEDED`、`UNSAFE_ASSET_PATH`、
`UNSAFE_ARCHIVE`、`ARCHIVE_LIMIT_EXCEEDED`）；应修复输入，而不是放宽限制。

| 退出码 | 含义 | Agent 动作 |
| --- | --- | --- |
| `0` | 成功 | 读取 JSON 继续流程。 |
| `1` | 运行错误（I/O、锁、缺少输入） | 排查环境，不要盲目重试。 |
| `2` | 用法错误（参数或标志不对、不支持的导入格式） | 修正调用方式。 |
| `3` | 校验/护栏拒绝（语句、资产、压缩包） | 读取 JSON 的 `code` 与 `hint`，**自行修复**，不得绕过。 |
| `4` | 未找到（文档、小节、语句、note id） | 重新 `inspect` 并核对名称。 |
| `5` | 哈希/版本冲突 | 重新 `inspect`，基于当前 `viewHash` 重做修改，只重试一次。 |

## Non-Cliché editorial standards / 反陈词编排标准

**Sparse Cognitive Intervention.** A module earns its place only if it reveals a structure the
prose makes hard to see: a mismatch that must be disclosed, a trajectory, a decision timeline,
a comparison the reader would otherwise assemble mentally. If prose is already clear, emit
`root = Col([])`. Density is not value; four good modules are a ceiling, zero is a valid run.

**Never summarize.** No module may restate, condense, or paraphrase the article. Banned shapes:
"Summary", "Key Takeaways", "Overview", "TL;DR", "要点", "总结", "摘要", and bullet lists of
already-written paragraphs. A `Source` module contains an analytical scaffold, not recap.

**Disclose mismatched units and periods.** Comparing a single-year cash figure with a
multi-year commitment, or a stock with a flow, requires an explicit column/caption that names
the basis. If the honest answer is "these cannot be added", say so in the Table or Caption.
Never place unlike quantities on equal bars to look tidy. `Chart` supports `bar` and `line`
only; if the story has no honest series, use `Table` or `Quote` instead.

**Fact-check before writing, verbatim.** For each figure, date, unit, entity, and quote, run
`inspect --heading` and confirm the exact string in the cited section. Copy numbers as printed
(`$18B`, not `18`; `2,600 GW`, not `2600`). A quote must be character-identical to the source
and attributed to the real section. If the source is ambiguous or contradicts itself, record
the ambiguity in a `Caption` instead of resolving it by guessing.

**Answer reader notes by revising, not arguing.** A note is a signal that a module misled or
failed. Re-inspect, patch the scaffold, resolve the note, re-export. Reader prose is never
edited, and a note is never dismissed to make a check pass.

**Chat short-code replies.** Humans reply with short codes, e.g. `K7·capex@r1 这两家不能直接相加` or
`K7·queue@r2 时间轴错了`. Treat the code as `<bundleId>·<statement>@r<revision>`: match `bundleId`
and `statement` against `inspect` output, use `revision` to detect staleness (behind current
revision → re-inspect before acting), record the human's sentence verbatim via
`note add --node <stmt> --rev <r> --msg-id <platform-id> --text "<verbatim>"`, then `patch --resolve-note`.
If the code names no existing statement, do not guess: reply with the current `modules` list
(statement + shortCode + heading) and ask which one the reader means.

**中文要点：** 模块只在能揭示正文不易看见的结构时才存在；正文已清楚就输出 `root = Col([])`。
禁止复述、概括、翻译正文，禁止"总结/要点/摘要"类标题。单位或统计期间不一致必须显式披露，
必要时直接在 Table/Caption 说明"不可相加"。写入前用 `inspect --heading` 逐字核对每个数字、
日期、单位、主体与引文；原文歧义就写进 Caption，不要替作者下结论。读者留言用 short code
（`K7·capex@r1`）指代模块时，按 `<bundleId>·<statement>@r<revision>` 解析，版本落后就重新
`inspect`，逐字记录留言后 `patch --resolve-note`；代码无法匹配时列出当前模块并反问，不得猜测。

## File ownership / 文件归属

- `<out-dir>/<doc>.md` + `<out-dir>/assets/` — `ingest` output for a Markdown source; prose is copied byte-for-byte except that local image links become `assets/<name>`.
- `<out-dir>/index.md`, `<out-dir>/book.json`, `<out-dir>/chapters/<NN>-<slug>/chapter.md` (+ its own `assets/` and `.deepread/`) — `ingest` output for an EPUB; each `chapter.md` is an isolated bundle and the unit every later command operates on.
- `<doc>.md` — human prose paragraphs stay byte-for-byte untouched; `prepare` inserts only synthetic `## §n · Title` heading lines and `note add` inserts only inline `<!-- note ... -->` comments. Keep one `<doc>.md` per bundle directory.
- `.<doc>.genui.json` — Mark Go Go v3 sidecar. Written only by `write` / `patch`.
- `.<doc>.genui.prev.json` — Mark Go Go's undo file, containing the previous sidecar.
- `.deepread/manifest.json` — `bundleId`, `revision`, synthetic sections.
- `.deepread/ledger.json` — notes, `msgId` dedupe, revision each note saw.
- `.deepread/history/r<rev>.genui.json` — revision snapshots for diffing and rollback.
- `<out>.html` — `export` output; regenerate after every accepted change.

Never copy, rename, or hand-edit these files; never commit an article's sidecar into the tool
repository. When a sidecar and a doc disagree, `inspect` is authoritative and exit code `5`
means your snapshot is stale.
