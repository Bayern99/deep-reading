# Experiment 0 — Editorial Factual Integrity

Status: implemented bounded gate; isolated reference validation completed. This implements [REPORT Experiment 0](REPORT.md#experiment-0--establish-the-factual-publication-input-contract) against the [seven-story Golden panel](GOLDEN-BASELINE.md). It does not migrate historical artifacts or establish independent editorial approval for every saved page.

Authoritative contract: [Claim Provenance](../../claim-provenance.md). Final machine-readable evidence: [results.json](experiment0/complete/results.json), including implementation hashes. Earlier run directories retain intermediate evidence; `experiment0/complete/` is the final run.

## Outcome

The compiler now rejects the unsupported E1-010 canonical rates, its pseudo-quote and E3-004's pseudo-quote. A source-bound challenge against E1-010's actual saved SVG also rejects the unsupported rates and 18/22/24-basis-point annotations. Supported quotations, corrected calculations, labeled interpretation, conceptual diagrams and quantitative charts still compile, persist, reopen and deliver over HTTP.

The approved narrative path is preserved: every historical panel version retains complete verbatim CN/EN coverage under diagnostic compilation. A narrative-only composition passes strict compilation for all seven stories, even when unused canonical candidates are rejected. The gate does not require every story to use a chart or a generative intervention.

## Investigation and repair boundary

`canonical_builder.py` uses curated derivations for three flagship stories and automatic quote/metric extraction elsewhere. Curated values were treated as high precision; automatic extraction paired the last English/Chinese quote or first numeric match in a paragraph. Neither operation establishes semantic equivalence or factual approval. The E1-010 and E3-004 errors therefore entered the supposedly verified generation libraries before the model composed HTML.

`editorial_compiler.py` previously populated `data-derive` directly from those candidates. It verified exact narrative coverage/order and inventoried some authored headings/SVG numbers, but inventory had no acceptance decision. Its SVG checks concern bounds, not factual data or visual encoding. `context_dossier.text_en` can also contain curated editorial background, so `data-ref="ctx1"` must not be a factual-review bypass.

The bounded repair adds `claim_provenance.py` and passes a caller-authored evidence sidecar through the existing compiler/publisher/raw-import seams. The canonical builder attaches candidate diagnostics without changing any approved body or historical derivation record. Publisher guidance stops describing the candidate libraries as verified; known rejected entries are exposed as rejected, rather than suggested for reuse. No new provider, agent runtime, UI or plugin was added.

The gate inventories canonical quotes/metrics/context and authored document text, text tails, accessibility labels, SVG geometry and retained presentation code. Optional `data-claim` groups an intervention. All active claims need a supported disposition; unavailable evidence is `needs_review`, not hallucination. Invalid evidence/calculation/binding is `rejected`. Diagnostic `strict=False` compilation retains the content and audit for review; strict compilation and new store promotion require a passing gate.

ArtifactStore additionally checks publication source, active canonical claim payloads, compiled-HTML and Shadow-bundle identity. Reusing an old passing report after changing a derivation or delivery content fails. Existing failed-attempt storage preserves rejected generations and the previous active artifact. Historical reopening remains unchanged; old `compiler_audit.passed` does not gain a new factual meaning.

## Deterministic checks and host responsibilities

| Material | Deterministic boundary | Host semantic review |
|---|---|---|
| Direct quotation | Literal contiguous source match in each supplied locale; no invented words or silent quote-to-interpretation relabeling | Speaker/role attribution, quotation context, bilingual pairing; whether a literal fragment distorts the speaker |
| Reported number | Exact source spans; normalized Decimal value/unit membership | Entity, denominator, horizon, survey versus observation, uncertainty and comparison meaning |
| Calculation | Source operands/token indexes; finite operations; explicit rounding; exact result/unit and display match | Whether operands are legitimately comparable and the calculation answers the intended editorial question |
| Factual explanation | Exact source/claim binding; any numeric claims must pass literal/calculation checks | Entailment, attribution, omitted qualifiers and invented causality |
| Interpretation | Bound evidence and review; visible interpretation label; numbers remain checked | Explain interpretive value and uncertainty; distinguish editorial reasoning from reported fact |
| SVG | Hash binds complete markup, coordinates and labels; numeric data must have support | Series, scale, geometry, causal arrows, hypothetical scenarios and reading semantics |
| Axis ticks | Specific bound `<text>` node, exact label/index and reviewed `axis_tick` role | Verify it is a scale marker, not a data observation mislabeled to bypass checking |
| Retained script/CSS content | Bound presentation-code payload requires review | Inspect any dynamic factual output; no assertion of a general executable-content security policy |

The minimal record contains schema, target, source/claim digests, exact `{block, locale, text}` spans and a reviewer disposition/reason. A calculation optionally adds operation, operand indexes, result, unit and rounding. Axis presentation annotations optionally identify exact scale-label nodes. These records are accepted from the host API caller, never from generated HTML. They are attestations, not authenticated or independent human judgments.

## Historical panel detection

Final replay uses the exact nine versions identified in the Golden Baseline. The stored original files remain unchanged. Counts below are active **review targets**, not counts of false facts; ungrouped historical layouts can yield many small text targets.

| Story/version | Verbatim CN / EN | Deterministically rejected active canonical candidates | Active targets needing review |
|---|---|---|---:|
| E2-001 v1 | 20/20 · 20/20 | q1, edited/stitched quotation | 69 |
| E2-001 v2 | 20/20 · 20/20 | q1, edited/stitched quotation | 98 |
| E2-001 v3 | 20/20 · 20/20 | None used; q1/q4 remain rejected unused candidates | 93 |
| E2-002 v2 | 38/38 · 38/38 | None | 155 |
| E1-010 v1 | 20/20 · 20/20 | q1, m1, m2, m3 | 132 |
| E3-004 v1 | 22/22 · 22/22 | q1 | 91 |
| E2-010 v1 | 14/14 · 14/14 | None | 74 |
| E1-024 v1 | 7/7 · 7/7 | None | 85 |
| E3-001 v2 | 7/7 · 7/7 | None | 84 |

All nine historical layouts need sidecars before **new** verified publication under this contract. This result does not declare all their additions false. E2-001 q1 combines reported quotations with punctuation/word edits; its failure means the current literal quotation representation is unsuitable, not that the reported speaker or ideas are fabricated. q4 changes terminal punctuation and is not active in these runs. Preserve these historical compositions and correct experimental quote payloads or use explicitly labeled paraphrase rather than weakening the literal check.

E1-010's canonical errors:

| Claim | Saved candidate | Accepted source | Result |
|---|---|---|---|
| m1 | 4.12% versus 3.94% | p4: end-2026 5.1% versus 4.4% | Rejected |
| m2 | 4.09% versus 3.87%, end-2027 | p5: mid-2027 4.96% versus 4.3%; end-2027 4.78% versus 4.26% | Rejected |
| m3 | 4.16% versus 3.92%, end-2028 | p5 supplies no such 2028 comparison | Rejected |
| q1 | “The bond market is adjusting to a world of higher neutral rates…” | Absent from the cited paragraph and full source | Rejected in both locales |
| E3-004 q1 | “In every major technological shift in history…” | Absent from the cited paragraph and full source | Rejected in both locales |

The actual saved E1-010 comparison SVG was tested with all source paragraphs available and a **deliberately permissive negative-test review**. Its five y-axis tick nodes were explicitly distinguished from data labels. The gate still rejected 3.94/4.12, 3.87/4.09, 3.92/4.16 and the 18/22/24-bps annotations. The separate saved comparison SVG had source-present numbers and cleared this numeric challenge; that permissive test disposition is not independent approval of its visual/economic meaning.

## Supported reference delivery

[E1-010 experimental output](experiment0/complete/E1-010-compiled.html), [raw anchors](experiment0/complete/E1-010-raw.html), [evidence records](experiment0/complete/E1-010-evidence.json):

- End 2026: 5.1% versus 4.4%, **70 bps**.
- Mid 2027: 4.96% versus 4.3%, **66 bps**.
- End 2027: 4.78% versus 4.26%, **52 bps**.
- Four supported interventions; a zero-based July/October comparison SVG remains available. Explicit review ties each forecast to its horizon and verifies consistent bar scale.
- Narrative matches **20/20 in both locales**. Strict compilation, isolated version save, active reopening and byte-identical HTTP compiled delivery pass.

[E3-004 experimental output](experiment0/complete/E3-004-compiled.html), [raw anchors](experiment0/complete/E3-004-raw.html), [evidence records](experiment0/complete/E3-004-evidence.json):

- The actual p2 warning, “AI wants to be God,” and its approved Chinese translation, with attribution established by p1/p2.
- A visible bilingual editorial interpretation distinguishes the pastor's concern from an authorial assertion that AI has religious intentions.
- An attribution diagram remains valid; no fabricated theological quotation or causal magnitude is introduced.
- Five supported interventions. Narrative matches **22/22 in both locales**. Strict compilation, isolated version save, active reopening and byte-identical HTTP delivery pass.

These are factual/reference compositions, not a redesign or a claim to improve the historical Golden pages' aesthetics. No external model calls occur in this replay. Both examples are rejected when modified without new valid evidence, and their previously supported isolated versions remain active.

## Checks performed

- `make test`: **26 unittest cases passed**, including nine provenance regressions; the separate legacy gate assertions also passed.
- Provenance regressions cover known pseudo-quotes/false rates; correct canonical `data-derive` injection; correct quotes/calculations/interpretation/SVG import; bad arithmetic and unit substitution; unreviewed content and injected-field spoofing; stale source/claim/geometry/delivery hashes and mutated canonical input at store admission; failed imports preserving active versions; semantic rejection; unsupported context; valid axis ticks while false observations still fail. Hyphenated forecast labels and Chinese `个基点` are included to prevent notation false positives.
- Final replay: seven stories/nine historical versions, strict narrative-only acceptance for all seven, two supported stored/delivered reference artifacts, actual saved-SVG negative challenge and Reader HTTP.
- Malformed-evidence smoke rejects a non-list span collection, an unhashable block identifier and a null span without accepting them or crashing.
- `make smoke`: both real builds, whole-issue copy/order and equal baseline assets, local Studio/Reader HTTP, 117 inputs, 92 published items, 21 stored article identities. No model calls in this isolated smoke.
- Successful replay hashes **201 protected files** before/after, including `final.json`, versions, index/latest records and queue; hashes match. Final source remains `00fa35e8f5a9bc164da3dae3af41c6b659c1e2c609d1e535729a6fbb3efd5782`.

An initial acceptance invocation exposed a pre-existing fixture hazard: `collect_issue_payload` can resume the live queue. Queue timestamp fields changed during that check. The queue was restored byte-for-byte to the recorded protection snapshot, and the affected tests now copy source/artifacts into a temporary fixture while omitting the queue. Final acceptance and replay use isolated inputs. No approved body or historical version was overwritten.

Reproduce with a new evidence directory:

```bash
make test
make smoke
.venv/bin/python scripts/experiment0.py --output /tmp/wsj-experiment0-new-evidence
```

The command refuses an existing output directory or an output inside the protected issue. Temporary issue versions are removed after the evidence is retained. The replay does not start a live production queue.

## Next bounded rollout

1. Use the Python diagnostic/import seam for a small real editorial batch. Give host reviewers source spans, expected reader benefit and explicit factual/interpretive roles. Collect disagreements about attribution, forecast horizons, chart scale and causal arrows before generalizing policy.
2. Group related authored labels/captions/graphics with `data-claim` to reduce the observed 69–155 review targets per historical page. Retain complete payload hashing and the audit of ungrouped remainder; do not replace evidence with a blanket artifact-level approval.
3. Freeze per-version canonical publication input and sidecar in the workflow; the existing mutable `canonical.json` is still only the latest snapshot. This experiment already preserves exact records/digests in each new version's compiler audit.
4. Expose factual state separately from historical narrative verification and browser acceptance when a later workflow/UI task is authorized. Existing Studio/queue cannot submit a review sidecar in this experiment; unsupported generation stops, and the host can review then import.
5. Add an independently approved external-source snapshot namespace and further deterministic calculation operations only for concrete editorial cases. Then decide how this gate applies to remaining publishing paths.

Semantic entailment, arbitrary SVG encoding, external evidence and visual quality remain bounded human/host responsibilities. The experiment supplies the missing enforceable factual-input boundary without treating all explanation as hallucination or banning new visual content.
