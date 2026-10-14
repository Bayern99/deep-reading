# Editorial Golden Baseline — research evidence panel

Research date: 2026-10-14. Status: version-pinned capability baseline, **not a declaration that every saved page is release-approved**. No source, artifact, active pointer, queue or production implementation was changed. The [main report](REPORT.md) defines the next experiments and acceptance process.

## 1. What is frozen

The isolated snapshot contained one issue, 117 source items, 21 stored article identities and 38 verified versions. Its index timestamp was `2026-10-14T14:16:16Z`; these counts differ from the earlier governance snapshot, which had eight identities and 11 versions. Live production had user-owned changes and was not started by this research.

Nine generated versions across seven stories were selected deliberately for capability coverage, not randomly:

| Story | Versions inspected | Capability represented | Baseline role |
|---|---|---|---|
| E2-001, private credit | v1, v2, v3 | Financial investigation; policy mechanics, capital flow, return comparison; same-source design variation | Principal generative capability comparator, with version-specific interaction caveats |
| E2-002, hacked cameras | v2 | Long investigation; six source subheads, physical mechanism, technical explanation | Investigative reading/composition comparator; clipping and repetition challenge |
| E1-010, bond yields | v1 | Quantitative analysis; comparison as the visual center | Aesthetic capability comparator **and factual-rejection challenge**, not an approved factual golden page |
| E3-004, AI and religion | v1 | Essay/humanities; opening scene, literary type, conceptual relations | Literary capability comparator **and quote/control challenge**, not blanket approval |
| E2-010, Sunday scaries | v1 | Human-interest narrative; personal scenes, work boundaries, survey evidence | Narrative/pacing comparator; assess whether the three SVGs earn their place |
| E1-024, rogue model | v1 | Seven-paragraph short report with meaningful actor/action/disclosure relationships | Short-but-complex treatment challenge; do not force text-only solely because of length |
| E3-001, Amazon/Decart | v2 | Seven-paragraph business report; acquisition uncertainty, valuations and hardware relationships | Short quantitative comparator **and responsive-rejection challenge** |

The hashes, byte sizes, source digests and fresh compiler results are in [artifact-manifest.json](evidence/artifact-manifest.json). The final source SHA-256 is `00fa35e8f5a9bc164da3dae3af41c6b659c1e2c609d1e535729a6fbb3efd5782`. Read the pinned `vN`, not `latest.json`, for future comparison.

A second comparator is the **deterministic reading floor**: an isolated `make build` equivalent produced `index.html`, `baseline.html` and receipts. The ordinary/no-intervention baseline shares source repairs and assets with its enhanced counterpart. The newspaper had 92 published items, five plans and 18 loaded images. This is the counterfactual to “generate everything,” not a lesser-quality disposable output.

The isolated copy is a research snapshot, not a transactionally locked backup: the source checkout could have another writer. Hashes pin the actual inspected files; they do not certify production backup consistency.

## 2. Verification actually performed

- `.venv/bin/python scripts/smoke.py --keep`: both real build commands, local Studio/Reader HTTP, complete source inventory and saved-artifact audits passed; no model calls; production queue omitted from copy.
- For all nine selected versions, rebuilt canonical input from the copied final source and ran `compile_editorial_artifact(raw_html, canonical, strict=True)` **in memory**. All nine passed; stored and current narrative source digests matched.
- Exact narrative results: E2-001 20/20 both locales, E2-002 38/38, E1-010 20/20, E3-004 22/22, E2-010 14/14, E1-024 7/7, E3-001 7/7. These counts are canonical units, not a measure of editorial quality.
- Chromium standalone inspection: nine versions × 1440/390 CSS pixels × requested CN/EN = 36 observations. Actual locale is recorded separately from requested locale. Four EN requests failed to change language; these are **not English inspection passes**.
- Saved Reader inspection: eight version selections × two widths × two locales = 32 observations. Reader outer controls changed both document and artifact-host locale in every observation, including E2-001 v1/v3. The Reader used the existing Shadow DOM adaptation; no generation controls were invoked.
- Newspaper: four width/locale observations; 92 articles, 18/18 loaded images, no document horizontal overflow. The Sunday narrative was also opened in the actual newspaper.
- Read article bodies, headings, diagrams and authored additions against selected final/canonical text. Inspected representative head/body screenshots; DOM observations cover the full text but do not equal a human reader study of every paragraph.

