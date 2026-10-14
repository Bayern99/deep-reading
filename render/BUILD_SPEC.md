# Static renderer contract

This file describes only the `build.py` whole-issue path. The Phase 5–7 publisher, compiler, artifact store and queue are documented in [ARCHITECTURE](../ARCHITECTURE.md). Commands and troubleshooting live in [BUILD](BUILD.md); product and visual authority live in [FOUNDATION](../FOUNDATION.md) and [DESIGN](../DESIGN.md).

## Inputs and output

Input is issue `final.json`, `front.json`, optional `enhanced-v1` plans, and verified images/curation manifests. Output is issue `dist/index.html`, internal `baseline.html` and execution receipts. The static renderer never invokes a model. The current CLI retains a 117-input assertion from its acceptance issue; cross-issue manifests must be scoped before it can publish arbitrary new issues safely.

## Rendering

`issue.py` selects the front pack and reading order from that issue's front metadata. Only selected PASS items enter visible content; excluded, WARN and BLOCK items remain in source. WARN/BLOCK receive review anchors. Published types receive different treatments:

- `article` / `opinion`: full article head and continuous bilingual body.
- `brief` / `letter`: compact metadata and body.
- `index_digest`: newspaper digest column, rather than a long-article header.
- `data_table`: curated appendix/table treatment; source number fidelity remains required.
- `photo_caption`: verified image when available, otherwise a caption entry.
- `correction`: compact correction entry.

`article.py` handles ordinary rendering. `enhanced_render.py` uses the same repaired source projection and supports only validated operations. An empty intervention preserves ordinary markup and metadata. Unknown source anchors, unsupported operations, unmatched exact text and stale content digests fail with receipts. Historical `component_plan` schemas are not interchangeable with `enhanced-v1` plans.

## Integrity and acceptance

Paragraph text and order are checked for both languages before successful page writes. Confirmed alignment repair records are shared by ordinary, enhanced and baseline paths; baseline assets match the compared output. Image paths must resolve to preserved verified media in the issue `assets/` directory, including figures recovered from the print edition.

The front pack is driven by `front.json`, never hardcoded article IDs. Per-story headline phrase protection is optional and exact-match only. Continuous Chinese prose uses natural line breaking, no `text-wrap: pretty`; new editorial additions must have source support and add reading value. The removed duel component stays removed.

Actual acceptance combines source/receipt checks with Chinese/English navigation and rendered inspection at desktop, tablet and 390px. Zero overflow does not replace comfortable reading or editorial judgment. Current test commands are maintained in BUILD and the root Makefile.
