# WSJ 深读 · Project Reconstruction Brief

Date: 2026-10-13  
Author: incoming Principal Engineer / Editorial Systems Architect  
Scope: repository archaeology of `wsj-deep-read` only. No system rebuild in this phase.  
Branch: `reboot/reconstruction-brief`

---

## Executive judgment

We already have a **readable bilingual issue shell** and a **validated visual language**.  
We do **not** yet have a daily product with reliable editorial intelligence.

The project split into two products that never fully reunited:

1. **Issue production** — `render/build.py` → `2026-10-12/dist/index.html`  
   Clean AJ×WIRED newspaper. Mostly plain text. Almost no editorial modules in production.
2. **Enhancement lab** — planner / layout-test / blind5 / cases/R3*  
   Real editorial experiments, mostly on a few repeatedly polished articles.

The failure is not “no code.” The failure is that **editorial judgment never became the default production path**, while reports increasingly measured pipeline health instead of reading quality.

Target product remains unchanged: a Chinese digital newspaper people want to open every day — faithful content, selective editorial intervention, professional design, mobile-first reading, daily reliability.

---

## A. What We Have

### Repositories and workspace

| Location | Role |
|---|---|
| `/Users/dmus/Documents/deep-reading/wsj-deep-read` | **The project.** 25 commits, branch `master` pushed to private `Bayern99/deep-reading`. |
| `Downloads/wsj-deep-read-skills/{deep-read,translate}` | Older agent skills: `pdftotext` + TranslateGemma workflow. |
| `Documents/Kuan-Fu Skills/.../deep-reading` | Unrelated academic deep-reading skill. Ignore for this product. |

No other WSJ Deep Read git repos found under Documents. This export **is** the codebase.

### Content for 2026-10-12

- `final.json`: **117** items. Types: 38 article, 25 data_table, 22 photo_caption, 11 brief, 11 opinion, 6 letter, 3 index_digest, 1 correction.
- Bilingual fields present: `title/dek/body` × CN/EN, plus `context_cn` on **12** items.
- Integrity gate: **113 PASS / 4 WARN / 0 BLOCK**. Warns are unconfirmed `turn_to` continuations.
- Rough CN/EN paragraph-count mismatches: ~20 items — content debt, not renderer bugs.
- `raw.txt`: pdftotext dump of the print edition (~4395 lines). Confirms Monday, Oct 12, 2026.
- **Original PDF is not in the repo.** Image crops and ovis-test page PNGs exist; full PDF must be relocated before re-extraction.

### Visual assets

- `2026-10-12/assets/`: 92 image files; `asset_registry.json`: **79** registered assets, **72** article-linked.
- Coverage: extracted 45 / no_asset 49 / unrecoverable 22 / needs_review 1.
- Honest gap: B5/B6 market charts are vector drawings → marked unrecoverable by raster pipeline.
- Manually recovered high-value visuals in `ovis-test/visual-assets/`:
  - `infographic-newleft-donors.png` (E1-033)
  - `chart-dow-jones.png`, `chart-sp500.png` (E3-014)

### Design system — Keep as canon

- `DESIGN.md` v1.0: AJ structure + WIRED type, real accepted values.
- `reference/hybrid-v3/`: approved visual baseline + review notes (including the correct deletion of “主张与现实”).
- Tokens, measure (640px body / 760px head), color discipline, mobile rules — these are product assets, not drafts.

### Runnable production path

```bash
cd render && python3 build.py --issue 2026-10-12
# → ../2026-10-12/dist/index.html
```

Verified facts about current dist:

- Single-file bilingual issue with TOC, masthead, lang toggle, 117 `<article>`s.
- Production curation files are nearly empty: `modules.json` only **E1-005**; `images.json` only **E3-002**.
- Dist contains almost no enhancement primitives (`ed-block`, sidenote, key-figures class usage, embedded assets). It is a **faithful text newspaper**, not the enhanced editorial product described in later reports.

### Editorial / enhancement stack that exists as code

| Piece | Status |
|---|---|
| `components.py` / `article.py` / `issue.py` / `build.py` | Production shell. Works. |
| `source_model.py`, `text_treatment.py`, `layout.py` | Real code; used by enhancement path. |
| `autonomous_planner.py` | Prompted planner with L02/L03/L05/L08 specs; talks to oMLX. |
| `plan_adapter.py`, `plan_validate.py`, `plan_render.py` | Contract + validation + plan-driven render. |
| `orchestrate.py` | Still contains **hardcoded E1-025** outline/treatments — lab code, not a general system. |
| `integrity_gate.py`, `declutter.py`, `turn_page.py` | Content integrity utilities; valuable. |
| Hand plans `editorial-plans/{E1-005,E1-033,E3-014}.json` | Best examples of actual editorial judgment in the repo. |
| Test folders `blind5`, `auto-test`, `layout-test`, `gen-test`, `cases/R3*` | Evidence of iteration; not production. |

### Models / infra (current machine facts)