Raw measurements: [standalone](evidence/browser-observations.json), [Reader](evidence/reader-observations.json), [newspaper](evidence/newspaper-observations.json), [derived-content findings](evidence/derivation-findings.json).

Widths were Chromium desktop emulation at 1440×900 and 390×900, device scale factor 1, not physical-phone testing. Fonts were awaited. A classic scrollbar consumed 15px in many observations. No Safari, Firefox, screen-reader or offline-font test was performed. Screenshot scrolling used instant browser-side scroll to avoid mislabeling a smooth-scroll intermediate state as the target diagram.

## 3. Successful editorial choices worth retaining

### 3.1 Private credit: make the mechanism visible without rewriting the reporting

The three versions preserve the same 20 bilingual narrative blocks while materially varying chapter boundaries, forensic rails and exhibit placement. v2 has five SVGs; v1/v3 have three. **There is no basis for treating “more diagrams” or the active/latest version as inherently better.**

v3 separates the household, insurer and private-credit destinations spatially. The diagram supplies a relational view across dispersed paragraphs; prose remains the main reading path. Its participation-rate trajectory and annualized-return comparison express different relationships and should not be collapsed into one generic key-number widget. Warm paper, serif body, thin rules, restrained accent and dark evidence areas establish article identity without a conventional web-app card grid.

Preserve: source anchors; asymmetric desktop prose/evidence relationships; explicit captions; Chinese/English typography; readable single-column prose; support for several valid compositions of the same story. Review risk: return benchmarks have different risk/guarantee profiles; a graphic must not imply economic equivalence or an invented causal magnitude. v2's right-hand policy exhibit visibly clips part of its text despite no document overflow.

Evidence: [v3 mechanism/prose](evidence/E2-001-v3-1440-zh-CN-body.png), [v2 alternative](evidence/E2-001-v2-1440-zh-CN-body.png), [v3 mobile](evidence/E2-001-v3-390-zh-CN-head.png), [Reader English/mobile](evidence/reader-E2-001-v3-390-en.png). Corresponding files: `2026-10-12/editorial-artifacts/E2-001/v1|v2|v3/compiled.html`.

### 3.2 Camera investigation: preserve reporting structure and explain a concrete mechanism

v2 keeps the six source section headings rather than inventing a competing chapter system. Its scene-to-mechanism move—from a border chicken coop to camera reorientation—explains why a mundane civilian device becomes military infrastructure. The technical rail belongs beside the relevant reporting, not on a disconnected landing page. Body order survives across 38 canonical units.

Preserve: source subheads, verified reporting, anchored technical explanations, desktop relation between prose and notes, mobile placement after the relevant paragraph. Do not inherit its weaknesses: the photographed diagram viewport clips a label on the right; a pull-quote repeats the adjacent emphasized body sentence. A valuable explanation and an unnecessary quote can coexist in one otherwise strong artifact.

Evidence: [investigation body and technical rail](evidence/E2-002-v2-1440-zh-CN-body.png), [mobile body](evidence/E2-002-v2-390-zh-CN-body.png).

### 3.3 Bond analysis: quantitative comparison can carry the composition

The generous comparative field, differentiated forecast series and explicit horizons make the survey relationship easier to inspect than scattered prose figures. This is an important capability to preserve. It is **not** permission to copy the current data. The actual chart and canonical derived metrics contradict the narrative; see §4.1.

