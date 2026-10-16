# The article map is derived from print signals, host-reviewed only for its semantic label

Status: accepted

`article-map.json` supplies per-story ownership to the pipeline: `id`, `type`,
`section`, `start_page`, `all_pages`, `regions`, `continuation_evidence`,
`title_source`, `byline`. For the reference issue (2026-10-14) it was made by
hand, and `delivery-report.json` recorded the gap:

> "No automated article-map builder: article ownership still requires host
> page-by-page review"

A 2026-10-17 ablation re-measured this rather than reading it. The chain stops at
article discovery, and `article-map.json` has no generator in either repo on any
branch. That gap is now closed by derivation, not by review.

## Decision

Split the article map by how each field is obtained.

**Derived from the printed page (no review, no model):**

- `start_page` — the page carrying the story's first body block.
- `all_pages` — start page plus the folios named by its jump marker. Both
  directions are printed: the start page carries `PleaseturntopageB4`; the
  continuation page carries `ContinuedfromPageOne` or `ContinuedfromPageB1`.
  Measured: 10-14 has 12 jump markers, 12 continuation markers and 12 multi-page
  stories, 1:1; 10-10 has 11 of each.
- `section` — the section head printed at the top of the page. Read directly on
  10-14: `U.S. NEWS` (p2, p6), `BUSINESS&FINANCE` (p19), `HEARD ON THE STREET`
  (p31).
- `continuation_evidence` — the marker line itself, with its `line_id` and
  `bbox`, so it stays auditable.
- folio → PDF page — cross-paired from the two marker directions (page 1 prints
  `turntopageA4`, page 4 prints `ContinuedfromPageOne`, so `A4 -> 4`). Not a
  lookup table.
- `regions` — paragraph ownership resolved against the derived page/column grid.

**Judged (`type`), and flagged for host review when confidence is low:**

- `type` is the only field with no printed marker. Measured on 10-14 across 86
  items: Jev `TypeSafe` 86.0%, host judge 91.9%. Low-confidence items carry a
  flag; the map is a draft until the host confirms them.

## Considered Options

- **Generate the whole map with no review (a).** Rejected. The recorded lesson
  that ownership needs review is not gone; it is superseded only for the fields
  that are printed facts.
- **Keep full host page-by-page review (b).** Rejected. It pays human cost for
  fields that are read straight off the page and are verifiable at a glance.
- **Generate only the routing subset of items.** Rejected. `routing.py` reads
  `id`/`type`/`section`/`start_page`/`all_pages`; `compose.py` also reads
  `paragraphs`, `media`, `byline`, `region`. A routing-only map leaves a
  hole that has to be filled by hand for every later issue.
- **Re-infer continuation by headline similarity.** Rejected, and already
  forbidden by `delivery-report.json` ("no headline-similarity joins"). The
  printed markers make inference unnecessary.

## Consequences

- A new issue's article map is a generated draft with flagged semantic items,
  not a blank file a host fills in.
- `type` remains a model call, so a low-confidence flag is part of the contract
  and must be surfaced in the draft.
- The derivation must reproduce 10-14: acceptance is routing parity (the eight
  derived flagships and their tiers match), with field-level comparison used to
  triage a mismatch. 10-14 is the only anchor — 10-12 has no article map at all.
