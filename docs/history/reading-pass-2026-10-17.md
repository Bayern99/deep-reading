# Reading Pass records for both pilot issues (2026-10-17)

Ticket #14. Every content page's reading items now answer which MinerU blocks
they own, for the reference issue (2026-10-14) and the held-out second issue
(2026-10-10).

## Reference issue: 2026-10-14

- 25 content pages, 100 reading items across the reference issue.
- Each answer names block indices per item, including the reprinted headline of
  every story that continues onto the page. Eight pages gained continuation
  items (2, 4, 6, 10, 20, 22, 24, 25); page 20 had two enumerated items for one
  reprinted headline and they were folded into one.
- Every answer was validated before merging: indices exist in the page's MinerU
  blocks, no index is assigned to two items, and no item is empty.
- The cache now carries `blocks` for all 100 items:
  `<pilot>/evidence/reader-items.json`. Pre-pass backup, outside every Git
  repository:
  `/Users/dmus/Documents/deep-reading/reader-items.pre-blocks-2026-10-17.json`.

## Result

- `derive_article_map` returns 86 records, **0 with `regions_source = geometry`**
  (74 `reading_pass_blocks`, 12 `reading_pass` where a continuation answer was
  merged into its origin record).
- Every record has derived `paragraphs`: 86/86, 1,316 paragraphs.
- Block boxes contain 96.6–100% of each page's text lines. Assignment coverage
  (text lines inside an item's blocks) is 81–99% on pages that are mostly
  editorial; it is low only where the page is mostly tables or ads (page 31
  market tables, page 12 crossword, page 20 business index).
- Paragraph boundaries against the reference inventory are unchanged by the
  block answers: 1,086/1,097 predicted boundaries correct (99.0%),
  1,086/1,106 recovered (98.2%).

## Where the regions still differ from the golden map

75 golden stories match a derived record. 18 have a per-page column-origin set
that differs by more than the 2pt grid-rounding tolerance:

- **Narrow columns merged by the grid.** Stories on pages 14, 15 and 17 own a
  column narrower than the 100pt merge threshold in `column_grid`, so the draft
  region cannot name it separately.
- **A sub-story shares its parent's columns (page 8).** The golden map gives the
  Taiwan story the columns its sub-story occupies as well; the block contract
  assigns a block to one content owner. ADR 0004 records that this ownership is
  editorial intent, not a printed fact.
- **An alternate column system on one page (page 12).** The story's own band
  grid recovers the five-column system, but one origin lands 12pt from the
  golden value.

These are draft-region differences. They are not compile inputs: the composer
reads the page column grid (ADR 0004). The 18 story ids and one reason each are
recorded in `KNOWN_REGION_DIFFERENCES` in `tests/test_article_map.py`; the test
fails if the set changes, so a new difference cannot join silently.

## Second issue: 2026-10-10

The same pass was run on the held-out issue after parsing it.

- **MinerU parse:** all 55 pages parsed with the pinned MinerU 4.0.7 local
  server (`structured_content`/middle schema 2.0), written beside the issue's
  other evidence. Seven ad pages were skipped by the pass.
- **Reading Pass:** 48 content pages, 138 enumerated items. Reprinted
  continuation headlines were left unassigned rather than enumerated as new
  items; market-data table sections were excluded.
- **Derivation:** 132 records, **0 geometric** and **0 placement-less**, 130 with
  derived paragraphs (1,536 paragraphs), 10 multi-page stories, 1 flagged.
- **Section vocabulary:** the issue prints weekend sections the reference map
  did not: `Review`, `Fall Books`, `Style & Fashion`, `Wellness & Beauty`,
  `Eating & Drinking`, `Design & Decorating`, `Adventure & Travel`. All map to
  the `life` canonical section and are now in `SECTION_MAP`.
- **Two placement fallbacks:** a table or centred list has no line at a column
  edge, and a page of market tables has no recoverable body grid. Both now get
  one union box rather than an empty `regions` list, so the any-issue rule
  "every item has at least one region" holds.

Known limits of this scale run, not defects in the deriver:

- Market-data pages (21, 22) enumerate their table sections as `sidebar` items;
  those whose blocks are all `table`/`chart` are dropped before the cache is
  written. Fifteen legitimate sidebars remain.
- Two forward markers sit on ad pages (35, 45) that the pass does not read, so
  10 multi-page stories are resolved against 11 printed markers. Relative
  markers (`turn to the next page` / `continued from the prior page`) resolve to
  the adjacent PDF page.
- Continuation regions added by `_attach_continuation_regions` are still
  geometric; the record's `regions_source` reflects its start page.

The second issue's cache is
`second-issue-pilot-2026-10-10/evidence/reader-items.json`.

Both caches are reproducible with `render/tracer/reading_pass.py` (ticket #18):

```bash
make reading-pass ARGS="merge --pilot-root P --bundles DIR --answers DIR --out CACHE"
```

The script builds bundles, validates answers (unknown indices and repeated blocks
are warnings; no answer, cross-item duplicates, unmapped sections are errors),
drops table-only and continuation-body items, and reports coverage. It never
calls a model.

## Acceptance against #14

- Answers validate, and every item's blocks map onto native lines by
  containment.
- Reference issue: no record is geometric. The ticket's
  `require_exact_regions=True` wording is stale; ADR 0004 removed that compile
  gate, and the equivalent check is `regions_source != "geometry"`.
- Second issue: the deriver completes and reports 132 items and 1 flagged
  record, which unblocks the scale check in #12.