Future acceptance: reproduce or improve the comparative reading benefit using verified values, horizon labels, units and attributed uncertainty. A beautiful chart with false values is unacceptable, even with 20/20 copy exactness.

Evidence: [comparative field](evidence/E1-010-v1-1440-zh-CN-body.png); source `final.json` E1-010 and `canonical_builder.py:195–241`.

### 3.4 Humanities: typography and narrative rhythm, not compulsory data charts

The AI/religion page uses an opening scene, literary serif hierarchy and chapter breathing room. Its conceptual triangle attempts to clarify competing institutions and concerns rather than pretending the essay is a financial dataset. This is the correct *kind of design freedom*, not proof that the triangle improves understanding. Agency and opposing positions must not be exaggerated by arrow direction or labels; the derived pseudo-quote and mobile header also fail acceptance.

Preserve: literary opening, prose emphasis, content-conditioned restraint and the ability to decline a diagram. Do not freeze a “theology triangle” template.

Evidence: [conceptual structure](evidence/E3-004-v1-1440-zh-CN-body.png), [mobile Reader](evidence/reader-E3-004-v1-390-en.png).

### 3.5 Human-interest narrative: visualize the reported object only when it helps the reader

The Sunday story's hourglass is tied to a real person's reported one-hour work limit. Unlike an arbitrary dashboard, it can explain a personal boundary. Survey/chart material appears later, respecting the shift from scene to broader evidence. But its boxed quote repeats a nearby sentence, and three illustrations may interrupt more than they clarify. The deterministic newspaper's continuous prose is a serious competitor here.

Preserve: human scene first; deliberate narrative pauses; selective visual treatment grounded in the story. Compare the hourglass alone, light typography, and current full composition rather than declaring full treatment mandatory because the story is long or on A1.

Evidence: [hourglass/mobile](evidence/E2-010-v1-390-zh-CN-body.png), [ordinary narrative](evidence/newspaper-narrative-390-en.png).

### 3.6 Short reports: length does not determine informational complexity

The rogue-model report's actor/action/disclosure diagram and detection lag have explanatory potential despite only seven canonical paragraphs. Amazon/Decart has real comparable acquisitions and a possible, not completed, deal; a modest comparison may help without a full feature apparatus. In both cases, every proposed intervention must justify its incremental value over clean bilingual text. The rogue-model page repeats the same corporate quote in a sidebar and prose; Amazon's masthead and mobile overflow are disqualifying defects, not arguments against short-form editorial capability.

Evidence: [incident relations](evidence/E1-024-v1-1440-zh-CN-body.png), [Amazon English mobile failure](evidence/E3-001-v2-390-en-head.png).

## 4. Negative cases that belong beside the golden panel

### 4.1 Source-referenced does not yet mean source-supported

Current canonical E1-010 `m1` is `4.12% vs 3.94%`, claiming `p4`; actual p4 is `5.1% vs 4.4%`. `m2` is `4.09% vs 3.87%`, claiming p5; actual p5 gives mid-2027 `4.96% vs 4.3%` and end-2027 `4.78% vs 4.26%`. `m3` labels a 2028 comparison not supplied in that source block. The chart displays the wrong series and 18/22/24-basis-point changes; the source comparisons above imply 70/66/52 basis points for their respective horizons.

The defect is not solely a model hallucination in SVG: the deterministic canonical derivation table itself carries unsupported values. The compiler injects/trusts these entries; copying exactly from this canonical derivation preserves the error. E1-010 q1 claims p9 but its quoted sentence is absent from that paragraph and the complete article. E3-004 q1 similarly presents commentary in quotation marks, absent from the attributed p12 and complete article.

Evidence: [machine-readable excerpt comparison](evidence/derivation-findings.json); `render/canonical_builder.py:195–258`, `412–418`; `editorial_compiler.py:458–489`. All selected versions still pass a fresh strict compile.

