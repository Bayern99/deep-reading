# ADR 0006: Headless Go Deep-Reading Engine (`deepread`)

- **Status:** Accepted
- **Date:** 2026-11-26
- **Supersedes:** [ADR 0001](0001-three-tier-editorial-composition.md), [ADR 0002](0002-issue-artifact-only-product.md), [ADR 0003](0003-derived-article-map.md), [ADR 0004](0004-page-column-grid-not-story-regions.md), [ADR 0005](0005-paragraph-boundaries-from-printed-indents.md)
- **Public History Reset:** Prior to public release, legacy v1 Python commits containing private newspaper test outputs were removed from public Git history and archived offline.

## Context

The v1 Python pipeline (~9,500 lines) spent most of its engineering budget reconstructing articles from multi-column print PDFs and forcing every article into one rigid template with four static SVG charts. At the same time, modern agent workflows (cloud-computer bots, Muse, and coding agent harnesses) already possess strong reasoning and shell execution, while readers consume long-form digital texts (Markdown and EPUB) primarily on mobile browsers or local Markdown/GenUI workbenches such as `Mark Go Go`.

## Decision

1. **Pivot to a headless single-binary Go capability (`deepread`) + `SKILL.md`.**  
   `deepread` embeds zero LLM orchestration, zero API keys, zero GUI dependencies, and zero CGO (`CGO_ENABLED=0`). The host agent is the editorial brain; `deepread` provides the deterministic runtime for ingestion, structure inspection, strict validation, atomic compare-and-swap patching, and zero-JS mobile HTML export.
2. **Prose-by-Reference with sparse anti-cliché guardrails.**  
   Original prose paragraphs remain untouched. `write` and `patch` enforce a narrowed 10-primitive static reading subset (`Col`, `Source`, `Title`, `Text`, `Caption`, `Quote`, `List`, `ListItem`, `Table`, `Chart` bar/line), zero-fault strict validation, single-section top-level `Source` topology, no summary-only blocks, and no card/badge dashboards. Zero modules (`root = Col([])`) is valid.
3. **One-way compatibility with `Mark Go Go` v3 (`f203c83`).**  
   Pure-Go headless packages (`openuilang`, `genuikit`, `markdown`) are synced with MIT attribution in [UPSTREAM.md](../../UPSTREAM.md) without modifying `Mark Go Go`. Sidecars conform to `version: 3`, `language: "openui-lang/1.0"`, `catalogId: "markgogo.dev:genui/v3"`, `.genui.prev.json` undo backups, `fnv1a32` section hashes, and attributed inline `<!-- note ... -->` comments. Every patch compacts into a single `createSurface` to stay well under the 1 MiB limit.
4. **One document per bundle directory & two-phase EPUB ingestion.**  
   Each article or EPUB chapter lives in its own directory (`chapters/<NN>-<slug>/chapter.md`, `assets/`, `.deepread/`) with advisory file locks, a note ledger (`.deepread/ledger.json`), and revision snapshots (`.deepread/history/`). `export` produces zero-JS 390px-first magazine HTML with always-visible short codes (`<bundleId>·<statement>@r<rev>`) and supports both budget-capped inline single-file mode and `--external-assets` directory hosting.

## Consequences

- The repository drops Python runtime dependencies, print-PDF geometry parsers, and hardcoded WSJ issue templates.
- Historical ADRs 0001–0005 remain in `docs/adr/` for architectural context while legacy v1 Python code is archived offline.
- Cross-platform static binaries (`darwin/arm64`, `linux/amd64`, `linux/arm64`, `windows/amd64`) build cleanly with standard Go tooling.
