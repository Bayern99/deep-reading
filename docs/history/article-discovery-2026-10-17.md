# Article discovery: the measurement record (2026-10-15 → 2026-10-17)

Dated evidence, not current authority. Current authority: [FOUNDATION](../../FOUNDATION.md),
[ARCHITECTURE](../../ARCHITECTURE.md), [ADR 0003](../adr/0003-derived-article-map.md).

This file records what the second-issue / reusability exploration measured, so the
measurements are one page instead of scattered across three working directories
outside Git. It exists because the decisions in ADR 0003 rest on them.

## What was asked

Can the pipeline compile an issue other than 2026-10-14? The exploration narrowed
this from "make it reusable" to a single measurable gap: **article discovery** —
turning an issue's pages into a set of source items with ownership.

## Measured on 2026-10-14 (86 items, 8 known flagships)

| Measurement | Result | Where it now lands |
|---|---|---|
| Print signals that transfer with zero human input | flagship rule reproduces all 8 at zero error | `routing.py:is_flagship`, shipped `1955e8e` |
| Whole-issue discriminators, false positives / negatives against the 8 | measured; the surviving rule is section-front + cross-page + body extent | ADR 0003 flagship clause |
| `brief` vs `article` separated by body-word threshold | **0/55 misclassified at 150 words** | basis of the Tier rule; no model needed |
| Jev (`TypeSafe`) on `type` | 86.0% exact | ADR 0003: `type` is the judged field |
| Host judge on `type` | 91.9% exact | same |
| Jev errors in Tier terms | 6 of 86 change tier → **93.0% tier accuracy**; all six err `brief → article` | Tier rule must catch `brief` by print, not by model |
| Jev confidence < 0.85 | 17/86 items (20%), precision in that band 47.1%; above the band 94.2% | confidence threshold flags 17 items, not 86 |
| Jev on the flagship question | 4/12 against the rule; **11/12 against the printed fact of what page the story starts on** | ADR 0003: models answer printed facts, not our editorial policy |

## Rejected hypotheses (measured, then discarded)

Recorded so they are not retried. Each was measured, not merely doubted.

- **Headline-similarity joins for continuation.** Explicitly forbidden by
  `delivery-report.json`, and re-confirmed: 10-10 segmentation bundled pages
  `[1, 2, 7, 10]` into one story.
- **Cross-page assembly by region projection.** Measured on 10-14: 6 multi-page
  stories, 1 closed (BOFA 97%); the rest 19–40%. Layout is column-parallel, and
  the paper carries no marker for which pages a story spans. Stopped rather than
  tuned.
- **Jev for the flagship decision.** It answers page facts well, editorial policy
  poorly; the policy belongs in reviewable code.
- **Model for the whole 11-class `type`.** Slower than the host judge (3.5×) and
  less accurate; only the Tier-relevant slice matters.
- **The claim-provenance sidecar.** Superseded 2026-10-16; see the historical index.

## The ablation (2026-10-17)

Ran the upstream chain against 2026-10-10 with the real scripts, recording the
first failure at each step. It stops at step 3: `article-map.json` has no
generator on any branch, and every script that mentions it only reads it. The
project had already written this down in
`first-issue-pilot/delivery-report.json` — *"No automated article-map builder:
article ownership still requires host page-by-page review"* — which the ablation
rediscovered by measurement instead of by reading that file first.

An adversarial pass then tried to falsify the finding and could not.

Downloads downstream (translation, review, post-edit) were not run to completion:
they cannot be, since step 3 has no input. So this records the first missing
input, not every later fragility.

## What remains unverified

- `regions` at paragraph precision — deferred by ADR 0003 to its own round.
- The second issue end-to-end — never attempted.
- Whether the derivation generalises past 10-14 — 10-10 gives a scale check
  (~131 items over 55 pages) but no golden answer to compare against.