- Tailscale sees `dmuss-mac-studio` (`100.64.6.57`). Common inference ports on Studio currently return nothing from this laptop.
- Local `~/.pi/agent/models.json` has **no omlx provider** on this machine.
- Repo claims Hy-MT2 + OvisOCR2 + Qwen planner usage in gen-test reports; those claims are **historical**, not currently verified live.
- Do not redownload models. Do not assume endpoints. Confirm Studio before any new extraction/translation work.

---

## B. What Went Wrong

Not a retelling of old reports — judgment from the actual tree and git history.

### 1. Two products, one name

Git moves from baseline issue HTML → DESIGN + production renderer → recovery audit admitting Editorial Intelligence never existed → then a surge of planner/layout/enhancement work.  
The surge produced better **lab pages**, but production `dist/index.html` remained mostly the plain renderer.  
Readers never reliably received the editorial product the docs describe.

### 2. Editorial Intelligence was demonstrated, not industrialized

Evidence:

- Best component plans are hand-authored (`created_by: Juno`).
- `orchestrate.py` hardcodes E1-025.
- `modules.json` has one article.
- Auto-test shows planner can choose L02/L03 with low false positives on a small set — useful — but that is selection skill on a sandbox, not daily production judgment across 117 heterogeneous items.

### 3. Golden-sample gravity

Houthis (E1-005), Davos/Guilfoyle (E1-025), New Left donors (E1-033), Dow charts (E3-014) absorbed disproportionate craft.  
Those pages prove design primitives can look excellent. They do **not** prove the system generalizes.

### 4. Extraction flattened the newspaper’s visual argument

pdftotext preserved text spine. It destroyed maps/charts as first-class evidence.  
Later recovery of a few crops proves the right instinct — keep the graphic — but the default path still treats many visual stories as text leftovers.

### 5. Metrics displaced reading

The repo is full of PASS counts, blind-test matrices, overflow checks. Necessary, insufficient.  
A page can be schema-valid, zero-overflow, and still be an undifferentiated wall of translated prose — or the opposite: component-busy without helping a reader finish the piece.

### 6. Complexity without a single spine

Multiple `build_v2…v7` HTMLs, parallel case builders, gen-test pipelines, enhancement orchestrators.  
Much of it is archaeology of search. The maintainable spine is thinner than the folder count suggests.

### 7. Upstream model story is unsettled

TranslateGemma is what the old skill documents. Hy-MT2 is what later notes decided. Studio is reachable on Tailscale but inference was not verified live in this audit.  
Continuing to “improve the product” while the translation substrate is ambiguous invites more report fiction.

---

## C. What Is Worth Saving

### Keep

1. **DESIGN.md + hybrid-v3** — accepted editorial design language.
2. **`final.json` for 2026-10-12** — freeze as content corpus for reboot proofs; do not regenerate blindly.
3. **Production issue shell** (`build.py` / `issue.py` / `article.py` / `components.py` / `tokens.css`) — best daily-delivery skeleton.
4. **Hand editorial plans** for E1-005 / E1-033 / E3-014 — gold examples of restraint + when to preserve graphics.
5. **LAYOUT_DECISION_SPECS / L02·L03·L05·L08 rules** — especially the insistence on real parallel structure and mobile reflow semantics.
6. **Integrity gate + quote/plan validation ideas** — loud fail > silent empty modules.
7. **Asset registry + recovered chart/infographic PNGs** — directionally correct visual policy.
8. **RECOVERY_AUDIT.md honesty** — still one of the most useful documents in the tree.

### Refactor

- Merge plan-driven rendering into the production builder path (one HTML product).
- Generalize planner I/O; delete article-ID hardcoding.
- Make assets first-class in article render when registry/plan says so.
- Reduce report surface area; keep one integrity gate + one reading QA checklist.

### Replace

- AnyDoc as PDF strategy (already disproven here).
- TranslateGemma as the intended production MT (decision already made; confirm Hy-MT2 live before cutover).
- “modules.json hand-only forever” as the long-term editorial data path — keep human approval, but stop pretending zero automation is the architecture.

### Remove / archive

- Duplicate `wsj-2026-10-12-deepread-v2…v7.html` once reboot proofs supersede them.
- Dead dual builders in `cases/` after primitives are ported.
- Hardcoded `E1025_*` paths in orchestration.
- Habit of equating test-pass counts with product readiness.

### Rebuild (narrow)

- Daily orchestration entrypoint: extract → structure → translate → plan → render → reading QA.
- Chart/infographic recovery path for vector market art (not more OCR prose).
- A small **editorial knowledge** store: positive/negative examples with conditions — not a 51-name catalog with 30 placeholders.

---

## D. What Should Change — Target architecture

Principle: **one spine, selective intelligence, design in service of reading.**

