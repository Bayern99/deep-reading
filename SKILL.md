---
name: deepread
description: Deep-read a Markdown article or an EPUB book in any language and deliver ONE offline HTML reader with the original prose, a full 50-component GenUI reading canvas, and a parallel translation layer. Use whenever a long text must be genuinely read and restructured, when the user asks for a Chinese (or other language) version of an article/book, when a reader note must be answered, or when a single self-contained HTML reading page must be produced.
---

# deepread — dual-face deep reading for Markdown and EPUB

`deepread` is one static Go binary. It never calls the network and never asks an LLM to do
deterministic work: **you** are the editorial brain, `deepread` is the runtime that ingests,
lists translatable blocks, validates your GenUI, stores translations, and renders the page.

`deepread` 是一个静态 Go 单二进制工具：不联网、不调用模型。**你**负责编辑判断，`deepread` 负责导入、
列出可译块、严格校验 GenUI、保存译文并渲染页面。

Every command prints deterministic JSON on stdout; every failure prints
`{"error":{"code","message","hint",...}}` on stderr with a stable exit code `0..5`.
命令成功时在 stdout 输出 JSON，失败时仅在 stderr 输出结构化 JSON 与退出码。

Build once (no cgo, no runtime dependency): `CGO_ENABLED=0 go build -o ~/bin/deepread ./cmd/deepread`.
或直接使用已安装到 `PATH` 的 `deepread`。

---

## STEP 0 — Mandatory reading contract (do this BEFORE `prepare` / `write` / `translate`)

Before touching any file, fix these four values for yourself. Do not skip this step; do not
re-derive them later from memory.

| Field | Allowed values | Default |
| --- | --- | --- |
| `targetLang` | BCP 47 (`zh-CN`, `ja`, `pt-BR`, …) or *none* | infer from the user |
| `mode` | `translated` \| `bilingual` \| `original` | `translated` when `targetLang` is set |
| `scope` | which chapters/sections | what the user asked for |
| `delivery` | **1 single unified offline HTML** | always this |

**Language already stated → adopt it immediately, never ask again.** If the user wrote
"用中文", "中文版", "translate to Chinese", "中文总结/深读", set `targetLang=zh-CN` and
`mode=translated` right now and continue. Same for Japanese, Korean, French, Spanish, etc.

**用户已经说了语言（例如"用中文""Chinese""中文版"）就立即采用 `targetLang=zh-CN`、`mode=translated`，
绝对不要重复询问。** 只有"语言"或"处理哪几章"确实无法判断时，才允许问 **一个** 简短问题；
一个问题里同时问清这两项即可，不要连问。

