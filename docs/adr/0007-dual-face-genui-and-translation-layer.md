# ADR 0007: Dual-Face GenUI, the Parallel Translation Layer, and Multi-Chapter Books

- **Status:** Accepted
- **Date:** 2026-12-10
- **Supersedes:** parts of [ADR 0006](0006-headless-go-deepread-engine.md) — specifically its 10-primitive whitelist, its zero-JavaScript mandate, its "never translate" rule, and its single-document-only export.
- **Extends:** [ADR 0006](0006-headless-go-deepread-engine.md) headless Go capability layer, Prose-by-Reference, one-way `Mark Go Go` v3 compatibility, and one-document-per-bundle-directory isolation.

## Context

ADR 0006 shipped a deliberately narrow reader: ten static primitives, no scripts, one document per export, and prose that was never translated. Real readers of `WSJ`- and `Economist`-style long-form texts immediately asked for three things the v0.2 contract could not express:

1. **Read in their own language.** Non-English readers want the whole article in Chinese (or Japanese, Portuguese, …) while keeping the original paragraphs available as immutable ground truth. A "translate the prose in place" design would have destroyed the Prose-by-Reference invariant that makes every later diff, note, and citation verifiable.
2. **A real reading canvas.** Causal mechanisms, multi-subject comparisons, timelines, terminology asides, and source-bounded "what-if" controls are not expressible as `Table` and `Chart` alone. The 10-primitive whitelist forced every article into the same sparse table shape, which is exactly the cliché ADR 0006 set out to prevent.
3. **One deliverable, not five files.** A five-chapter EPUB produced five independent `chapter.html` files that no reader would ever open in sequence.

At the same time the host agent — not this binary — remains the editorial brain, and lightweight cloud-computer models are the primary operators. Any new capability therefore has to be **deterministic, offline, and impossible to misuse**: the runtime may not call a translation API, may not execute agent-authored JavaScript, and may not silently publish a half-translated page.

## Decision

### 1. A parallel, content-addressed translation layer

Prose stays byte-for-byte untouched; translations live beside it.

- `.deepread/translations/<lang>.json` stores `{id, sourceHash, text}` entries keyed by a deterministic block id. Block ids are `b` + the `fnv1a32` digest of whitespace-normalized prose, so reflowing a paragraph or inserting a reader note never invalidates a translation, while genuinely edited prose does.
- `deepread blocks` exposes the live units (`heading`, `paragraph`, `blockquote`, `list_item`, `table_cell`, `image_alt`) with their ids, hashes, section attribution, and text.
- `deepread translate --lang <bcp47> --input <file|->` merges a batch (JSON array, `{"entries":[...]}`, or JSONL). Every entry is validated against the *live* document before the layer is written: an unknown id or an unsafe body (empty, raw `<script>`, block-level image markdown) is a validation rejection, and a stale `sourceHash` is a compare-and-swap conflict so an Agent can never overwrite fresh prose with a translation of the old text.
- `inspect` reports `translation.coveragePct`, `translatedBlocks`, `staleBlocks`, `missingIds`, and `staleIds`; `export` refuses `translated`/`bilingual` rendering unless coverage is 100% with zero stale blocks (override only with the explicit `--allow-partial-translation`).
- The reading contract (`sourceLang`, `targetLang`, `mode`) is recorded in `.deepread/manifest.json`, so `ingest --lang zh-CN` and `export --lang auto --mode auto` agree without re-stating flags. Synthetic H2 anchors inserted by `prepare` carry an optional translated heading in the manifest instead of becoming translation units.

### 2. A 50-component canvas profile beside the legacy margin profile

`view.WriteOptions.Profile` selects the contract, and `deepread catalog [--profile canvas|margin]` prints it:

- **`canvas` (default).** The complete `Mark Go Go` v3 component catalog (50 components: `Col`, `Row`, `Grid`, `Card`, `Svg`, `Chart` with bar/line/area/pie/donut/scatter, `Table`, `List`, `Popover`, `Flashcard`, `Slider`, `SegmentedControl`, `RadioGroup`, `Input`, …). `Source` statements may cite several sections for genuine cross-section synthesis, and the page header may sit outside `Source`.
- **`margin`.** The byte-compatible v0.2 ten-primitive subset, retained for existing bundles and for hosts that want the narrowest possible contract.

