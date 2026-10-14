# Claim Provenance Contract

Implemented by [`render/claim_provenance.py`](../render/claim_provenance.py). Experiment evidence: [Experiment 0](research-2026-10-14/EXPERIMENT-0.md). Scope: new canonical-derived and authored content passing through the generated-article compiler and ArtifactStore. Approved narrative, source repairs, historical artifacts and the deterministic whole-issue renderer retain their existing contracts.

## Trust boundary

Canonical narrative is the lossless bilingual projection of approved source. `derived_quotes`, `derived_metrics` and background context are **candidates**, not evidence of their own truth. A `source_block` identifies a place to check; it does not prove entailment. Automatic extraction can select different quotations or numbers in the two locales; it never supplies semantic approval.

The compiler inventories canonical candidates and authored content throughout the document. An authored **intervention** — `figure`, `aside`, `table`, `blockquote`, `section`, `svg`, or any `data-claim` element — is one **review unit**: its heading, copy, data labels, accessibility attributes and drawing share a single evidence record, addressed as one `html:<XPath>`. Only the outermost such element is a unit, so a comparison figure is one target rather than one per text node. Loose authored text, tails and accessibility attributes outside any intervention stay individually inventoried. SVG payload hashes cover the complete markup, including coordinates, paths, labels and attributes. Retained scripts and styles containing CSS `content` are inventoried as presentation code. Fixed language-control labels and fully injected narrative/excerpts are exempt. `ctx1` remains injectable but its context candidate requires evidence when used.

## What has to be reviewed

`host_review_required` decides deterministically, per target, whether a record is required. It is true for every canonical candidate (`derive:`, `context:`), every chart/SVG, every direct quotation, every presentation-code target, every authored intervention, and every loose text or attribute that carries a number or quotation marks. It is false for loose typography, headings, labels and decorative text with no number and no quotation mark: those stay in the audit as `disposition: inventoried_not_gated` and do not gate publication. The audit's `summary` reports `active_targets`, `host_review_required` and `inventoried_not_gated`.

Merging is not an exemption. A unit's `text` is the authored copy inside it, so every number and every quotation in a merged intervention is still extracted and still compared against the record's spans. A wrong figure inside a reviewed comparison figure fails as `Numbers absent from evidence/calculation`. Quote-marked strings and `<blockquote>`/`<q>` descendants are checked verbatim whatever `kind` the record uses, so relabelling a unit as `fact`, `interpretation` or `chart` cannot drop the literal check. Any content change invalidates the record through `claim_digest`.

A candidate has one of three states:

| State | Meaning | New publication |
|---|---|---|
| `supported` | Literal checks pass and the caller supplies a source-bound semantic disposition | Allowed, subject to narrative/structure checks |
| `needs_review` | Evidence or semantic review is missing | Diagnostic compilation only; no verified promotion |
| `rejected` | Evidence, arithmetic, binding or semantic disposition fails | No verified promotion |

Missing evidence does **not** establish hallucination. Interpretation and conceptual diagrams remain legitimate editorial work. They require explicit review; an interpretation must have a visible `Editorial analysis` / `Interpretation` / `编辑解读` / `编者解读` label. Its factual numbers still need support. Attribution, uncertainty, causal arrows and comparison semantics remain review responsibilities.

## Minimal Evidence Record

The host supplies `evidence_records=[...]` as a Python API argument. Generated HTML cannot supply or approve these records. Use `make_evidence_record(canonical, inventoried_claim, ...)` to calculate bindings; it does not approve a claim.

```json
{
  "schema_version": "claim-evidence-v1",
  "target": "derive:m1",
  "kind": "calculation",
  "source_digest": "<SHA-256 of the publication source projection>",
  "claim_digest": "<SHA-256 of the exact inventoried claim payload>",
  "spans": [
    {"block": "p4", "locale": "en", "text": "5.1%"},
    {"block": "p4", "locale": "en", "text": "4.4%"},
    {"block": "p4", "locale": "en", "text": "<exact surrounding source text establishing horizon and pairing>"}
  ],
  "calculation": {
    "operation": "basis_points_change",
    "operands": [{"span": 0, "token": 0}, {"span": 1, "token": 0}],
    "result": "70",
    "unit": "bps",
    "decimal_places": 0
  },
  "review": {
    "decision": "supported",
    "reviewer": "<host reviewer identity>",
    "reason": "p4 pairs October 5.1% with July 4.4% for end-2026; these remain survey forecasts, not guaranteed yields."
  }
}
```

Targets are `derive:<id>`, `context:ctx1`, or automatically inventoried `html:<XPath>` addresses. Do not author guessed XPath addresses: consume the diagnostic inventory. A DOM move changes the target; a content/geometry change changes the claim digest. Unknown and duplicate targets fail rather than silently dropping records.

Kinds: `quote`, `number`, `calculation`, `fact`, `interpretation`, `chart`, `nonfactual`. `nonfactual` is an explicit host disposition for navigation/section labels or presentation code, not an exemption from numeric checks on reader text. SVGs require `chart`; canonical/direct quotations cannot be relabeled as interpretation.

