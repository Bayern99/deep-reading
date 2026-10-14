# WSJ Deep Read — Agent-Native Architecture & Editorial Intelligence Research

**Date:** 2026-10-14. **Status:** research recommendation, not an accepted architecture migration or implementation specification. Audience: Jerry and the next engineering/research team.

## Decision in brief

WSJ Deep Read should become a **portable editorial capability operated by the host Agent Harness**, not a second AI application users must operate. Preserve the proven editorial methods, narrative integrity mechanisms, deterministic rendering, source-reference compiler and saved artifacts. Put semantic selection, processing decisions, art direction and review reasoning in the harness. Distribute the deterministic programs with the capability; do not make the current development computer an application server.

Start with **file contracts, narrow local execution and a task-oriented skill experiment**. Keep existing Publisher generation as a quality comparator and optional engine. Do not require an MCP server, a full plugin, a new queue framework, or a package migration before testing the decision system. Adopt MCP only where measured cross-harness discovery/structured-call benefits justify it; use Claude Code plugin packaging later for installation, not as the business architecture.

The most important missing capability is **explainable editorial judgment over the entire issue**, including items never recommended by current rules. The most important newly observed quality risk is **unsupported material inside canonical derived entries**, not just model-authored additions. Fixing execution organization alone cannot resolve that trust problem.

### Reading map

