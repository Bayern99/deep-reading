[ English | [简体中文](0005-paragraph-boundaries-from-printed-indents.zh-CN.md) ]

# Read Paragraph Boundaries from Printed Indents and Type

**Status: accepted**

This closes the placement question in [ADR 0004](0004-page-column-grid-not-story-regions.md). Paragraph placement (`native_regions`) is deterministic and print-grounded. The Reading Pass supplies the item's line or block ownership; it does not decide where each paragraph begins.

## Context

Candidate signals included first-line indentation, extra line spacing, and asking the Reading Pass to identify every paragraph. Extra spacing is unreliable because paragraph gaps may equal normal line leading. Asking for paragraph starts adds another semantic task to a pass that already identifies item ownership, and still requires a printed check.

## Decision

A paragraph is a run of reconstructed printed lines between two printed starts. Apply these signals:

- **First-line indent:** 6–20pt from the *local body edge*. The local edge is the minimum left edge of the previous five printed lines in that column, not the page grid origin. A figure wrap or nested column can narrow the body measure partway down the page; an offset larger than 20pt may be a wrap, not a new paragraph.
- **Subhead size:** 10–16pt. A subhead is its own paragraph. The prose after a subhead starts a new paragraph even if its first line has no indent.
- **Drop cap:** one uppercase letter above 20pt starts the paragraph.
- **Exclude non-narrative lines:** display type at or above 15pt, bylines (`BY …`), rubric labels in `RetinaCondensed*`, continuation markers, and an item's headline or deck when the Reading Pass provides a whole block. Reprinted continuation headlines are removed only when the printed backward marker and the display-font signal agree. Restart the check on every page.

Reconstruct printed lines before detecting paragraph starts. Fragments sharing a baseline form one line when they occupy the same printed column. Determine the column from its content span, so a fragment at the right edge belongs to the next column only when it actually crosses into that printed measure.

The font roles provide useful checks: body faces include `Exchange*`, `DJ5*`, and `RetinaBook`; a `RetinaLight` deck and a `RetinaCondensed*` rubric are not narrative body lines. Do not use extra leading as a paragraph-start signal.

## Considered options

- **Ask the Reading Pass for paragraph breaks:** rejected. A judgement should not replace a printed signal, and an incorrect answer would lack a second opinion.
- **Use extra leading:** rejected. Paragraph space and ordinary line leading may be indistinguishable.
- **Keep hand-authored paragraph IDs as tool inputs:** rejected. A new external issue workspace must be able to derive its own paragraph IDs from printed lines.

## Consequences

- A synthetic example: when a new paragraph's first line begins about 10pt inside the local body edge, that is a paragraph-start candidate; a 25pt offset is not accepted by this rule.
- The five-line local-edge window is part of the rule. A figure wrap or nested column that extends beyond that local window can confuse the boundary; inspect the resulting paragraph boxes when the layout changes the measure.
- Each derived paragraph keeps page, column, and bounding-box evidence so the composer can order paragraphs and anchor figures in physical print order.
- Paragraphs derived from a Reading Pass are a draft until their source lines bind correctly. Final composition uses approved issue units.