Spans are exact, nonempty substrings of the specified `pN` block and locale (`en`/`cn`). Quotes require contiguous literal support after whitespace and outer-quotation-mark normalization. Punctuation/word edits and stitched quotations need an explicitly corrected experimental quote or a labeled paraphrase; semantic review cannot waive failed literal checks. For canonical quotes, each locale must independently match its evidence. Speaker, role, attribution and cross-language pairing still require semantic review.

Numbers use `Decimal`, preserving units: percent, basis points, USD and plain numbers. Recognized currency magnitudes include million/billion/trillion, K/M and 万美元/亿美元/万亿美元. Chinese `70个基点` and English `70 bps` are equivalent units. Numeric presence is a necessary check, not proof of the right entity, year, denominator or forecast status. Those relationships belong in the review reason and surrounding spans.

Calculations support two source operands, explicit token indexes, and `difference`, `sum`, `ratio`, or `basis_points_change`. Percentage-point differences convert to bps by multiplying by 100. Results use `ROUND_HALF_UP` at the declared 0–8 decimal places (default 0), must equal the recorded result/unit, and must appear in the displayed claim. No executable expressions, float tolerance or model arithmetic is trusted. Other mathematics needs a bounded deterministic extension before automatic publication; a semantic approval cannot override unsupported arithmetic.

`review.decision` is `supported` or `rejected`; supported records require a reviewer and substantive reason. This is a trusted-caller attestation, not authentication or independent human approval. The host must read the evidence and rendered intervention. The generating model's own assertion, a confidence score or `verified=true` is insufficient.

Chart scale ticks are presentation labels, not reported observations. An optional `presentation_numbers` list can identify a specific SVG `<text>` node by its one-based `text_index` within the bound chart payload, exact `text`, `role: "axis_tick"` and a review `reason`. The host must verify that role. Only that node's text is excluded from source-number matching; another plotted label with the same number remains checked. Geometry and role annotations remain bound to the reviewed payload. This permits a zero baseline and intermediate scale ticks without manufacturing source evidence. Misclassifying a data label as a tick is a semantic-review failure, not something numeric membership can decide.

## Identity and persistence

The existing narrative `content_digest` remains unchanged. An additional source digest binds issue date, article ID, narrative digest, actual blocks, metadata and context. Each claim digest separately binds the complete derivation object or authored text/markup. Changing a curated value, label, attribution or SVG path invalidates that claim's review even if the narrative digest stays constant.

The audit preserves the records, claim outcomes and source digest. Whole compiled-HTML and Shadow-DOM bundle digests bind delivery to the checked result. `ArtifactStore.save_verified_artifact` requires a passing current claim gate, unchanged active canonical claim payloads and matching delivery digests before writing a new version. Failed imports retain their audit in the existing failed-attempt mechanism and leave the active version intact. Reading or deliberately selecting a historical saved version does not silently certify it under this new contract.

Unused canonical candidates remain visible in the audit but do not block an artifact that does not publish them. A narrative-only article still compiles without a semantic sidecar. `data-ref`, sentence anchors, highlights, `data-derive`, arbitrary SVG/CSS composition and the existing store format remain available.

## Host procedure

1. Build canonical source and inspect its candidate audit. Preserve the approved source and all saved versions.
2. Compose anchored HTML. Run `compile_editorial_artifact(raw_html, canonical, strict=False)` to inspect narrative and claim diagnostics. This result is **not publishable** if its audit fails.
3. For each target whose `host_review` is true, provide exact source spans. Verify calculations. Review quotation attribution, factual interpretation, uncertainty, bilingual agreement, chart scales/series/geometry and accessibility text. Review the unit as a whole; its internal numbers and quotations are checked deterministically.
4. Bind records to the diagnostic targets and exact payloads. Recompile with `strict=True, evidence_records=records`.
5. Import using `import_raw_generation(..., evidence_records=records)`. Inspect visual delivery separately. The compiler does not certify mobile readability or graphic legibility.

Publisher generation uses the same gate. Missing semantic review stops the automatic repair loop and records a failed attempt; the generating model cannot review itself. Existing Studio/queue entry points have no evidence-review UI in this experiment. A host can finish review and import through the Python seam. UI/runtime/model-service/plugin work is outside this change.

## Limits and rollout

This contract checks immutable local issue evidence, not arbitrary URLs or external background claims. Independently approved external source snapshots need a future evidence namespace. Unit extraction does not establish semantic entailment. Chart geometry is hash-bound and reviewed, not numerically reverse-engineered for all possible SVG encodings. Presentation-code review requires the host to inspect dynamic output; this is not a complete executable-content security policy.

A `section` used as a broad layout wrapper becomes one coarse unit: the numbers inside stay individually matched, but a single review reason has to cover the whole block. The publisher prompt therefore asks for one visual idea per intervention block. Author the boundary deliberately; splitting a wrapper into `figure`/`aside` blocks gives finer review without weakening any check.

Next: validate a small batch of real Publisher output with independent editorial review; freeze per-version publication inputs and records; expose factual state separately from historical narrative verification and visual acceptance. Extend the same claim contract to remaining publishing paths only after these reference cases are calibrated.

## Calibration on the pinned panel

Nine historical generations of `2026-10-12` carry 888 active targets under per-text-node inventory and 24 per article under intervention units, with no numeric token outside gated review. `scripts/experiment0.py` records the current counts under `claim_provenance.summary`.