```
WSJ PDF
  → Text spine (pdftotext -layout + continuation merge)
  → Visual spine (page images + photo XObjects + targeted chart crops)
  → Content Model (stable blocks, bilingual map, asset links, provenance)
  → Translation (Hy-MT2 once verified; glossary + numeric/name QA)
  → Editorial Understanding (narrative roles, reader difficulties)
  → Editorial Decisions (T-treatments / L-layouts / A-aids OR deliberate none)
  → Plan Validation (evidence, non-duplication, bilingual alignment)
  → Renderer (DESIGN.md production shell + plan hooks)
  → Reading QA (desktop/tablet/phone, human rubric — not only asserts)
```

### Content Model

Keep paragraph-stable bilingual blocks as source of truth. Add:

- `blocks[]` with stable IDs (already emerging in source_model)
- `assets[]` references with credit/caption/status
- `continuations` / integrity marks
- `plan_id` / `plan_status` without rewriting body text in the renderer

Renderer still must not invent body copy.

### Editorial Intelligence

Planner’s job is comparative judgment among:

- leave alone
- text treatment
- layout change
- reading aid

Not pattern bingo.  
Ship with a tiny validated pattern set (current L02/L03/L05/L08 + restrained T01/T03/T06/T11/quote/timeline/key_figures). Expand only with counterexamples.

Human review remains required for WARN integrity and for any plan that adds `editorial_added` text.

### Editorial Design

Do not reopen AJ×WIRED. Inherit it.  
Invest energy in **content-conditioned layout**, especially mobile semantic reflow (already correctly stated for L02/L03/L08).

### Production

- Cache by content hash; incremental re-plan/re-render.
- Fail loud on empty modules / bilingual desync.
- Daily definition of done = reading QA on a stratified sample, not “117 built.”

### Why this beats status quo

Status quo can print a clean issue **or** show beautiful one-off enhanced pages.  
The product needs enhanced judgment **inside** the daily issue, with restraint as a first-class outcome.  
This architecture reuses the working shell and the hard-won design canon, while forcing lab intelligence onto the only path that ships.

---

## E. First Working Proof

### Goal

Four end-to-end reading samples that are **not** the over-polished Houthis/Davos pair, opened in a real browser at desktop and phone widths.

### Article set

| # | ID | final_id | Why |
|---|---|---|---|
| 1 | **E2-002** | 006 | Long narrative feature (38 CN paras). Has extracted photo. Tests continuity, restraint vs over-modularization, image placement. |
| 2 | **E1-010** | 010 | Analytical markets piece with genuine compare opportunity (prior planner work found real L03). Tests judgment without golden-sample glow. |
| 3 | **E3-004** | 083 | Opinion/analysis (“AI has a God problem”). Tests typographic hierarchy + when *not* to invent data modules. |
| 4 | **E1-014** | 014 | Short brief. Success = almost no intervention. |

Optional fifth visual check (separate, honest): render **E1-033** or **E3-014** using already-recovered graphics as a **visual policy reference**, labeled as recovered assets — not as proof that auto-planning invented them.

### Pipeline for the proof (reuse, don’t rewrite)

1. Freeze `final.json` bodies.
2. Build Source Model blocks for the four IDs.
3. Run planner **or** hand a minimal plan where model infra is down — but label which.
4. Validate plan.
5. Render via plan-aware path into `2026-10-12/reboot-proof/`.
6. Open in browser: 1440 / 768 / 390.
7. Write a one-page reading note per article: Content / Editorial / Design / Reading.

### Success criterion

Not “4/4 generated.”  
Success = a skeptical reader can say: these pages are complete, faithful, selectively edited, and more readable than plain dist — especially on phone — **and** the brief article stayed quiet.

---

## F. Immediate Next Actions

1. **Keep working on `reboot/reconstruction-brief`.** No mass regen. No destructive cleanup yet.
2. **Locate the original 2026-10-12 WSJ PDF** (missing from export). Needed before any extraction reboot.
3. **Verify Mac Studio model endpoints** (Hy-MT2, planner model, Ovis if still used). Until green, proofs use frozen `final.json` + local render only.
4. **Baseline read** current `dist/index.html` vs `test-pages/E1-005.html` / a layout-test page — capture what “good” already looks like.
5. **Implement First Working Proof dir** `2026-10-12/reboot-proof/` for the four articles above; smallest glue necessary to reuse existing renderer/planner.
6. **First checkable artifact for Jerry:** four HTML pages + short reading notes + screenshots at 1440 and 390. No claim of production readiness.

### Explicit non-actions this week

- Do not regenerate all 117 enhanced pages.
- Do not invent a new design system.
- Do not replace the production shell wholesale.
- Do not download models already expected on Studio.
- Do not treat old PASS reports as proof of reader quality.

---

## Bottom line

We are not starting from zero.  
We are starting from a **strong design canon**, a **usable bilingual issue renderer**, a **partial visual recovery path**, and a **lab-grade editorial planner** that never fully owned production.

The reboot is to make editorial judgment ordinary, restrained, and shippable — then prove it on fresh articles, in a browser, on a phone.
