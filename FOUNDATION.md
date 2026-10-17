# WSJ 深读 · Foundation

Audience: the person or agent compiling the next Issue Artifact.

This file is the product constitution. `DESIGN.md` is the visual canon of the Issue Artifact.
Current modules and limitations live in `ARCHITECTURE.md`; commands live in `render/BUILD.md`.
Content changes every day. These principles do not.

---

## Product

A Chinese AI-native digital newspaper people open every day: faithful WSJ journalism, editorial judgment from typography through whole-issue composition, a distinctive identity developed from AJ × WIRED, mobile-first, bilingual.

Delivery is one lightweight Issue Artifact compiled from Primary Vector Signals. There is no operator workbench on the reader surface.

One-line test: **does this look like a newspaper, or a production log?**
If a reader can see the pipeline, the surface is wrong.

---

## What is foundation (stable)

| Layer | File | Changes when |
|---|---|---|
| Visual tokens, type, measure | `DESIGN.md`, `render/tracer/shell.py` | Evolve from the Issue Artifact when real reading evidence justifies it. |
| Reader surface rules | this file | When the newspaper identity changes, not when a story changes. |
| Publishing implementation | `render/tracer/` compiler, LQA Funnel, Certification Oracles | Bugfixes and reusable capabilities, not per-article renderer hacks. |
| Integrity | Paragraph-scoped `data-src`, LQA Funnel, Certification Oracles | When a new failure mode appears. |

## What is daily (must change)

| Layer | File | Owner |
|---|---|---|
| Print PDF | external protected original | retain outside Git |
| Primary Vector Signals | issue `native.json` / pinned `PILOT_ROOT` | vector extraction |
| Reviewed bilingual units | issue translation inventory | extraction → glossary → translation → QA |
| Curation | print-signal routing in `tracer/routing.py` | editor / agent following print hierarchy |
| Flagship editorial layers | `tracer/content.py` (issue-specific) | Full Editorial Composition, including Forensic Dossier |
| Delivery | Issue Artifact HTML | `make tracer` / `make tracer-certify` |

Do not copy 2026-10-12 or 2026-10-14 story IDs into renderer code as if they were the next issue.

---

## Invariants

1. **Verbatim body.** Reviewed English source and Chinese translation are the approved copy. Compilation never rewrites or retranslates narrative text, and never uses `text-wrap: pretty` on Chinese prose. The LQA Funnel records dispositions; it does not edit paragraphs.
2. **Coherent editorial identity.** Develop from AJ × WIRED. Variation must express real content relationships. Typography is reading craft. See `DESIGN.md`.
3. **No pipeline chrome on the Reader surface.** Forbidden: machine-translation banners, per-edition summaries as dek, "Vertical Tracer", gate-report dumps, article counts as dek, baseline links, operator queue UI. Internal ids may exist hidden for asserts. Workspace JSON never ships inside the Issue Artifact.
4. **No invented modules.** Takeaways, thesis boxes, Forensic Dossier panels, charts and companions appear only from print-grounded composition. Empty editorial layer → clean article.
5. **No restatement.** A module must add a view the body does not already give. Tier 2 takeaway/thesis elements do not cite the lede (`p1`).
6. **No 「主张与现实」 / duel.** Deleted. Do not revive.
7. **Type is layout.** Full Editorial Composition, Typographic Editorial Composition and Compact Functional Format are different surfaces. Do not stamp a flagship header on a digest or a Composite Column.
8. **Self-contained delivery.** The Issue Artifact is one HTML file (target 5–8 MB). Google Fonts may be external. No Studio server, no npm runtime, no embedded PDF, no full-page PNG evidence bundle.
9. **Mobile is the product.** 390px must read comfortably: 17px / 1.85 body, one 20px inset per side. Certification Oracle 7 probes 1440×900 and 390×844 in 中文 / EN / 双语. Zero overflow alone does not prove reading quality.
10. **Primary Vector Signals over secondary crops.** Printed charts re-crop from the PDF union of the graphic and adjacent `Retina*` title/source lines. Do not prefer chopped PNG crops or OCR tables for chart labels.
11. **Paragraph-scoped fidelity.** Every authored element's substantive numbers ground in its `data-src` paragraphs (plus `Retina*` text for Chart Companions). Cross-language magnitude must match (`$2.3 billion` ≡ 「23亿美元」). Fail the compile rather than silently drop a number or a tier.
12. **Print over inference.** A fact printed on the page is read, never guessed. Fields carried by a printed mark — continuation markers, section heads, folio labels, body extent — are derived deterministically and audit back to a `line_id` or a bbox. A model is used only for what no printed mark carries, and only behind a confidence threshold that flags the rest for host review. One source per field: two sources for the same fact is both slower and wrong. Every derived signal carries an adversarial test that perturbs the printed mark and asserts the output follows, so the check proves the rule reads the paper rather than remembering an answer. Speed and quality are the same move here, because inference is both the slow path and the wrong one.

---

## Front (every issue)

The Issue Artifact opens on an edition overview, then immersive reading units. The dek is today's reason to open, not a production statistic. Lead treatment follows print A1 news, not What's News, not a photo caption, not a table.

Jump navigation is the seven canonical sections, not a file tree of raw section strings.

Kicker on stories: print rubric / section label. Priority codes are internal.

---

## Editorial composition

Curation is print-signal routing into three tiers and Composite Columns (ADR 0001). Flagship layers may include Forensic Dossier grammar. Models emit Declarative Visual Primitives, not raw SVG coordinates.

Decline a module when it restates, fills a column, or was copied from yesterday.

---

## Acceptance principles

A published Issue Artifact preserves source copy (Certification Oracle 1), bilingual numeric and qualifier agreement (LQA Funnel), printed-chart vectors, figure order, and the publication's editorial identity. Oracle PASS does not replace reading the newspaper.

Inspect desktop and 390px, Chinese, English and bilingual, overview and immersive views, figures, one flagship and one digest. Confirm no horizontal overflow, no duplicated interventions and comfortable continuous reading.

Operational commands and current limitations: `render/BUILD.md` and `ARCHITECTURE.md`.