Consequences: preserve the lossless narrative projection, but do not call all of canonical source “verified fact.” Quotes require source spans/speaker attribution; metric derivations require operands, units and horizon evidence; commentary must be labeled as interpretation, not an invented quotation. `source_model.content_digest` hashes source entry plus alignment repair, **not** curated derivations/media/code, so equal narrative digests do not prove the entire publication input is unchanged.

### 4.2 Reader and standalone delivery are different surfaces

E2-001 v1 and v3 standalone buttons retain no click handler, although their scripts define `switchLang` and `setLanguage`. EN clicks left the document in `zh-CN` at both widths. The sanitizer only preserves the specific inline `setLang(...)` form (`editorial_compiler.py:211–216`). The Reader outer control successfully switched both versions, because the host manages locale separately. Architecture: keep Reader behavior, but do not infer standalone correctness from it.

Screenshots whose filename contains `en` for these failed standalone requests still show Chinese. The JSON's `requestedLocale`, actual `locale` and `switchSucceeded` fields are authoritative. They are failure evidence, not successful English render evidence; successful English reading was exercised separately through the Reader.

E3-004 at 390px: the EN pointer action was intercepted by the header. Keyboard focus/Enter changed the locale. Its mobile screenshot shows a clipped control. This is an interaction/accessibility challenge even though keyboard operation works.

### 4.3 Zero page overflow can hide clipping

E3-001 v2 standalone `scrollWidth` was **494px in CN and 578px in EN at a 390px viewport**. In the Reader, document overflow was absent; its host uses clipping guards. That does not repair the article's underlying layout or ensure every label is visible.

Other observed evidence rails/SVG labels clip internally while `scrollWidth` is within the viewport. Require inspectable data, legible text, reachable controls and meaningful reflow—not only `scrollWidth <= viewport`. Visual-review evidence is a distinct contract from compiler metadata and Shadow DOM encapsulation.

### 4.4 Historical “golden” is evidence, not authority

[Phase 5 experiment summary](../../../experiments/phase5-exp01/artifacts/experiment-summary.json) records the Phase 4 golden at 18/20 verbatim matches in both languages, while three source-referenced runs reached 20/20. Source-referenced runs also had inventoried unverified editorial numbers. The historical baseline teaches both aesthetic possibility and why compilation improved integrity. Its name does not waive today's acceptance rules.

## 5. Golden acceptance card for future comparisons

Keep the panel immutable. Attach independent approval to each tested version or intervention; do not edit the old artifacts to make the comparison cleaner.

| Dimension | Minimum requirement | Preferred comparison question |
|---|---|---|
| Narrative fidelity | All bilingual canonical narrative units, ordered and exact; attributed repairs | Does either presentation hide, truncate or visually demote necessary reporting? |
| Derived/editorial fidelity | Quotes match evidence; values/units/horizons supported; additions distinguish fact/interpretation/uncertainty | Does the intervention make a stronger or different claim than its source? |
| Composition | Each intervention has a reader need and evidence; no duplicate highlights/quotes | What can the reader understand here that clean prose does not already supply? |
| Reading | Continuous prose is primary; typography and pacing suit the actual story | Does a reader follow the scene/argument without repeatedly leaving it? |
| Identity | Publication coherence plus article-specific expression | Does it remain journalism rather than UI chrome or infographic theater? |
| Bilingual/responsive | Actual switch, both languages, 1440/390, visible labels/control targets | Does the same explanatory relationship survive reflow rather than merely fit? |
| Delivery/reuse | Saved version reopens without a model; source/decision/renderer provenance pinned | Can another host reproduce the *validated execution*, not regenerate the same stochastic design? |

This establishes a **capability floor with explicit exceptions**, not a fixed stylesheet. New agent-native execution must retain or improve these capabilities and clear the known negative cases. Independent human approval and fresh-issue comparisons remain necessary before claiming generalized editorial excellence.
