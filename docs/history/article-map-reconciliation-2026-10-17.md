# Reconciliation: derived article map vs the reference issue (2026-10-17)

Dated evidence. Records how the derived map compares with the hand-made
`article-map.json` of 2026-10-14, field by field, and where it does not match.

## What matches

| field | result |
|---|---|
| record count | **86 / 86** |
| `start_page` | 86 / 86 |
| `section` | 86 / 86, per-page multiset equal |
| `all_pages` | 12 / 12 multi-page stories |
| `type` | 88.9% exact, 97.5% tier (Jev baseline 86.0% / 93.0%) |
| routing tier | per-item **80 / 80**; distribution 8 / 54 / 9 |
| flagships | 8 / 8, six front page and two business front |
| `continuation_evidence` marker sets | 7 / 12 exact; 2 cite a different line of the same page; 3 have no golden evidence to compare |

The three with no golden evidence are `CASE-B1B2-PRIVATE-EQUITY`, `BOFA` and
`IPOS`: their `continuation_evidence` is `null` in the golden map while
`all_pages` is `[19, 20]`. The derived map cites the printed markers that golden
left unrecorded — more evidence, not less.

## Where it does not match: `regions`

Two geometric models were measured against the golden rectangles.

| model | rectangles ≥ IoU 0.5 | median per story |
|---|---|---|
| per-column text run, jump marker caps the last column | 39% | 0.38 |
| every column × the story's horizontal band | 51% | 0.44 |

Neither is exact, and the cause is structural rather than a tuning problem: **the
paper does not print which columns a story owns.** A column can look nearly empty
(page 14's first column holds two lines of the lead story's text) while the story
still owns it, because a photo or the headline block occupies the space. Two
stories can also share a continuation page as stacked bands, where the reprinted
headline is a *rewrite* — pairing a band to its story would need the
headline-similarity join that `delivery-report.json` forbids.

Measured examples:

- `PILOT-A14-BREWERS` — golden: five columns, y 114–977. Derived: one column,
  y 198–229. The first column carries only the lede's opening.
- `PILOT-B4-PUBLICIS` — golden: one column at x 657–773, y 274–1099. Derived:
  one line.
- `PILOT-B1-PHANTOM` — golden spans a band on page 19 and again on page 24;
  derived picks the neighbouring column on page 19.

## The fix, and why it is not more geometry

| item | detail |
|---|---|
| what is missing | each story's own set of line ids |
| how to get it | the reader already reads the page; add `lines: [line_id, …]` to its answer |
| what it unlocks | exact `regions`, and `body_words` if it is ever wanted again |
| why not more heuristics | five models measured; the best reaches 51%. The information is absent from the print, so more geometry cannot recover it |

Everything that *is* printed is derived and reconciled: folio from each page's
printed id, jump markers both directions, section banners and rubric heads, the
column grid, body typefaces, image-only pages.

## Why this is the right stopping point

The remaining gap is one field. It does not affect routing, tiers, flagships or
the issue's item inventory — all reconciled exactly. It affects the composer,
which needs per-paragraph page/column/y placement, and the composer is not yet
wired to a derived map.