Delivery is never negotiable: multi-chapter work still ends in **one** HTML file (see
[Single unified HTML](#single-unified-html-never-five-chapter-files)).

---

## Unbreakable invariants / 不可违反的红线

1. **Original prose is immutable ground truth.** Never rewrite, shorten, reorder, or translate a
   prose paragraph in `<doc>.md`. `ingest` only rewrites local image links to `assets/<name>`;
   `prepare` only inserts synthetic `## §n · Title` heading lines; `note add` only inserts inline
   `<!-- note ... -->` comments. All your editorial output lives in the v3 sidecar
   (`.<doc>.genui.json`) and in the translation layer.
   原文段落是不可篡改的地面真值：不得改写、缩写、重排或就地翻译；你的产出只进侧文件与翻译层。

2. **Translation is a parallel layer, never an edit.** Use `deepread blocks` to get the live unit
   ids, then `deepread translate` to store the translation. The original paragraph stays
   byte-for-byte available behind the `原文` face.
   译文走并行层（`blocks` → `translate`），原文永远保留。

3. **In `translated` / `bilingual` mode, 100% of blocks must be translated before export.**
   That includes the H1 headline, every H2/H3 subhead, every body paragraph, every caption,
   every list item, every table cell, and every localized term. Never leave a half-translated
   phrase such as `黑 mass`; write the real localized form `黑粉（black mass）`. Export refuses to
   run until coverage is 100% with zero stale blocks and names the missing/stale block ids.
   `translated` / `bilingual` 模式下，导出前必须是 **100% 块覆盖**：标题、小标题、正文段落、图注、
   列表项、表格单元格、专有名词全部译出；不允许"黑 mass"这种半翻译，要写"黑粉（black mass）"。
   覆盖率不足时 `export` 会直接拒绝并列出缺失/过期的块 id。

4. **GenUI must be content-driven, not a template.** Run `deepread catalog` and design the canvas
   for *this* article. Diversify media across the page; never repeat one shape.
   GenUI 必须由内容驱动，先跑 `deepread catalog`，为这篇文章定制画布。

5. **One document per bundle directory; one chapter per directory.** Never mix two articles in
   one directory, never copy sidecars across chapters.
   一目录一文档、一目录一章节，不得混放。

---

## Full-information structured reading canvas (zero wall-of-text, ~95% fidelity) / 去文字墙的全信息量结构化精读

`deepread catalog` prints the **canvas** contract (default, 50 components) with signatures,
editorial patterns, and the language reference. `deepread catalog --profile margin` prints the
legacy 10-primitive subset — use it only for old bundles.

**Default layout is dual-face (`dual`):**
- **Front face (`深读`):** A **full-information structured reading canvas** built specifically for
  this article — zero unbroken walls of dense prose, yet **~95%+ information retention** (every
  key person, company, figure, case study, counterpoint, original artwork/chart, and punchy quote
  preserved in clean narrative order).
- **Back face (`原文`):** The 100% verbatim translated / original / bilingual prose (`中文 / EN / 双语`),
  always one click away from the top bar or from any Act's `查看原文 ↗` / `预览` button.
- Optional faces: `--face inline` (prose with paragraph-interleaved GenUI modules) and
  `--face hybrid` (masthead hero canvas + paragraph-interleaved prose).

**Avoid BOTH failure modes — never thin summaries, never walls of text:**
- **Do NOT write a thin 3-card summary** that strips away the reporting, anecdotes, quotes, and
  nuances (a reader shouldn't have to switch to `原文` just to find out what actually happened).
- **Do NOT dump raw dense paragraphs into `Card([Text(...), Badge(...)])`** (`PROSE_WRAPPER_REJECTED`,
  exit `3`), never pile isolated numbers into decorative KPI cards, and never emit generic
  `指标|数值` / `项目|事实` / `metric|value` two-column tables (`GENERIC_KV_TABLE`, `MONOTONE_VIEW`).
- **Structure the full article Act-by-Act (typically 3 to 6 Acts per article):**
  1. **Header (`head`, outside `Source`):** Localized headline + 1-line thesis subtitle + `Popover`
     terminology glossary for domain terms.
  2. **Original artwork & charts:** Embed the article's own lead photo and original charts directly
     inside the relevant Act via `Image("assets/<file>", "Localized caption")` (read filenames from
     the chapter's `chapter.md`).
  3. **Scannable fact-dense prose (zero walls of text):** Break dense reporting into pill-tagged
     bullet points `List([ListItem("Bold anchor", "1–2 line detail keeping every concrete name, number, and caveat", "Tag")], "none")`
     paired with punchy verbatim `Quote`s.
  4. **Visual & interactive leverage where structure demands it:** Weave bespoke `Svg` mechanism
     diagrams, comparative `Chart`s, multi-column `Table`s (real subject columns), dated `Timeline`
     lists, and bounded `$variable` + `Slider` / `SegmentedControl` reactive islands right inside
     the Act where they clarify causal logic or math. **Put each reactive control (`Slider` /
     `SegmentedControl`) in its own dedicated `Source` statement** so the control sits directly above
     its chart/table rather than floating above a long bullet list.

**避免两个极端（既不做丢信息的薄摘要，也不堆「哒哒哒哒」的密集文字墙）：**
- **不要做成缩水摘要**：必须保留原文 **~95%+ 的真实信息量**（关键人物、公司案例、精确数字、反方观点、原刊插画/图表与原声金句），让读者在 `深读` 这一面就能完整吃透全篇。
- **彻底消灭大段豆腐块**：按逻辑拆成 **3～6 幕（`01 …`、`02 …`）**，用「左标签胶囊 + 加粗锚点 + 1～2 行高密细节」的结构化 `ListItem` 与原声 `Quote` 替代冗长段落；严禁 `Card+Text+Badge` 套壳（`PROSE_WRAPPER_REJECTED`）、严禁孤立 KPI 数字墙、严禁 `指标|数值` 两列废表（`GENERIC_KV_TABLE`）。
- **图文交互有机混排**：把原刊配图/图表（`Image("assets/...", ...)`）、因果机制 `Svg`、数据 `Chart`、多主体 `Table`、`Timeline` 与有边界的 `$variable` `Slider`/`SegmentedControl` 互动推演编织到对应幕中（交互控件单独放一个 `Source` 语句，确保滑块/切换条紧贴自己的图表上方）。

Pick the medium strictly from what each Act actually contains:

| The Act contains… | Emit |
| --- | --- |
| Dense reporting, concrete cases, actors, caveats | **Pill-tagged `List([ListItem("Anchor", "Concise fact-dense detail", "Tag")], "none")`** (≥2 structured items) + verbatim **`Quote`** |
| Original lead illustration or source chart in `assets/` | **`Image("assets/<filename>", "Localized caption")`** inside the relevant Act |
| A causal mechanism, feedback loop, system flow, physical layout | **`Svg`** (`viewBox` + `label` + `Rect`/`Path`/`Line`/`Circle`/`SvgText` nodes and arrows) |
| A time series or numeric comparison with the *same* unit/period | **`Chart`** (`bar`\|`line`\|`area`\|`pie`\|`donut`\|`scatter`, localized `seriesLabels`) |
| Several subjects scored on several dimensions | **`Table` with ≥3 columns** named after the real subjects, or **`Grid` of `Card`s** (multi-subject comparison only, NOT isolated KPI dumps) |
| Dense dated turning points in chronological order (≥3 milestones) | **`List([ListItem(...)], "none", true)`** timeline — re-verify every date against the prose, never shift a year |
| Key terminology, policy nuance, methodological caveat | **`Popover`** (typically in `head`) or **`Flashcard`** |
| An explicitly bounded numeric scenario (source gives min/max endpoints and per-unit figures) | Dedicated `Source` with **`$variable` + `Slider` / `SegmentedControl`** + live `Chart` / `Table` |

**Cite the exact paragraphs.** For every Act (`Source`), attach
`--cite <statement>:<sourceId>=<blockId>[,<blockId>...]` using the live block ids from
`deepread blocks`; the reader's `查看原文 ↗` / `预览` button then jumps straight to those exact
verbatim paragraphs (and also powers paragraph-level interleaving in `--face inline` / `--face hybrid`).
每一幕都务必用 `--cite` 绑定对应的具体段落块 id。

---

## Single unified HTML (never five chapter files) / 单一 HTML 交付

Internal layout is always one chapter per directory
(`chapters/<NN>-<slug>/chapter.md`, own `.deepread/`, own `assets/`). Delivery is always **one**
self-contained offline HTML:

```bash
deepread export --book books/example --chapters 1,2 -o example-deep-read.html
deepread export --book books/example                       -o example-deep-read.html   # all chapters
```

Never hand the user five separate `chapter.html` files, never ask which format they prefer.
多章节任务同样只交付一个 HTML：永远用 `export --book … --chapters … -o <有意义的名字>.html`。

---

## The 10 commands / 十条命令

```bash
deepread ingest    <src.md|book.epub> -o <dir> [--lang <bcp47>] [--source-lang <bcp47>] [--mode original|translated|bilingual]
deepread inspect   <doc.md> [--heading <text> [--occurrence <n>]] [--lines <start>:<end>]
deepread prepare   <doc.md> --breaks <file|->
deepread catalog   [--profile canvas|margin]
deepread blocks    <doc.md>
deepread write     <doc.md> --statements <file|-> [--source <id>="<Heading>"[#<occ>]]... [--cite <stmt>:<srcId>=<blockId>[,<blockId>...]]... [--profile canvas|margin] [--model <m>] [--request <r>]
deepread translate <doc.md> --lang <bcp47> --input <file|-> [--mode translated|bilingual] [--source-lang <bcp47>]
deepread note add  <doc.md> (--node <stmt> [--source <srcId>] | --heading <h> [--occurrence <n>]) --text "<note>" [--rev <r>] [--msg-id <id>]
deepread patch     <doc.md> --replace <stmt> [--replace <stmt2>] --expect-hash <sha256> [--expect-source-hash <srcId>=<hash>]... --statements <file|-> [--source <id>="<Heading>"[#<occ>]]... [--cite <stmt>:<srcId>=<blockId>...]... [--resolve-note <id>]... [--profile canvas|margin] [--model <m>] [--request <r>]
deepread export    <doc.md> -o <out.html> [flags]
deepread export    <doc1.md> <doc2.md> ... -o <out.html> [--title <t>] [flags]
deepread export    --book <book-dir> [--chapters <spec>] -o <out.html> [--title <t>] [flags]
```

### 1. `ingest` — create the bundle

```bash
deepread ingest essay.md -o bundles/essay --lang zh-CN --source-lang en
deepread ingest book.epub -o books/example --lang zh-CN
```

- Markdown → `<dir>/<name>.md` + `<dir>/assets/` + `<dir>/.deepread/manifest.json`.
- EPUB → `<dir>/index.md`, `<dir>/book.json`, and one isolated bundle per chapter under
  `<dir>/chapters/<NN>-<slug>/chapter.md`.
- `--lang` alone implies `--mode translated` (unless it equals `--source-lang`, then `original`).
  The contract is persisted, so later commands only need `<doc.md>`.
- Unsupported extension → exit `2`. Unsafe archive/image → exit `3` (`UNSAFE_ARCHIVE`,
  `ARCHIVE_LIMIT_EXCEEDED`). Never re-ingest into a non-empty or existing bundle (exit `5`).

### 2. `inspect` — read the state before acting

Returns `bundleId`, `revision`, `viewExists`, `viewHash`, `reader` (`sourceLang`/`targetLang`/`mode`),
`translation` (`coveragePct`, `translatedBlocks`, `totalBlocks`, `staleBlocks`, `missingIds`,
`staleIds`), every section (`heading`, `level`, `occurrence`, `startLine`, `endLine`, `hash`,
`synthetic`), `modules` with `shortCode`s, `openNotes`, `staleSources`, `missingSources`,
`affectedStatements`, plus an optional `excerpt`.

```bash
deepread inspect article.md
deepread inspect article.md --heading "Interconnection queues"   # exact prose of one section
deepread inspect article.md --lines 120:180                      # numbered lines
```

Read the excerpt before citing it. Re-run `inspect` after every exit `5`.

### 3. `prepare` — add H2 anchors only when the article has none

```bash
echo '[{"beforeLine": 41, "title": "Interconnection queues"}]' | deepread prepare article.md --breaks -
```

Inserts synthetic `## §1 · Title` lines (never touching prose), flagged `synthetic` in `inspect`.
Breaks must ascend, hit non-blank lines, and stay outside fenced code.

### 4. `catalog` — read the contract before writing

`deepread catalog` = canvas (50 components, default). `deepread catalog --profile margin` = the
legacy 10 primitives. Read it every time you start a new document.

### 5. `blocks` — list the translatable units

```json
{"docPath":"…","bundleId":"K7","totalBlocks":12,
 "blocks":[{"id":"b3f2a1c9","kind":"paragraph","sectionHeading":"Capital","sourceHash":"3f2a1c9d","text":"…"}]}
```

Kinds: `heading`, `paragraph`, `blockquote`, `list_item`, `table_cell`, `image_alt`. Synthetic
`prepare` headings are not units. Copy `id` **and** `sourceHash` exactly; never invent either.

### 6. `translate` — store translations in the parallel layer

`--input` accepts stdin (`-`), a JSON file, or JSONL:

```bash
# JSONL: one object per line — best for many blocks
printf '%s\n' '{"id":"b3f2a1c9","sourceHash":"3f2a1c9d","text":"并网排队容量从 750 GW 增至 2,600 GW。"}' \
  | deepread translate article.md --lang zh-CN --input -

# JSON array, or {"entries":[...]}
deepread translate article.md --lang zh-CN --input zh-CN.json
```

Rules: one entry per live block; `text` non-empty; no raw `<script>`; no block-level image
markdown; keep every number/year/unit exactly (`$18B`, `2,600 GW`). Stale `sourceHash` → exit `5`
(re-run `blocks`); unknown id or unsafe text → exit `3` (`VALIDATION_FAILED`). Output is the new
`TranslationStatus`; re-check with `inspect` until `coveragePct` is `100` and `staleBlocks` is `0`.

Translate **everything**: H1/H2/H3 headings, paragraphs, captions, list items, table cells,
localized terms. 全部译出，包括标题、图注、表格单元格与专有名词；数字、年份、单位原样保留。

### 7. `write` — commit the GenUI canvas

Write **bare openui-lang**, one statement per line, exactly as `catalog` shows it — no JSON, no
escaping. `--statements -` reads stdin.

```bash
cat <<'OPENUI' | deepread write article.md --statements - \
  --source s1="Interconnection queues"#1 --source s2="Capital basis"#1 \
  --cite queue_mechanism:s1=b3f2a1c9 --cite capex_grid:s2=b7d1e004
root = Col([head, queue_mechanism, capex_grid])
head = Row([Title("电网为何承压：排队机制与资本口径", "xl"), Badge("原文保真", "info")], 2)
queue_mechanism = Source(["s1"], [Svg([Rect(5, 10, 30, 20, "surface"), Path("M 35 20 L 60 20", null, "info", 2), Circle(70, 20, 10, "warning"), SvgText("排队", 15, 25)], "0 0 100 50", "项目进入受限的并网排队")])
capex_grid = Source(["s2"], [Grid([Card([Title("Firm A", "md"), Text("2024 单年现金支出", "sm"), Badge("$18B")]), Card([Title("Firm B", "md"), Text("三年累计承诺（2024–2026）", "sm"), Badge("$42B")])], 2, 200, 3), Caption("依据原文 §2 口径注释")])
OPENUI
```

- `--source <id>="<Exact Heading>"[#<occ>]` maps each `Source([...])` id to a section. Copy the
  heading bytes from `inspect` (omit `#occ` for occurrence 1). Never cite the H1 alone.
- `--cite` anchors one statement's block ids; anchors you already stored for other statements are
  preserved across later `write`/`patch` revisions.
- A canvas `Source` may cite several sections (`Source(["s1","s2"], [...])`) for genuine
  cross-section synthesis; keep it top-level under `root`.
- `root = Col([])` is a valid zero-module view.
- On success: `revision`, `viewHash`, `moduleCount`, and one `shortCode`
  (`<bundleId>·<statement>@r<rev>`) per module. Quote short codes when discussing a module; never
  re-derive them.

### 8. `note add` — record a reader note verbatim

```bash
deepread note add article.md --node capex_grid --rev 2 --msg-id "tg:44118" \
  --text "这两家公司口径不同，不能直接比大小"
```

`--node` targets a module statement; `--heading` targets a section when the scaffolding itself is
wrong. If the statement cites **several** sections, you must add `--source <srcId>` so the note
lands on the right prose. `--rev` records the revision the reader saw (stale → exit `5`);
`--msg-id` makes a chat-platform replay idempotent. Only record notes a human actually wrote, in
their own words.

### 9. `patch` — compare-and-swap revision

```bash
deepread inspect article.md      # read viewHash + openNotes
deepread patch article.md --replace capex_grid --expect-hash <viewHash> \
  --statements - --resolve-note n3 --cite capex_grid:s2=b7d1e004 <<'OPENUI'
capex_grid = Source(["s2"], [Table(["主体", "披露口径", "原文数值", "年均参考"], [["Firm A", "2024 单年实付", "$18B", "当年一次性"], ["Firm B", "三年累计承诺（2024–2026）", "$42B", "约 $14B"]]), Caption("依据原文 §2 口径注释")])
OPENUI
```

- `--replace` (repeatable or comma-separated) names ONLY the modules (or canvas `$variables`) to
  swap; never include `root` or untouched modules (exit `3` `PATCH_SCOPE_VIOLATION`).
- `--expect-hash` is the exact `viewHash` from `inspect`; a stale one exits `5`.
- `--expect-source-hash <srcId>=<hash>` is required when the cited section's prose changed
  (`staleSources` non-empty) — read the new prose first, then pass its live `hash`.
- `--source` adds newly introduced source ids; `--resolve-note` closes answered notes;
  `--cite` refreshes the cited block ids for that statement + source and leaves every other
  module's `查看原文 ↗` anchor intact.

### 10. `export` — render the delivery

```bash
deepread export article.md -o article.html                       # one document
deepread export ch1.md ch2.md -o reader.html --title "My Reader"  # several bundles, in order
deepread export --book books/example --chapters 1,2 -o example.html
```

Flags: `--out`/`-o` (required), `--title`, `--face dual|inline|hybrid|genui|read|margin`,
`--lang auto|original|<bcp47>`, `--mode auto|original|translated|bilingual`, `--no-js`,
`--allow-partial-translation`, `--external-assets`, `--max-bytes <n>`, `--max-image-bytes <n>`.
`--chapters` accepts `1,3,5-7`, a slug, a title, or `all`, and may be repeated.
`--face` picks the reading surface:
- `dual` (**default** when modules exist): full-information structured reading canvas (`深读`,
  zero walls of text, ~95%+ fidelity) paired with 100% verbatim translated / original / bilingual
  prose (`原文`) and one-click `查看原文 ↗` / `预览` paragraph anchors.
- `inline`: prose-first interleaved essay where each module appears directly after its `--cite`
  paragraph, with `精读 / 图解 / 纯文` toggle.
- `hybrid`: elevates the first module into a masthead hero overview below the headline/subtitle,
  and interleaves remaining modules after their `--cite` paragraphs.
- `genui` (canvas only), `read` (prose only — default when 0 modules exist), `margin` (v0.2 legacy).

The default output is the **dual-face (`dual`)** reader: the front canvas turns dense long-form
prose into scannable Acts with pill-tagged bullet points, quotes, original artwork/charts, causal
SVGs, interactive islands, tables, and timelines, while the verbatim original/translated/bilingual
prose stays one click away behind `原文` and `查看原文 ↗`. The constant runtime script is pinned by
a SHA-256 CSP hash (`--no-js` renders the same page with controls disabled). Assets are inlined as
`data:` URIs (1.5 MiB single-doc / 6 MiB book / 512 KiB image budgets) unless `--external-assets`
copies them beside the HTML.

Exit `3` `TRANSLATION_INCOMPLETE` means missing or stale block ids: translate them (see §6), then
export again. Never bypass it with `--allow-partial-translation` unless the human explicitly asked
for a preview of an unfinished translation.

---

## Exit codes / 退出码

| Code | Meaning | What you do |
| --- | --- | --- |
| `0` | Success | Read the JSON, continue. |
| `1` | Runtime error (I/O, lock, unresolvable request) | Diagnose; do not retry blindly. |
| `2` | Usage error (bad flag, bad argument, unsupported format, bad language tag) | Fix the invocation from this manual. |
| `3` | Validation/guardrail rejection (GenUI, assets, archive, translation body, incomplete translation) | Read `code` + `hint` + `message` and **self-repair**; never bypass. |
| `4` | Not found (doc, section, statement, note, block, source id) | Re-run `inspect` / `blocks`; correct heading/occurrence/id. |
| `5` | Conflict (stale `viewHash`, stale `revision`, stale block `sourceHash`) | Re-run `inspect` (and `blocks`), rebase, retry once. |

Stable exit-`3` codes: `DISALLOWED_COMPONENT`, `DISALLOWED_CHART_TYPE`, `PROSE_ONLY_SUMMARY_REJECTED`,
`PROSE_WRAPPER_REJECTED`, `CLICHE_TITLE_REJECTED`, `TOO_MANY_MODULES`, `SINGLE_SOURCE_REQUIRED`,
`NESTED_SOURCE_FORBIDDEN`, `UNKNOWN_SECTION`, `MISSING_SOURCE_MAPPING`, `H1_SOURCE_FORBIDDEN`,
`DUPLICATE_SECTION_MODULE`, `OPENUI_ERROR`, `UNRESOLVED_IDENTIFIER`, `INVALID_ROOT_TOPOLOGY`,
`GENERIC_KV_TABLE`, `MONOTONE_VIEW`, `UNTRANSLATED_GENUI`, `UNSAFE_SVG`, `UNSAFE_URL`,
`VALIDATION_FAILED`, `TRANSLATION_INCOMPLETE`, `ASSET_BUDGET_EXCEEDED`, `UNSAFE_ASSET_PATH`,
`UNSAFE_ARCHIVE`, `ARCHIVE_LIMIT_EXCEEDED`.

`TRANSLATION_INCOMPLETE` / `CONFLICT` / `INVALID_ARGS` 三类错误各有明确修复路径，逐条照做即可，
不要放宽限制、不要手改 `.genui.json` 或翻译文件。

---

## Mandatory done checklist / 交付前必查（reply only after all four pass）

1. **Language fulfilled 100%.** `deepread inspect <doc.md>` shows `translation.coveragePct: 100`
   and `staleBlocks: 0`; the HTML carries `<html lang="zh-CN">` (or the requested tag) and
   `data-lang-mode="translated"`. 目标语言 100% 完成，无过期块。
2. **Full-information, zero wall-of-text canvas.** Zero two-column `指标|数值` / `项目|事实` dumps,
   zero prose-in-a-box `Card` wrappers, zero thin 3-card summaries that drop reporting details;
   the article flows Act-by-Act combining pill-tagged scannable `ListItem` points, verbatim `Quote`s,
   original `Image("assets/...", ...)` charts/artwork, causal `Svg`, honest `Chart`, multi-subject
   `Table`, `Timeline`, and bounded reactive islands (each in its own `Source` statement).
   全信息量且零文字墙：既有高密结构化要点、原声金句与原刊图表，又有因果图/对比表/交互推演，无两列废表与纯文字套壳框。
3. **Every figure verified.** Each number, year, unit, entity, and qualifier was re-checked
   against `deepread inspect --heading` / `deepread blocks`; localized terms are complete
   (`黑粉（black mass）`, never `黑 mass`). 所有数字、年份、单位、主体与专有名词均已逐字核对。
4. **One unified HTML.** A single offline HTML was exported with exit `0`; it ships the full-information
   structured `深读` canvas alongside verbatim `原文` prose (`中文 / EN / 双语`) with `查看原文 ↗`
   block anchors, and (for a book) includes every requested chapter in one file with `data-chapter`
   navigation. 只交付一个 HTML，正面全信息结构化精读、背面完整原文与双语对照、锚点齐全。

## File ownership / 文件归属

| Path | Contents | Written by |
| --- | --- | --- |
| `<doc>.md` | original prose (immutable) + synthetic anchors + inline notes | `ingest`, `prepare`, `note add` |
| `.<doc>.genui.json` / `.<doc>.genui.prev.json` | Mark Go Go v3 sidecar + undo backup | `write`, `patch` |
| `.deepread/manifest.json` | `bundleId`, `revision`, reader contract, synthetic sections | `ingest`, `write`, `patch`, `translate` |
| `.deepread/translations/<lang>.json` | `{id, sourceHash, text}` per language | `translate` |
| `.deepread/citations.json` | `statement → sourceId → [blockId]` | `write`, `patch` |
| `.deepread/ledger.json` | notes, `msgId` dedupe, revision seen | `note add`, `patch` |
| `.deepread/history/r<rev>.genui.json` | revision snapshots | `write`, `patch` |
| `<out>.html` | the deliverable | `export` |

Never hand-edit these files, never copy them across bundles, and never commit a real article's
bundle or HTML into the tool repository. When in doubt, `inspect` is authoritative.
