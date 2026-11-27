[ English | [简体中文](0004-page-column-grid-not-story-regions.zh-CN.md) ]

# Compose from the Page Column Grid, Not Per-Story Regions

**Status: accepted**

This decision refines [ADR 0003](0003-derived-article-map.md): the page column grid is a printed page property; a story's exact column ownership is not necessarily printed.

Stories may share a horizontal band when a sidebar, sub-story, or short item appears beside a main story. Guessing a story's region can reorder text or place a figure at the wrong point. These are visible reading errors, not harmless diagnostics.

## Decision

The composer uses each page's column grid derived from its printed vector lines. A column ordinal is computed from the page grid and the element's horizontal position. Per-story `regions` remain a draft record with `regions_source` and `needs_review`; they are never a compile input.

## Considered options

- **Infer every story's exact column set:** rejected as a compile input. Story ownership can be ambiguous where items share a page band; requiring a hand-read line set for every story defeats deterministic reuse.
- **Accept approximate per-story regions:** rejected. A wrong column set silently changes physical reading order and figure placement.
- **Delete `regions`:** rejected. Regions remain useful as an auditable draft and may be refined by the Reading Pass. They are simply not authoritative for compilation.

## Consequences

- The page column grid drives paragraph and figure order on a page. The composer uses the printed line geometry, not a story bounding box, to determine a column.
- `regions` and `regions_source` describe what is known and how it was obtained. `needs_review` identifies unresolved ownership. A consumer must not treat these fields as a compile contract.
- Paragraph-level native placement (`native_regions`) remains useful for anchoring authored material and figures. It is derived from owned printed lines and paragraph boundaries, not guessed from the story rectangle.
- Do not restore an exact-region compile gate. If a future layout needs story-owned regions, define a separate evidenced rule and human review boundary first.