Sparsity and editorial craft are enforced by *content* rather than by a 10-primitive whitelist: `PROSE_WRAPPER_REJECTED` rejects wrapping raw paragraphs in `Card([Title(...), Text(...), Badge(...)])` while permitting structured multi-item scannable `List` (`>=2` `ListItem`s with title + description), `Quote`, `Image`, `Svg`, `Chart`, `Table`, `Timeline`, `Popover`/`Flashcard`, and reactive islands; `GENERIC_KV_TABLE` rejects two-column key–value dumps (`指标|数值`, `项目|事实`, `metric|value`), `MONOTONE_VIEW` rejects a canvas where more than two thirds of `Source` blocks share the same dominant medium (tables or plain text), `CLICHE_TITLE_REJECTED` rejects summary titles, and `UNTRANSLATED_GENUI` rejects English-only GenUI text under a Chinese reading contract. The default `dual` face opens into this full-information structured reading canvas (eliminating dense prose walls while retaining ~95%+ reporting fidelity) with verbatim translated/original/bilingual prose one click away; `--face inline` (paragraph-interleaved via `--cite`) and `--face hybrid` (masthead hero canvas + paragraph-interleaved prose) are also supported.

### 3. Go-precomputed reactive islands, one constant offline runtime

Charts, timelines, and diagrams need no scripting; "what-if" controls do. DeepRead resolves that tension without ever shipping agent-authored JavaScript:

- The Go exporter enumerates the bounded state space of every `$variable` control and pre-renders **every** state as a static `<template data-island=… data-state=…>` fragment. State spaces above 64 combinations degrade to the default state with a `REACTIVE_STATE_EXPLOSION` warning instead of exploding the page.
- A single **constant** runtime script toggles face (`GenUI ↔ 原文`), chapter, language mode, island state, and the `查看原文 ↗` anchor jump. It is never templated with document data, and it is pinned by a SHA-256 `script-src` hash in the page's Content-Security-Policy, so a modified or injected script cannot execute.
- `--no-js` still produces a complete dual-face page with all controls disabled, and a single-document `read` export without a view keeps the original zero-script shape.
- Every module keeps its always-visible short code (`<bundleId>·<statement>@r<rev>`) and gains a `查看原文 ↗` chip that jumps to the exact cited paragraph, driven by `.deepread/citations.json` written from `--cite <stmt>:<srcId>=<blockId>`.

### 4. Multi-chapter aggregation into one offline HTML file

On-disk isolation is unchanged: one chapter per directory (`chapters/<NN>-<slug>/chapter.md` with its own `.deepread/` and `assets/`). Delivery changes:

- `deepread export --book <book-dir> [--chapters 1,3,5-7|<slug>|all] -o <out.html>` resolves `book.json` through `os.OpenRoot`, verifies every chapter stays inside the book directory, and renders **one** offline HTML reader with a table of contents, chapter navigation, and a unified asset budget.
- `deepread export <doc1.md> <doc2.md> … -o <out.html>` aggregates already-ingested bundles in the supplied order.
- One document still exports exactly as before (`deepread export <doc.md> -o <out.html>`), and per-chapter intermediate HTML files are no longer part of the delivery contract.

## Consequences

- **Positive.** Readers get prose in their own language with the original always one click away; hosts get a rule-based, deterministic canvas contract that cannot degenerate into summary tables; every page stays offline, dependency-free, and CSP-hardened; one book yields one file.
- **Positive.** Translation work is incremental and auditable: `blocks` → `translate` → `inspect` (`coveragePct`, `staleIds`) → `export` is a closed loop with exit codes that distinguish a missing translation (`3` `TRANSLATION_INCOMPLETE`) from a stale one (`5` `CONFLICT`).
- **Negative.** `SKILL.md` must carry the full Step-0 reading contract (target language, mode, scope, delivery) because lightweight models will not infer it; the manual is therefore longer, and it is the authoritative spec.
- **Negative.** Canvas mode puts more weight on editorial guardrails: a weak agent can still produce a legal but dull page. The `MONOTONE_VIEW` and `GENERIC_KV_TABLE` gates bound the failure, not the ambition.
- **Migration.** `version: 3`, `language: "openui-lang/1.0"`, `catalogId: "markgogo.dev:genui/v3"`, `.genui.prev.json`, `fnv1a32` hashes, and attributed `<!-- note ... -->` comments stay unchanged. Existing v0.2 margin bundles keep working via `--profile margin`, and the `margin` export face remains byte-compatible.
- ADR 0006 remains the record of the headless-Go pivot; only the four superseded clauses above are replaced.
