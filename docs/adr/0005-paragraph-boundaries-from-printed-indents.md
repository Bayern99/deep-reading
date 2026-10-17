# Paragraph boundaries are read from printed indents, type size and drop caps

Status: accepted

Closes the design question ADR 0004 left open: per-paragraph placement
(`native_regions`) for the composer. The rule is deterministic and print-grounded;
the Reading Pass supplies the item's line or block set, and no extra model call is
asked for paragraph breaks.

## Context

#16 listed three candidate signals — first-line indent, extra leading, or the
Reading Pass answering paragraph breaks — and asked for a design round before
implementation. Measured on the reference issue's 1,106 hand-paragraphs:

- the first line is indented 8.6–12.8pt in 92% of paragraphs; 26 first lines are
  set at body size 9.5pt in a body face;
- a continued line sits within ±2pt of its column edge in 88% of cases;
- a subhead is set at 10.5–12.6pt in `RetinaBold`, while body is 8.4pt;
- a deck is `RetinaLight` at 12.6pt, and a rubric is `RetinaCondensedBold`.

Extra leading is not a usable signal: paragraph gaps are 1.2pt, the same as line
leading. Asking the pass for paragraph starts would add a second judgement to a
pass that already names item ownership, and would still need a printed check.

## Decision

A paragraph is a run of printed lines between two printed starts:

- **First-line indent** of 6–20pt from the *local* body edge. The local edge, not
  the page grid origin, because a figure wrap narrows a column mid-page; the edge
  is the minimum left edge of the previous five printed lines in that column.
- **Subhead size** 10–16pt. A subhead is its own paragraph; the paragraph after it
  starts fresh even when unindented.
- **Drop cap** — one uppercase letter above 20pt starts the paragraph.
- Lines that are not narrative are skipped: display type (≥15pt), bylines (`BY …`),
  rubrics (`RetinaCondensed*`), continuation markers, and the item's headline/deck
  on block answers. Each page restarts the check, so a continuation page's
  reprinted headline is dropped too.

Printed lines are reconstructed first: fragments sharing a baseline belong to one
line unless they sit in different printed columns, and the column is the one whose
content span contains the fragment — nearest-origin snaps a right-edge word into
the next column.

## Considered options

- **Ask the Reading Pass for paragraph breaks.** Rejected. It moves a printed
  signal back into a model call and gives no second opinion when it is wrong.
- **Use extra leading.** Rejected. Measured at 1.2pt, identical to line leading.
- **Keep the hand inventory's paragraph ids.** Rejected. It is the input a new
  issue does not have.

## Consequences

- Reference inventory: 1,086/1,097 predicted boundaries correct (99.0%),
  1,086/1,106 recovered (98.2%).
- The local-edge window is five printed lines. A figure wrap or nested column
  longer than that is the known failure mode; both are rare and visible in the
  paragraph boxes.
- `paragraphs` is a draft field. The composer still reads the issue's approved
  units; wiring the derived map end to end is out of scope.