1. [What have we actually built?](#1-what-have-we-actually-built)
2. [What is fundamentally wrong with the current approach?](#2-what-is-fundamentally-wrong-with-the-current-approach)
3. [What editorial intelligence is missing?](#3-what-editorial-intelligence-is-missing)
4. [How should we benchmark it?](#4-how-should-we-benchmark-it)
5. [What should the agent-native architecture look like?](#5-what-should-the-agent-native-architecture-look-like)
6. [What should we test first?](#6-what-should-we-test-first)

Companion: [Editorial Golden Baseline](GOLDEN-BASELINE.md), with version-pinned comparisons, positive design findings and negative cases. Evidence files and primary sources appear in §7–8.

### Evidence labels and scope

- **Observed:** repository/code/data inspected or an execution exercised in this research.
- **Historical:** a dated repository report describes an earlier result; not rerun or generalized here.
- **Recommendation:** a proposed responsibility, decision procedure, benchmark or experiment; not implemented or proven superior.
- **Unresolved:** prerequisite or result not available. An absent test is not a failure finding.

Observed runtime: an isolated copy of the preserved `2026-10-12` issue, with production queue omitted; no paid or external model calls. Both production builds and Studio/Reader HTTP passed. Selected saved generations were recompiled in memory. Chromium inspected actual standalone articles, the saved Reader and whole newspaper. Existing source/artifact/index/queue changes were the user's and left untouched. Only research documents and evidence were written.

This is **not** a multi-issue benchmark run, fresh OCR/translation certification, security audit, blind human study, or measurement of live model prices/latencies. Recommendations below name those gaps rather than replacing evidence with architectural preference.

## 1. What Have We Actually Built?

### 1.1 The real product asset is editorial capability

The established foundation is not the Studio. It is the ability to preserve bilingual journalism while producing content-conditioned reading experiences: coherent identity, prose-centered typography, selected explanatory interventions, exact narrative injection, inspectable failures and saved versions.

[FOUNDATION](../../FOUNDATION.md) (lines 44–56) and [DESIGN](../../DESIGN.md) (lines 10–28) already say that source copy is immutable, modules must add a view, empty intervention is valid, and typography/reading rhythm precede decoration. The publishing prompt also explicitly rejects rigid templates and asks for genre/narrative analysis (`render/editorial_publisher.py:28–77`). Those principles survive an agent-native cutover.

The current Foundation describes a daily Chinese AI-native newspaper. **Recommendation:** distinguish that reader outcome from the operator/distribution model. A faithful newspaper/Reader delivered by a host agent preserves the reader principles without requiring a separate AI Studio. Do not silently rewrite Foundation in this research; a later accepted decision should reconcile its wording with the agent-native operator intent.

### 1.2 Capability and maturity ledger

| Capability | Evidence | Maturity claim justified today |
|---|---|---|
| Approved bilingual source and translation provenance | `final.json`, extract/merge/translation batches, glossary, issue analysis | Real accepted source for one issue; not independently certified against an original PDF here |
| Exact bilingual projection and repairs | `source_model.py:34–75`; immutable source plus auditable repair records | Reusable deterministic core; unmatched tails retained; repair provenance matters |
| Integrity Gate | `integrity_gate.py`; current smoke: 113 PASS / 4 WARN / 0 BLOCK | Detects known completeness risks; PASS is not translation/fact/selection approval |
| Whole-issue publication | Isolated build: 117 inputs, 92 published items, five plans, bilingual copy/order checks | Working deterministic output path; issue-local configuration and 117-count assumption block daily generalization |
| Canonical narrative anchors | `canonical_builder.py:380–497`; nine fresh strict compiles | Strong lossless narrative representation; derived entries have a separate, currently weak trust contract |
| Source-referenced generative composition | Seven representative stories/nine versions; varied investigation, analysis, humanities, narrative and short-report layouts | Demonstrated content-conditioned composition on real material, not universal superiority or selection competence |
| Compiler | `editorial_compiler.py:343–544`, audits `547–699` | Exact narrative coverage/order/copy and some structural checks; not chart truth, complete security or visual acceptance |
| Saved artifact versions | Snapshot: 21 identities/38 versions; Reader version/locale inspection | Reopen without generation; old versions preserved; active pointer is not an independent editorial approval record |
| Persistent queue | `generation_queue.py`; documented pending/running/completed/failed/cancelled behavior | Useful serial workflow execution; heuristic recovery and process-local locking, not exactly-once publication |
| Provider adapters | Callable, OpenAI-compatible and Anthropic in `model_provider.py` | Reusable optional generation adapter; no necessity to route host reasoning through it |
| Web Studio/Reader | Isolated HTTP smoke; 32 Reader width/locale/version observations | Functional local inspection/delivery tooling; operator UI and AI controls are not mandatory future workflow |
| Autonomous editorial selection | Current curation rules; historical planner reports | Some useful restraint and rules; no independent full-issue/multi-issue selection reference or consequential-omission estimate |
| Fresh PDF-to-reader operation | Missing PDF/external adapters; `pipeline.py` only runs integrity | Not reproducible end to end from the repository alone |

The snapshot has 38 articles, 11 opinions, 11 briefs, six letters, three digests, 22 photo captions, 25 data tables and one correction. These 117 **Source Items are not 117 narrative articles**. Selection, preserving source, ordinary publication and recommending generative treatment are four different sets.

Current WARNs are E1-004, E1-007, E3-002 and E3-005, with unconfirmed continuation evidence documented in governance. Do not resolve them by successful compilation or by a new orchestration method.

### 1.3 There are two production paths, not one pipeline

```text
Whole issue:
  final source + alignment projection + issue plans/front/assets
  -> Integrity Gate + deterministic renderer + receipts
  -> newspaper index.html / comparison baseline.html

Generated article:
  final source -> canonical narrative/derivations/media
  -> Publisher provider OR externally supplied source-referenced HTML
  -> deterministic compiler/audit -> Artifact Store versions
  -> saved Reader / standalone compiled HTML
```

The newspaper build does **not** consume generated article artifacts. Reader export does **not** build the whole newspaper. A future delivery decision must specify which output family it needs. Initially retain both; do not unify their rendering engines just to obtain one command. A host agent can deliver a deterministic issue and selected generated articles together with a clear reading entry point, without claiming that generated pages have been integrated into `index.html`.

The existing `import_raw_generation(...)` is important: host-composed HTML can already cross into the production compiler/store **without another generic-model provider call** (`editorial_publisher.py:232–267`). This is a real seam, not a proposed rewrite. It currently persists/promotes compiler-verified output and lacks an explicit gate check; experiment in an isolated store and apply admission first.

### 1.4 The complete upstream workflow and its limits

| Stage | What exists | When it is needed / what can be reused |
|---|---|---|
| Obtain edition | External WSJ PDF; original absent from repo | Needed for new extraction, inventory completeness and unresolved continuation/figure checks; never needed simply to reopen a saved artifact |
| Initial inventory/layout/text | Preserved `raw.txt`, `extract-E1/E2/E3.json`; historical Poppler/layout reconstruction | Use available extraction; OCR only image-only/damaged regions, not every page reflexively |
| Continuations/merge | Issue `merge.py`; `turn_page.py` optionally uses PyMuPDF and fixed A/B offsets | Repair only affected spans against PDF/web edition evidence; continuation identity cannot be assumed from title similarity alone |
| Terminology and translation | Issue glossary (historically 511 terms), `trans-T*.json`, draft/QA notes | Preserve approved translation; translate only missing/stale selected text; titles/captions/table handling may differ from complete prose |
| Specialized translation execution | Historical adapters import `/home/hatch/workspace/translate-gemma.py`; old `~/workspace/...` paths | Restore tool/version/endpoint contract for a new issue; endpoint connectivity is not the research problem |
| Assembly/QA | Issue `assemble.py` combines batches into `final.json` and overwrites `report.md` | Historical provenance, **not safe to rerun over approved final source**; future inputs need a separate candidate and explicit acceptance |
| Integrity/alignment | Gate, source projection, exact repair overrides | Required for publication admission; a stored, matching accepted result can be reused under its validated tool/config contract |
| Editorial decisions | `front.json`, static plans, curation manifests, historic planner outputs | Useful evidence; semantic selection/treatment needs a stronger reproducible decision record |
| Canonical representation | Ordered bilingual blocks/sentence anchors/derivations/media | Reuse matching narrative projection; check additional canonical inputs separately, not only narrative digest |
| Composition | Ordinary/enhanced static rendering; generative Publisher; raw-generation import | Execute the treatment selected for the item; no generative treatment is a complete, valid outcome |
| Verification/store | Compiler, receipts, audits, versioned artifacts | Required for changed output; preserve raw output, failed attempts and accepted prior versions |
| Reader/delivery | Whole issue, saved Reader, standalone versions | Reopen/export already accepted results without model use; separate delivery choice from generation |

`render/pipeline.py:23–35,71,107–112` hardcodes the issue, hashes only the first 100 Chinese characters per item, and mostly prints stage labels after running integrity. Do not build future incremental execution on its cache or describe it as a PDF-to-reader orchestrator.

Upstream is a distinct uncertainty from downstream quality. The [TranslateGemma proof](../../docs/history/translate-gemma-proof.md) establishes historical small-sample translation/terminology behavior, not today's service availability or whole-issue translation accuracy. The [AnyDoc evaluation](../../docs/history/anydoc-eval.md) explains rejection of one extraction approach; it does not prove that an unintegrated alternative will work. New extraction-engine selection is not necessary to test editorial decisions on already available text.

### 1.5 The Golden Baseline protects capabilities, not every pixel or historical claim

[GOLDEN-BASELINE.md](GOLDEN-BASELINE.md) pins seven stories/nine generated versions and the deterministic reading floor. It records source hashes, fresh compilation, desktop/mobile bilingual behavior, article-specific design strengths and defects. Principal preserved capabilities:

- Capital-flow/mechanism explanation beside intact investigation prose.
- Quantitative comparison as an analytical composition's center.
- Original source subheads and long-form reporting structure.
- Literary opening scenes and typography for humanities/narrative.
- Short-but-complex reporting eligible for a justified small diagram.
- Distinct valid designs for the same source; fewer interventions can be better.
- Save/reopen/compare versions without regeneration.

**Observed disqualifying defects must not become frozen quality requirements.** E1-010's canonical-derived values and quotations contradict their alleged source, E3-004 has a pseudo-quote and clipped mobile control, E2-001 v1/v3 standalone EN switches fail, and E3-001 v2 overflows mobile. Retain all these originals as evidence; use successful capabilities as the quality floor and defects as challenge cases. Human/editorial approval of future candidates is still needed. Compiler “verified” does not automatically make a whole artifact a human-approved golden release.

## 2. What Is Fundamentally Wrong With the Current Approach?

### 2.1 The architectural error is an operator inversion

In the current application path, the operator opens Studio, selects models/items, initiates generation, monitors a queue, then reads saved outputs. In a capable Agent Harness, the user has already supplied intent to an agent with reasoning, tool execution, files and task planning. Requiring a second app to repeat those choices is an **interaction and responsibility mismatch**, not proof that the Studio code or Publisher is worthless.

A second conversation manager, generic agent memory, model-chat runtime or universal orchestrator would amplify the mismatch. Persisting article source, decisions, outputs, execution receipts and unresolved risks is necessary **business state**. It does not require saving the model's conversation or keeping all articles in its context.

### 2.2 Distinguish architecture, implementation and editorial uncertainty

| Problem class | Concrete evidence | Recommendation |
|---|---|---|
| Architecture | UI/model selection/queue submission are the assumed operator path | Host is primary operator; optional Studio/Reader inspection, headless business calls |
| Architecture | Provider call packages analysis and HTML generation for every admitted item | Permit host planning/composition; keep Publisher as comparator/optional specialist path |
| Architecture | Two output paths are mistaken for one end-to-end pipeline | Explicit deliverable choice and shared source/verification; retain both proven renderers |
| Implementation | Global curation/images/repairs/derivations keyed by issue-local IDs; fixed 117 assertion | Issue-scope these inputs before second-date production; no compatibility shim into another issue |
| Implementation | Direct multi-file store writes, process-local queue lock, timestamp recovery, cancellation after persistence | Single writer now; bounded identity/commit/promotion design before unattended/multi-writer operation |
| Implementation | Source drift is not checked when deciding “already generated” | Keep old artifacts readable; distinguish archival readability from current-source suitability |
| Editorial trust | Hard-coded derived values/quotes not supported by their cited source | Validate derivation provenance and label interpretation; do not treat canonical-derived entries as inherently factual |
| Editorial judgment | A1/P1/paragraph count are used as treatment decisions | Retain as signals/comparator, not automatic authority |
| Security | Loopback HTTP has no origin/auth policy; short scripts allowed; Shadow DOM is not a sandbox | No shared server; bounded HTML policy and browser isolation before trusting arbitrary output |
| Evidence gap | One issue and a historical 18-item layout-selection exercise | New-date reference/omission benchmark; don't generalize a small selected sample |

### 2.3 Some current shortcuts manufacture editorial certainty

`evaluate_article_curation` (`generation_queue.py:165–217`) excludes some non-narrative types from generation, recommends full composition for A1/front stories, recommends features for plans/P1 or sufficiently long P1/P2 stories, and defaults others to a compact brief. Its A1 explanation asserts rich narrative suitability without reading the narrative. The final branch can classify a P3 long article as a “short” item. Useful triage signals are being presented as completed judgment.

Non-narrative **generation admission** is also not the same as preservation/reading value. A correction may be important, a table may be essential evidence, and a caption may connect a crucial photograph. They may need ordinary preservation or structured presentation without a generated feature page.

[SELECTION_VALIDATION_REPORT](../history/SELECTION_VALIDATION_REPORT.md) (lines 13–36) historically describes an 18-item layout exercise with 16 no-intervention outputs and two sidebars, and reports no omissions from an abstracted spot-check. This is encouraging evidence of restraint. It is not independent full-edition selection recall, is not the current source-referenced Publisher path, and does not establish multi-issue editorial judgment.

### 2.4 The deeper integrity gap crosses the deterministic/generative seam

Observed E1-010 canonical `m1` says `4.12% vs 3.94%` with source p4. p4 actually says `5.1% vs 4.4%`. Further canonical metrics and the displayed SVG repeat unsupported series. Canonical q1 for E1-010 and q1 for E3-004 are not verbatim quotations anywhere in their article. These are hard-coded `CURATED_DERIVATIONS`, not merely an unrestricted model label.

`canonical_builder.py:412–418` accepts curated derivations; `editorial_compiler.py:458–489` injects them. Nine selected raw generations still pass fresh strict compilation. `source_model.py:52–57` hashes original source plus alignment repair, not curated derivations/media. Therefore:

1. Exact canonical narrative is a proven asset.
2. A source-block identifier attached to a metric/quote is **not proof of entailment**.
3. A narrative digest match is **not a full publication-input digest**.
4. A new host model and a new plugin could faithfully carry the same factual errors forward.

Repair scope for a later phase: evidence-backed derivation records and admission/approval, not replacement of the entire canonical model or rewriting approved narrative. This research identifies and preserves the contradictions; it does not change them.

## 3. What Editorial Intelligence Is Missing?

### 3.1 Use decisions with reasons, not a mechanical weighted score

**Recommendation:** an editorial deliberation procedure with independent questions and auditable outputs. Page, priority, section, length, type and gate findings inform attention; none determines treatment alone. Separate:

- **Reading value:** does this item matter to this reader/task/issue?
- **Source readiness:** can it be faithfully processed with the evidence available?
- **Processing need:** what missing/repaired/translated material is actually needed?
- **Intervention value:** what specifically improves understanding or reading?
- **Publication quality:** did the executed treatment meet those claims?

The values are not interchangeable: important-but-incomplete calls for recovery, not exclusion; long-but-clear can call for restrained prose; short-but-relational can earn a diagram; visually impressive can still be false.

Human editorial policy establishes audience, topic interests, consequential-omission definitions, acceptable uncertainty, budget constraints and escalation. The agent applies that policy to the actual source; deterministic programs enforce contracts. Avoid pretending a single universal “newsworthiness score” expresses these tradeoffs.

### 3.2 A practical six-stage decision procedure

| Stage | Agent/editor judgment | Deterministic responsibility | Persisted result |
|---|---|---|---|
| 0. Inventory and reuse | Determine task and available accepted work; reconcile potentially missing items | Enumerate files/items, identities, digests, validations; report freshness and unresolved findings | Complete issue inventory and available-result ledger |
| 1. Selection | Reader relevance; consequence, explanatory value, originality, evidence depth, topical diversity; explicit omissions | Detect duplicates/types/known exclusions as review signals; never confuse gate with worth | Selected/preserved/withheld/excluded decisions, evidence and omission reasons |
| 2. Processing | What must be extracted/repaired/translated? What can use approved text or lighter table/caption handling? | Completeness/alignment/number/name checks; exact source projection; provenance tracking | Needed operations, accepted inputs and unresolved source risks |
| 3. Treatment and plan | Reader difficulty and benefit of a particular intervention; credible alternatives, including none | Verify anchors, available media/data, supported operations and plan freshness | Content-specific intervention plan with evidence and counterfactual |
| 4. Execute | Choose host composition, optional Publisher, or static path based on demonstrated capability | Compile/render/store candidate, audit narrative/contracts | Candidate artifact, program/model/input identity, receipts and usage |
| 5. Review and disposition | Read/fact-check additions; evaluate actual benefit; revise, decline intervention, hold or accept | Fresh compile, provenance/arithmetic, browser measurements; preserve accepted prior output | Separate copy/fact/visual/editorial decisions and next action |

Stages 1 and 2 are iterative. Fresh issues need **minimum viable extraction/inventory before selection**, or important unseen material disappears. Full costly translation/composition need not precede value judgment. When inventory text is insufficient to assess an item's consequence, gather the missing evidence; do not label it worthless because OCR/metadata is weak.

### 3.3 Selection: protect recall without processing everything equally

Read the complete inventory first, then enough actual text to justify each decision. Use section/page/type/length only to route attention. Record `preserve for ordinary reading`, `select for deeper reading`, `withhold pending source repair`, and `exclude from reading delivery` as distinct dispositions; the labels are provisional vocabulary, not a mandated UI tier system.

Two passes are useful:

1. **Positive pass:** identify significance, reader questions, investigation/analysis/human narrative and issue-wide links. A reader's explicit interests may elevate an otherwise ordinary item.
2. **Omission pass:** independently inspect everything not selected. Ask which exclusion would leave a substantive hole, whether short/back-page/opinion items were systematically missed, and whether “blocked” concealed an important story needing repair.

Adverts, navigation debris and true duplicates can usually be excluded with clear rules. Ambiguous duplicate/continuation links need source evidence. Opinion and news retain distinct authorship/epistemic status; ideological agreement is not a selection criterion. Tables/corrections/captions remain in inventory even without generative composition.

### 3.4 Treatment is a set of justified interventions, not compulsory levels

Use the least complexity that **actually solves the reader's problem**, not “fewest elements regardless of quality.” Candidate actions may include faithful bilingual text, typographic pacing, source-section navigation, a verified figure, one explanatory note, a comparative data field, an annotated timeline, a mechanism diagram or a fully bespoke composition. Combinations are valid; no fixed three-tier ladder is required.

Every intervention must answer:

- **Need:** what will the reader otherwise misunderstand, struggle to compare, or lose track of?
- **Evidence:** which source paragraphs/spans, table cells or verified asset support it?
- **Form:** why this form instead of prose or a simpler alternative?
- **Position:** why here in the actual scene/argument; what must remain continuous?
- **Truth:** what are the units, denominator, time horizon, speaker, uncertainty and limits?
- **Counterfactual:** what is lost if we omit it? What repetition/disruption does it introduce?
- **Mobile/bilingual:** how does the relationship survive reflow and locale changes?

Examples from the panel:

- Private credit: capital-flow relations may justify an exhibit; not every repeated number needs a card.
- Bond yields: same-horizon October/July forecasts justify comparison **after** data is verified. Forecasts must remain forecasts; unlike periods cannot be plotted as equivalent series.
- AI/religion: a literary scene/argument may be sufficient. A conceptual triangle is optional and must not invent antagonisms or direct quotations.
- Sunday scaries: the hourglass can explain a reported boundary; an illustrated page is not necessarily better than sustained prose.
- Seven-paragraph AI incident: actor/action/disclosure/detection lag can be complex enough to merit a small diagram. Paragraph count cannot veto it.

Segel and Heer's primary study [S9] supplies useful narrative-visualization vocabulary and examines both successful and problematic journalism examples. It does not prove any chosen WSJ intervention increases comprehension. That requires reader evidence.

### 3.5 A small durable decision record

Proposed logical fields, **not a new implementation/schema introduced here**:

```text
identity: issue_date + source_item_id + source revision
policy: audience/task + editorial policy version
selection: disposition + rationale + cited evidence + omission consequence
processing: available accepted inputs + needed actions + unresolved risks
treatment: reader need + proposed/declined interventions + source anchors
execution: input/config/tool/decision identity + candidate/version/result paths
review: copy status + derivation/claim status + visual status + editorial disposition
```

Persist concise reasons/evidence, not private chain-of-thought or a transcript. A changed task/policy can legitimately change selection while the source stays identical. A changed source/repair invalidates its anchored plan; a changed derivation/media/compiler can invalidate output suitability without changing the existing narrative digest.

WARN disposition should cite the actual evidence and responsible decision/policy. Agent resolution is allowed when policy authorizes it and source evidence is conclusive; uncertain continuation, translation meaning, false quotations and consequential factual ambiguities escalate to a human. A route's `confirm_warn=True` is not that evidence.

### 3.6 Quality judgment and stopping

Separate **candidate compiled**, **factual additions checked**, **browser checked**, and **editorially accepted**. These need not become four new services; file fields/receipts are enough. Existing `verified` versions currently reflect compiler acceptance and promotion; don't retroactively reinterpret that status.

Use hard gates for missing/altered narrative, unsupported quotes/figures, stale inputs and broken required interactions. Then assess qualitative benefit: coherent reading, appropriate identity, legible hierarchy, supported explanatory relation and no duplicative interventions. A page can pass the gate and still be worse than the faithful floor.

Repair a localized demonstrated failure with a bounded attempt and an explicit acceptance condition. If the intervention lacks benefit, remove/decline it rather than repeatedly prompt for prettier versions. Stop when it satisfies the planned reader need and checks, when further generation lacks a concrete hypothesis, or when source uncertainty prevents safe publication. Keep the previous accepted artifact readable. No source-fidelity failure is traded for lower cost or better aesthetics.

AP's policy treats generated output as unvetted source material [S10]. That supports review accountability; AP's stricter prohibition on using it for publishable copy is **not imported as a ban on this project's supported generative layout/editorial interpretation**. Preserve approved narrative, and review/labeled-source-support additions deliberately.

## 4. How Should We Benchmark It?

### 4.1 Benchmark purpose and three complementary collections

**Recommendation:** estimate decisions and outputs separately, then test the real trajectory. Do not design a benchmark merely to make the agent-native candidate win.

1. **Capability regression panel:** the pinned Golden Baseline plus observed negative cases. Repeated use is allowed for development/regression; it is not an unbiased test of unseen editorial judgment.
2. **Representative fresh-issue collection:** complete WSJ editions sampled from a declared accessible date window; independently inventoried. Reserved issues never used for prompt/rule development supply the decision-grade comparison.
3. **Challenge collection:** cross-page continuations, column/sentence splits, missing figures, inconsistent locales, data tables, short complex stories, no-treatment cases, corrections, possible duplicates and unconfirmed sources. Report separately; do not average an oversampled stress corpus into claimed daily performance.

Current repo supplies only one issue and no source PDF. Therefore a real multi-issue benchmark needs **lawfully acquired editions and full source inventories**, plus reference-editor participation. They are prerequisites for execution, not reasons to delay the available single-issue decision/host-composition experiments. Do not count artifact versions of one date as independent issues.

### 4.2 Choose dates and sample size from information needs

Define the sampling frame before reading candidate recommendations: available full WSJ editions over a specified window, edition identity, missing dates/sections and acquisition method. Use issue-level strata for high/ordinary/low news intensity and differing page/section composition; classify intensity from an independently recorded editorial assessment, not the candidate's output. Balance financial/technology/international/opinion and human-interest coverage across dates. Record calendar/edition effects where relevant; don't assume every edition has the same A/B page offsets.

Randomly choose dates within the declared strata using a recorded seed. Within **every selected date**, inventory all source items, including advertisements/non-narrative debris and any missed by extraction. The selection benchmark requires a complete denominator, so do not judge only top recommendations. Deep treatment/output review can use a stratified item sample from that universe, recording inclusion probabilities.

Use a calibration pilot to estimate prevalence of consequential stories, disagreement, plausible treatment effects and within-issue correlation. Pick the next sample expansion from:

- Uncovered important strata/difficulties.
- Uncertainty in consequential omissions and treatment error rates.
- Precision or power needed for the specific engineering decision.
- Feasible independent editorial review, with its budget reported—not hidden as statistical adequacy.

For orientation, an independent binary proportion near 0.5 requires roughly `1.96² × 0.25 / h²` observations for 95% half-width `h`: about 96 for ±10 percentage points, 384 for ±5. These are **planning examples, not an assigned article/issue target**. Issue clustering, repeated versions and rater dependence reduce effective sample size. Zero observed critical omissions is not zero risk: under an independent-binomial approximation, the upper 95% bound is about `3/n`; clustering weakens that simplification.

Use issue-level paired outcomes and resampling/cluster-aware intervals once enough dates exist; with very few issues, report descriptive results and uncertainty, not fragile daily-ready claims. Pre-register a fixed validation batch or planned sequential looks with appropriate error control; don't stop after an attractive win-rate. Define each practically consequential regression tolerance before comparison; derive the number of dates from pilot variance and that decision. Lakens [S13] supports explicit sample-size justification; it does not prescribe an arbitrary sample count.

### 4.3 Independent human reference: preference variation is data

Reference editors work from the full edition/source library **before seeing candidate decisions**. Initial reference process:

- Two independent bilingual editorial judgments establish audience-specific selection, must-not-miss items, source uncertainty, acceptable treatment alternatives and prohibited claims/interventions.
- A separate human adjudication step resolves consequential disagreements. Preserve individual judgments and reasons; acceptable treatment may be a set, not one exact design.
- Calibrate instructions on development material. Report raw agreement and an appropriate chance-adjusted statistic with category prevalence; do not force arbitrary kappa cutoffs or relabel genuine disagreement to manufacture agreement.
- Jerry sets editorial policy and approves material decisions; a trained second rater supplies independent judgment. If unavailable, the run remains exploratory with that limitation, not “human validated” by a single generating agent.

Producers do not write the reference, evaluate their own results and declare success. An independent agent may identify possible omissions/unsupported claims or act as a screening reviewer, preferably a different model family, but **human reference and consumer-visible checks retain final authority**. Position/self-preference bias is evidenced in original studies [S11–S12]; changing model family or hiding model labels reduces some risks but does not prove judge neutrality.

Reference record per item: selection disposition, consequence if omitted, source-readiness decision, minimum acceptable processing, acceptable intervention set, key evidence and uncertainty. Avoid treating “unjudged” as “irrelevant.” Do not construct the reference solely by pooling the candidates' selections; material no candidate finds would vanish from evaluation.

### 4.4 Four evaluation layers

| Layer | Measure/process | Critical safeguard |
|---|---|---|
| **A. Selection** | Full-inventory selected-set precision/recall; raw must-not-miss misses; recoverable-vs-unrecoverable omissions; section/type/length/readiness breakdowns; explicit exclusion audit | Excluded/blocked/unextracted items remain in denominator. Audit every reference-important omission, not only recommended articles |
| **B. Treatment decision** | Processing necessity; appropriate restraint/intervention; under-treatment and over-treatment; acceptable-set agreement; unsupported intervention proposals; reference-approved rationale quality | Not fixed tier accuracy. Text-only/no generation is eligible success; short/long length is a subgroup, not treatment authority |
| **C. Final quality** | Narrative exactness/order/coverage, translation meaning checks, claim/quote/number/media support; blind paired visual/reading evaluation; actual desktop/mobile CN/EN interactions | No averaging away integrity/factual failures; source and output family matched between comparisons |
| **D. Workflow** | Actual host/provider/specialist calls, token/usage/cost availability, elapsed/active/operator time, tool work, repair attempts, retries, duplication, resumption, source mutation, stale publication | Include harness reasoning and review costs—not only external Publisher requests; quality before cost comparison |

For selection, report per-issue recall/precision and macro summaries rather than only pooled totals that hide a weak date. Count consequential omissions separately from ordinary optional items; do not bury them in an overall F1. Report exclusions and non-narrative retention independently. The human task profile defines “important,” not A1 alone.

For treatment, ask a reviewer to identify concrete over/under-treatment and the simpler viable alternative. A correct rationale is not enough if the resulting plan invents facts; a different design can be acceptable if it meets the same reader need. Keep declined-intervention rationales and disagreement cases.

### 4.5 Match counterfactuals and measure reading, not screenshot prettiness alone

Run two distinct comparisons:

- **Decision isolation:** freeze source and human-approved treatment intent; compare existing Publisher vs host composition and vs faithful static output where appropriate. This tests execution/composition without selection confounding.
- **End-to-end policy:** candidates choose items/processing/treatment from the same inventory; assess selections, plans, outputs and trajectory together. Items only one candidate selects must still receive reference judgment; do not disappear in an intersection-only visual comparison.

For artifact comparisons, same source projection/repairs/verified assets, language, width, output family and font availability. Preserve article identity; hide engine/provider/version/promotional status and randomize presentation order. Keep enough navigation to read the whole article; compare prose, graphics and ending, not only hero screenshots. Use sequential paired reading as well as side-by-side diagrams; counterbalance which rendering a participant reads first. Repeat source/source or order-swapped controls sparingly to detect unreliable review, not inflate sample counts.

Questions for human paired review:

1. Which version makes the reporting easier to follow without losing nuance? A / B / tie / both unacceptable.
2. Does any intervention introduce unsupported meaning or conceal uncertainty?
3. Which relation does the diagram/note reveal, and does it duplicate the body?
4. Does the mobile/bilingual rendition preserve that benefit?
5. Could a simpler treatment achieve it?

For a small reader-comprehension study, write source-grounded questions in advance: explain the private-credit pathway; distinguish forecast horizons; state that Decart is in acquisition talks, not already acquired. Compare accuracy and misinterpretations, navigation difficulty and reading comfort. Completion time is secondary—faster reading caused by omitted copy is not a win. Blind expert aesthetic preference alone does not prove comprehension.

Automatic checks run on **all produced artifacts**; factual/translation screening never grants approval on its own. Inspect SVG labels, values and mapping to geometry; decimals-only set matching cannot detect wrong denominators, dates, speakers or risk comparisons. Include target visibility/hit testing, intra-component clipping, font fallback and meaningful responsive reflow—not only page overflow. Test Reader and standalone separately.

### 4.6 Reproducibility, costs and promotion

Proposed benchmark records:

```text
benchmark manifest: edition/date sampling frame, strata, seed, split, rights/storage policy
source inventory: complete universe, extraction omissions, source/provenance checksums
reference: per-rater decisions, adjudication, acceptable alternatives, uncertainty
run: host/version/model, policy/prompt/tool versions, decision records, calls/events
artifacts: exact candidate versions, canonical/derivation/media identity, validation
reviews: randomized order, rater/session, findings, pairwise results, comprehension
summary: per-layer/per-stratum outcomes, CIs/limits, actual resource use, decision
```

Do not copy private newspaper inputs into distributed plugin packages or public benchmark datasets. Keep lawful originals and source/translation/artifact provenance privately under the existing data policy. Distribution/licensing is separate from technical portability.

Record host reasoning, selection, generation, review and recovery calls separately. A host-composed artifact has zero **external generic-generation** calls but not zero model cost. Subscription accounting and hidden tokens may be unavailable: report observable call/tool/time measures, unknown charges as unknown, and any estimated token prices with dated rate assumptions. Historical `completion_chars` is not billable tokens; incomplete artifact usage cannot establish previous production cost. Count unsuccessful attempts and human review time. Useful editorial judgment is not automatically “toil” to be eliminated.

Promotion is a **conjunction of requirements**, not a weighted score: no observed disqualifying fidelity/truth/interaction failures; acceptable selection/treatment on the declared reference; final quality non-inferior within editor-approved practical tolerances; reliability demonstrated for promised restart/reuse; cost/time reported and acceptable. If intervals are too broad, say inconclusive. A failed candidate remains evidence. Golden examples remain development regression material; fresh held-out dates support generalization. Do not claim dataset contamination is known merely because an article is public or fresh.

## 5. What Should the Agent-Native Architecture Look Like?

### 5.1 Recommended responsibility map

```text
USER INTENT
   |
HOST AGENT HARNESS                 owns conversation/context/reasoning/tools
   |  task-oriented editorial guidance + on-demand references
   |  reads persisted source, decisions, results and failures
   |
LOCAL EXECUTION INTERFACE          small task-level calls; files + concise receipts
   |
PRESERVED PYTHON CORE              projection / gates / canonical / render / compile
   |                              candidate persistence / artifact read/export
   +---- SPECIALIST ENDPOINTS      OCR / translation / optional editorial provider
   |
LOCAL ISSUE WORKSPACE              source + provenance + decisions + versions
   |
READING DELIVERY                   newspaper / saved Reader / standalone artifacts
```

No WSJ-owned conversation runtime, persistent model-context manager, autonomous-agent framework or generic multi-agent coordinator. Harness subagents may be used under the host/user's policy; WSJ supplies editorial standards and verifiable tasks, not another orchestration layer.

### 5.2 Preserve deep modules and expose tasks, not every Python symbol

The [current architecture](../../ARCHITECTURE.md) already locates reusable capabilities. Keep shared implementations; small command entry points/adapters may expose needed operations in a later experiment.

| Existing module/group | Future position | Change justified before broader use |
|---|---|---|
| SourceModel/alignment/gate | Shared deterministic source-preparation module | Issue identity, evidence-backed repairs, explicit disposition; keep accepted source immutable |
| Canonical builder | Shared narrative/anchor interface and provenance-bearing derivations | Audit curated content, source/derivation/media identity; don't replace proven ordered blocks |
| Static build/render/plan execution | Faithful reading floor and optional whole-issue publication | Issue-local inputs and generalized item count; retain `enhanced-v1` contract |
| Compiler/audit | Shared publishing core for **either** host or external composition | Derivation/claim support, required interaction checks and explicit safety contract; keep lossless injection |
| Artifact Store | Durable primary evidence and result reuse | Frozen per-version input references, explicit candidate/approval distinction; transactional promotion if promised |
| Publisher | Existing optional composition engine, prompts/repair baseline and raw import seam | Common admission/review contract; don't force every task through a provider call |
| Model Provider | Optional adapter for Publisher/specialized composition comparisons | Explicit portable config; registry fallback not required on every host; OCR/translation may have different adapters |
| Queue | Optional durable **domain-job execution**, not agent planning | Keep proven serial path for comparator; use only if unattended/background/recovery requirement warrants it |
| Studio | Optional workbench for debugging, manual editorial review and side-by-side inspection | Headless tasks must not depend on server startup or imply WARN acceptance |
| Reader/export | Retain reader-facing delivery and saved-version access | Can open independently of Studio controls; separate Reader-host and standalone acceptance |
| Legacy planner/pipeline/drivers | Preserved historical evidence | Not silently promoted to production or deleted; no new daily runtime built on incomplete cache |

Queue retains independent value when a task must continue without an active agent session, track a remote specialist operation, or serialize costly work. But “the host can plan” does not prove it can durably execute after disconnect, and “queue exists” does not mean every interactive task needs it. In an initial host-driven single-article experiment, synchronous execution plus saved result receipts is sufficient. If background production is requested, retain a thin domain worker, not chat/context machinery.

The existing store promotes after compiler success; the new conceptual review lifecycle must first be tested using isolated copies and sidecar review records. A permanent candidate/promotion change later needs compatibility and accepted-artifact preservation. Do not expose a concurrent-writing MCP server/CLI until the single-writer contract is enforced.

### 5.3 Skills: divide procedural knowledge by real tasks

Official Agent Skills specifies a `SKILL.md` directory with optional scripts/references/assets and progressive disclosure; `allowed-tools` is experimental [S1]. Anthropic's engineering example demonstrates executing deterministic scripts without loading implementation/source documents into the model context [S2]. These support **knowledge + procedures over shared code**, not one skill per module.

Start the experiment with a single complete **process-issue workflow skill**, with on-demand editorial-decision, source-readiness and composition/verification references. Its core instructions: inspect available results; reconcile inventory; decide selection/processing/treatment; invoke deterministic programs; check outcomes; deliver saved reading output. This prevents a fragmented set of low-level skills from becoming a manual tool menu.

Split only where observed reuse or context isolation earns it:

- Source preparation/bilingual QA: different prerequisites, long provenance/translation guidance and specialist endpoint use.
- Editorial decisions: cross-item selection/processing/treatment/omission review, callable without generation.
- Single-story composition/review: specific canonical input plus intervention intent, callable without full-issue ingestion.

These are **responsibility candidates**, not a mandated count. Composition and its verification guidance should remain closely connected; deterministic compile is an operation, not a professional skill by itself. An issue workflow references shared task contracts; it does not reproduce them in every file.

### 5.4 Local scripts first; MCP only with demonstrated leverage

Initial task surface candidates, logical operations rather than a prescribed command/tool count:

- Inspect issue/source/result availability and freshness.
- Prepare/audit canonical input and source readiness for an item.
- Compile externally supplied source-referenced HTML, returning candidate/audit paths.
- Record review/admission and produce the requested reading delivery.
- Optionally invoke the retained Publisher or durable job path explicitly.

Commands should accept explicit workspace/issue/item identity and file inputs, print concise structured outcomes plus durable result paths, use meaningful exit status, never silently overwrite approved source, never resume production work on a read, and make expensive calls explicit. Reuse the existing functions and smoke-copy convention; don't mirror the entire module tree into a second implementation.

| Operation | Prefer script/file initially | When MCP could earn its cost |
|---|---|---|
| Build, compile, deterministic validation | Batch, inspectable local command; existing Python | Host cannot safely express calls or consistently parse outcomes; one structured task call improves measured reliability |
| Source/canonical/decision/result reading | Local JSON/Markdown/HTML paths already usable by host | Repeated URI discovery/filtering, access control or resource mounting genuinely reduces cross-host friction |
| Local job status/cancel/retry | Optional domain job command, no daemon if unnecessary | Live interactive job tools require structured lifecycle across hosts |
| OCR/translation endpoint invocation | Specialized adapter with validated input/output | Existing specialist MCP integration supplies useful capability/auth/discovery; not because it is remote |
| Editorial reasoning/composition | Host model + instructions -> file | Do **not** implement another reasoning/chat endpoint just to use MCP |

MCP Resources represent application-driven context and URI-based data [S6]; they do not guarantee automatic model access on every host. If useful, expose issue inventory/canonical/audits as bounded resources and effects as Tools. Do not embed a whole newspaper in every tool response. Tool annotations/metadata cannot substitute for actual admission/security enforcement.

Local stdio MCP launches as a subprocess on the host computer [S7]; **MCP does not imply a central server**. Its benefit can be stable schemas/discovery/permissions, not only remote state. Costs include another process, protocol/version/transport dependencies, configuration, tool visibility and implementation surface. Host tool-search strategies vary, so do not assume every MCP schema is permanently in context or that scripts always have lower token cost; measure the actual host.

As observed from the current official documentation, MCP's current revision is **2026-07-28**, using per-request version metadata, with compatibility guidance for earlier initialization-handshake clients [S5]. Protocol publication is not proof of deployed Claude/Muse/Grok SDK/client support. If MCP is selected, pin an SDK and validate the actual host/client version; do not hand-roll a universal dual-era protocol layer prematurely.

### 5.5 Local distribution and cross-harness portability

**Recommendation:** distribute one versioned capability bundle containing reusable guidance, the existing Python implementation, required styles/schemas/static assets and a small execution entry point. Install its runtime on each host computer in an isolated environment. Mutable newspaper/source/decision/artifact data lives in an explicit external workspace, **not the plugin cache**; updates/uninstallation must not erase primary evidence.

Separate configuration: host-local workspace path, Python environment, endpoint URLs, credential environment-variable names, model/translation choices and optional provider configuration. Preserve secrets outside prompts/artifacts/package; no `/Users/dmus`, `/home/hatch` or harness registry dependency in the portable contract. The current Python core's `lxml` dependency is small; validate additional Poppler/PyMuPDF/upstream prerequisites only when the task needs them. Distribution must include required program/assets, not instructions to connect all users back to this checkout.

Claude Code plugins package skills/agents/hooks/MCP as one installable unit, with a manifest and optional marketplace [S3]. A standalone skill or local plugin directory works without a marketplace. Later a thin Claude manifest can make installation coherent; the business protocols remain ordinary files and Python tasks. No mandatory hooks/always-running worker merely to supply editorial capability.

Verified official portability evidence: open Agent Skills format [S1]; Claude Code plugin/skill model [S3]; OpenAI's current official skill guide explicitly supports Codex CLI local skills and plugins [S4]. The integration research initially missed Codex's official page; direct source verification corrected that finding. Real public practice: Anthropic's PDF skill combines procedure, on-demand references and program execution [S8]—evidence for the pattern, not a license to vendor its proprietary skill into this project.

The official `xai-org/grok-build` README [S14] documents MCP, skills and plugins for **Grok Build**. That is **not proof of Grok Bot's installation contract**. No primary-source Muse/Grok Bot compatibility contract was established here. Preserve filesystem/script usability and test the actual user-named hosts next; don't claim plug-and-play support or build a broad compatibility framework from secondary marketplace claims. Claude API/cloud skill containers are also not equivalent to a locally tool-capable computer: target the stated local host environment first.

### 5.6 Incremental execution is dependency validity, not context memory

Reuse must account for **the dependencies of the result**, not just whether a file exists:

| Changed input | Necessary downstream reconsideration | Unnecessary work |
|---|---|---|
| Reader language/opening request only | Load saved version/control state | OCR, translation, composition |
| Editorial audience/task policy | Selection/treatment rationale, then only affected outputs | Re-extract immutable source |
| One story's treatment | Plan/composition/verification for that story | Reprocess entire issue PDF |
| Source/translation/alignment repair | Reproject affected canonical blocks, revalidate anchored plan/output | Rewrite other unchanged stories |
| Derived data/media provenance | Revalidate dependent diagrams/quotes/output | Retranslate intact narrative |
| Compiler/renderer/security policy | Recompile/review affected saved raw output under new contract | Reinvoke model when existing composition is still usable |
| New edition | New full inventory and issue-scoped inputs | Inherit prior-date local-ID manifests |

A durable receipt can record operation identity, exact input/config/program versions, start/result/failure and output references. A resumed host reads it and current files, verifies suitability and continues. The host maintains its own conversation context. Exact task/version association and atomic promotion become necessary only for the promised recovery semantics; content-valid reuse is required even for a simple synchronous workflow.

For new production, old accepted versions remain archival and readable. “Source drift” should mean unsuitable as **current** output, not deletion of valuable history. Freeze canonical/derivation/media inputs per version or reference a preserved immutable revision; today's overwritten `canonical.json` is insufficient as a historical input archive.

### 5.7 Security and publication boundaries

Treat news/PDF/OCR/model HTML as untrusted **data**, never instructions granting tools or altering policy. Paragraph text may itself contain imperative language; no marker or sanitizer makes it trustworthy. Keep allowed effects explicit, use host permissions, scope writes to issue candidates/results, and never expose credentials to generated/browser content.

The current sanitizer preserves short scripts and a specific inline toggle, and the Reader relies on Shadow DOM. This is partial markup handling, not a security sandbox. Before expanding unattended/shared usage, test an explicit HTML/CSS/script/network policy against the preserved interactions and assets. If sandboxing changes layout/controls, measure that quality regression rather than dropping functionality silently. Use isolated browser contexts for generated artifacts; do not treat arbitrary pages as privileged tools. Current localhost HTTP remains optional and must not be exposed as a shared remote WSJ server.

## 6. What Should We Test First?

Four bounded experiments; no full plugin build as prerequisite. They target the largest uncertainties with existing source/programs and explicit evidence. All generated output goes to isolated experiment workspaces, never active protected artifacts. External model comparisons require deliberate paid-call budgeting in that later phase.

### Experiment 0 — Establish the factual publication-input contract

**Question:** can every quoted/derived value and plotted claim in the selected panel be traced to accepted evidence, and can fresh compilation remain successful while unsupported additions are rejected by a separate review?

**Inputs:** current seven-story panel, raw/compiled HTML, canonical inputs, existing compiler inventory; include E1-010 and E3-004 contradictions. **Procedure:** audit quotes against spans/speakers; values against operands/units/time horizons; SVG labels/geometry against data; separate source quotations from editor interpretation. Build an independently reviewed reference list, not a new LLM-only factuality score. Keep old artifacts intact.

**Deliverable:** small derivation/claim acceptance contract, corrected *experimental* input records and rejection examples; recommendation for source-vs-publication dependency identity. **Success:** unsupported canonical entries and chart series are identified regardless of compiler PASS; approved narrative remains exact; real explanatory capabilities remain available. **Failure response:** do not proceed to a superiority claim using the contaminated derived baseline. This is bounded trust work, not a canonical rewrite.

### Experiment 1 — Editorial decisions before generation

**Question:** does semantic issue-wide deliberation improve selection/treatment versus today's curation heuristics, including omissions and legitimate no-generation outcomes?

**Inputs:** all 117 items for calibration plus fresh complete issue inventories once lawfully available; independent reference. **Arms:** current `evaluate_article_curation` suggestions; host agent using §3's evidence/counterfactual procedure. Same audience and source access; no HTML generation required. Hide artifact popularity/current active status from decision-makers.

**Deliverable:** item-level decisions, omission audit, acceptable-treatment judgments, cost/trajectory ledger and disagreement cases. **Success:** no new consequential omission, fewer concrete over/under-treatment errors, evidence-supported rationales; report uncertainty rather than assert generalization from this date. **Learning:** which guidance/semantic evidence actually changes decisions, not whether a larger prompt produces longer explanations.

### Experiment 2 — Host composition versus retained Publisher

**Question:** can host-generated source-referenced HTML maintain editorial capability without a second generic-model call?

**Inputs:** independently approved treatment intent and corrected experimental derivations for contrasting real stories: private-credit mechanism, bond comparison, literary/human narrative, short complex report, plus a no-generation control. Use a balanced coverage matrix rather than automatically assigning full treatment to all panel items.

**Arms:** faithful static output; existing Publisher generation; host directly emits anchored HTML and crosses the existing `compile_editorial_artifact` / raw-import seam. First reuse saved Publisher output as a non-live comparator; if a causal current-model/cost comparison is needed, generate both arms under logged configurations. Existing artifacts alone cannot establish current generation cost. Same source/evidence and quality policy; model differences disclosed as a confounder unless held constant where possible.

**Deliverable:** isolated versions, exactness/derivation/browser results, blind paired reading and call/cost/time records. **Success:** host arm clears hard gates and preserves/improves reading/composition within declared tolerances; actual external generic-generation calls eliminated **without claiming zero host-model work**. **Failure response:** keep Publisher as execution engine for the affected class; use host judgment/planning anyway. A host failing composition does not invalidate agent-native operation.

### Experiment 3 — Incremental local execution and portability

**Question:** can a new host computer/session determine the next required action from files, execute only that work, and reopen/deliver results without Studio startup or unnecessary generation?

**Scenarios:** reopen accepted version; change only one treatment; restart after raw HTML exists but before compile; failed compile with prior accepted artifact; source drift; two dates reusing the same local story ID; cancel while external generation is in flight. Use existing copy isolation, one writer, no production queue. Real second-date material is required for new-date editorial claims; a synthetic identity-collision scenario is useful deterministic contract testing, not a second-real-issue benchmark.

**Arms:** one task-oriented local skill + scripts/file receipts in Claude Code, then the same business contract in another available host. Test Muse/Grok Bot only with their actual documented/runtime setup, not Grok Build substituted for Grok Bot. Add a small MCP adapter comparison only if script discovery/parse/permission failures are observed; measure operation reliability, installation friction and actual context/process overhead.

**Deliverable:** observed trajectories, install/prerequisite inventory, reuse/resume/failure evidence, minimum stable task interface and a packaging choice. **Success:** unchanged source/accepted outputs preserved; already completed steps not recharged; another host operates on local copies plus configured specialist endpoints; no mandatory central server or WSJ agent runtime. **Failure response:** repair the specific file/identity/receipt seam. Don't build generic memory/orchestration to compensate.

### Dependency and implementation roadmap

```text
Current pinned evidence
  -> Experiment 0: trustworthy derivation/review inputs
  -> Experiment 1: independent decision calibration
       + fresh-edition acquisition/reference benchmark expansion
  -> Experiment 2: composition comparison under approved intent
  -> Experiment 3: minimum local task/receipt interface and second-date isolation
  -> only then: approved implementation slices and distribution packaging
```

Decision research on already accepted prose can begin while the derived-data audit runs; composition comparisons using disputed numbers must wait for reviewed experiment inputs. Broad second-date publication must wait for issue-scoped manifests/derivations and upstream acceptance. Durable background/concurrent production must wait for promised store/job guarantees. Those are real dependencies, not reasons for a global rewrite.

Small implementation slices justified by evidence would be: common admission/receipt entry points; issue-local config isolation; derivation provenance; candidate/review/promotion and frozen input references; narrowly required safety/interaction fixes. Retain interfaces and tests for proven behavior. Package migration, renderer unification, deletion of Studio/queue/provider, and full plugin/MCP framework are not prerequisites. Major refactors and deletion still require Jerry's approval.

## 7. Evidence package and verification limits

### Local evidence

- [Golden panel and findings](GOLDEN-BASELINE.md).
- [Pinned artifact manifest](evidence/artifact-manifest.json): nine version hashes, narrative source identity and fresh strict-compile results; total snapshot inventory 117/21/38.
- [Canonical derivation contradictions](evidence/derivation-findings.json): exact quoted strings/value records versus claimed source blocks.
- [Standalone observations](evidence/browser-observations.json): 36 states; requested locale differs from actual for four failed switches.
- [Saved Reader observations](evidence/reader-observations.json): 32 states; outer locale controls worked for all sampled versions/widths.
- [Newspaper observations](evidence/newspaper-observations.json): four states; 92 items, 18 loaded images each, no document overflow.
- [Governance](../../docs/governance-2026-10-14.md), [actual architecture](../../ARCHITECTURE.md), [build/recovery contracts](../../render/BUILD.md), [data policy](../../docs/data-policy.md), [domain terms](../../GLOSSARY.md).

Representative visual evidence is linked inline in the Golden Baseline; further head/body captures sit in `evidence/`. They are current research captures, not silently substituted historical screenshots.

Executed command: `.venv/bin/python scripts/smoke.py --keep`. It used the two actual build entry points, isolated HTTP routes and saved artifacts, not mocked generation. The copied queue was omitted. The selected current compiler was then exercised in memory against saved raw HTML and rebuilt canonical inputs. No production test suite, live model, fresh PDF extraction/translation, multi-date publication, standalone offline-font operation or other browser engine was exercised. Tests alone would not answer the editorial questions, so no new permanent tests were added.

Reproduce the local evidence by obtaining a stopped-writer protected snapshot if backup consistency is required, running that same isolated smoke, serving only the copied files over loopback, opening pinned versions and exported Reader at 1440/390 in both languages, and recording actual locale, visible labels/control access and source/claim comparisons. Future snapshots may contain more versions; compare manifest hashes, not current mutable pointers. A failed standalone EN switch must remain a failure observation, not a forced-JS “pass.”

### Missing prerequisites and decisions

1. Original PDF/full edition inventory and additional dates: absent in repo; needed for upstream certification/full-issue omissions.
2. Current extraction/translation executable versions and endpoint contracts: historical external paths are not portable installation evidence.
3. Independent bilingual editorial raters and audience/critical-omission policy: required for decision-grade benchmark, not supplied by an LLM self-assessment.
4. Actual Muse/Grok Bot installation/tool contracts: not established by primary sources here.
5. Live current-model quality/usage/rate data: not measured; saved artifacts cannot supply all current cost comparisons.
6. Practical quality-regression/uncertainty tolerances and paid-call limits: editorial/experiment governance, not numbers to invent as architectural facts.

All reachable repository/runtime/source research was completed without those prerequisites. The report supplies an executable protocol and experiment route; it does not claim the unavailable benchmark has already succeeded.

## 8. Primary external sources and what they establish

Accessed 2026-10-14. Published papers are evidence within their studied conditions, not proofs of product-specific quality. Vendor pages are rolling documentation; recheck actual host/SDK versions before implementation.

| ID | Primary source | Established fact / use | Limit |
|---|---|---|---|
| S1 | [Agent Skills specification](https://agentskills.io/specification) | `SKILL.md`, optional scripts/references/assets, progressive disclosure; experimental permissions metadata | Format portability is not execution/permission parity |
| S2 | [Anthropic: Equipping agents with Agent Skills](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills) | Filesystem/code-execution workflow; deterministic scripts; evaluate before expanding skills; open-standard update | Not evidence of WSJ judgment quality |
| S3 | [Claude Code plugins](https://code.claude.com/docs/en/plugins) | Plugin bundles, standalone alternatives, local directory development, footprint and permissions | Claude integration layer, not universal host runtime |
| S4 | [Official ChatGPT/Codex skill guide](https://learn.chatgpt.com/docs/build-skills) | Codex CLI local skill support, discovery, optional scripts and plugin distribution | Does not establish Muse/Grok Bot compatibility |
| S5 | [MCP versioning](https://modelcontextprotocol.io/docs/learn/versioning) | Current 2026-07-28; per-request versioning, legacy compatibility | Current spec is not deployed-client coverage |
| S6 | [MCP Resources](https://modelcontextprotocol.io/specification/2026-07-28/server/resources) | Application-driven context/resources and URI templates | Host decides resource access/UX |
| S7 | [MCP stdio](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/stdio) | Host launches local subprocess; framing/shutdown/version compatibility | MCP adoption adds lifecycle/protocol responsibilities |
| S8 | [Anthropic PDF skill source](https://github.com/anthropics/skills/blob/main/skills/pdf/SKILL.md) | Real procedure/reference/Python/CLI hybrid skill practice | Proprietary licensing; pattern evidence, not a dependency recommendation |
| S9 | [Segel & Heer, Narrative Visualization (2010)](http://vis.stanford.edu/files/2010-Narrative-InfoVis.pdf), [DOI](https://doi.org/10.1109/TVCG.2010.179) | Case-based design space, narrative flow/discovery, helpful and problematic journalistic visualizations | Taxonomy/cases, not WSJ comprehension validation |
| S10 | [AP standards around generative AI](https://www.ap.org/the-definitive-source/behind-the-news/standards-around-generative-ai/) | Editorial accountability; generated output unvetted, source verification essential | AP's own publishing prohibition is stricter than this project's intended composition policy |
| S11 | [Zheng et al., MT-Bench/Chatbot Arena (2023)](https://arxiv.org/abs/2306.05685) | LLM judge position/verbosity/self-enhancement limitations and human preference comparisons | Results do not certify editorial/visual judges |
| S12 | [Panickssery et al., Self-recognition/preference (2024)](https://arxiv.org/abs/2404.13076) | Models can recognize/favor own outputs; supports independent evaluation | Different-family reviewers still need calibration |
| S13 | [Lakens, Sample Size Justification (2022)](https://doi.org/10.1525/collabra.33267) | Explicit inferential goals, precision/power and smallest-effect justification | Tolerances/cluster variance remain benchmark-specific |
| S14 | [Official Grok Build repository](https://github.com/xai-org/grok-build) | Tool-capable terminal agent; documented skills/plugins/MCP scope | Grok Build is not Grok Bot |
| S15 | [van der Lee et al., Human NLG evaluation (2019)](https://aclanthology.org/W19-8643/) | Human-evaluation design/reporting best-practice literature | Doesn't supply editorial policy or reference labels |

**Final recommendation:** develop the decision/review contract first; compare real host execution against the preserved Publisher and faithful reading floor; then choose the smallest proven local distribution interface. Retain excellent editorial capabilities and strengthen their factual trust boundary. Do not preserve redundant AI application interaction merely because it produced the evidence—and do not discard the evidence to obtain a cleaner architecture.
