# The composer reads the page column grid, not per-story regions

Status: accepted

Amends [ADR 0003](0003-derived-article-map.md), which lists `regions` as derived
from the printed page.

`regions` has exactly one consumer in the product: `compose._column_origins`,
which reads nothing from it but `column_origin`, per page, to turn an x coordinate
into a column ordinal. That is a property of the **page**. Which columns a story
owns is not printed; it is editorial intent, and it is ambiguous wherever a
sidebar or a sub-story shares a belt — on page 8 the reference issue's hand-drawn
boxes give the Taiwan story the two columns its sub-story occupies.

Three attempts to derive per-story column sets from the printed page measured 54%
(geometry), 77% (MinerU `doc_title` anchors) and 80% (band grid), and only reach
100% with a hand-read line set per story. A wrong column set reorders the printed
page, so it is a reader-visible error, not a diagnostic.

## Decision

The composer takes each page's column grid from the vector lines — the same
projection that recovers the grid for every other purpose. Per-story `regions`
remain in the map as a **draft** field, carrying `regions_source` and
`needs_review`, and are never a compile input.

## Considered Options

- **Derive per-story regions exactly.** Rejected as a compile input. Measured
  ceiling is a hand pass per story; the information is not on the page.
- **Keep per-story regions and accept the error rate.** Rejected. The failure
  mode is silently wrong figure placement.
- **Delete `regions` entirely.** Rejected. It is the auditable record of where a
  story ran, and the reading pass can make parts of it exact.

## Consequences

- `require_exact_regions` stops being a compile gate.
- `native_regions` — per-paragraph page, column and bbox — becomes the remaining
  gap for composing a new issue, and it is tractable: paragraph starts are
  printed as first-line indents.
- A future reader of `regions_from_lines` must not assume the field is a compile
  input; ADR 0003's bullet for `regions` is amended here.
