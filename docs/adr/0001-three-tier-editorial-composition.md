[ English | [简体中文](0001-three-tier-editorial-composition.zh-CN.md) ]

# Three-Tier Editorial Composition from Primary PDF Signals

**Status: accepted**

WSJ Deep Read is a reusable CLI and Agent workflow. Given a user-supplied print PDF and an external issue workspace, it produces one portable, self-contained HTML Issue Artifact. The workspace supplies issue-specific metadata, article inventory, reviewed bilingual paragraphs, print evidence, and editorial decisions. The tool provides the reusable rules and compiler.

The product path reads primary PDF vector and font signals, routes items through a Three-Tier Editorial Hierarchy, grounds every intervention in source paragraphs, extracts printed chart vectors, runs the two-stage LQA Funnel, and emits one HTML artifact with no operator surface.

## Decision

**Use Primary Vector Signals and three distinct editorial tiers.** Keep approved narrative inline in the issue data and bind authored material to paragraph IDs with `data-src="p2"` or `data-ref`. Model-authored charts use semantic markup such as `<wsj-chart data-src="p2">`; the compiler checks source grounding and renders the graphic. A direct quote remains verbatim in the language it quotes.

The tiers mean:

- **Tier 1 — Full Editorial Composition:** complete art direction for selected lead and feature stories. Choose narrative pacing, original figure choreography, or a declarative visual diagram based on the story. A Forensic Dossier is one supported grammar for investigations and mechanism stories.
- **Tier 2 — Typographic Editorial Composition:** genre-aware typographic treatment for standard articles, analyses, opinions, and reviews. Takeaways, thesis boxes, subheadings, highlights, pull quotes, and work metadata are candidates, not required slots.
- **Tier 3 — Compact Functional Format:** restrained presentation for briefs, digests, corrections, letters, and read-only tables. It has no flagship header or unnecessary narrative art direction.

The Agent reads the entire item before choosing among no intervention, text treatment, layout change, or a reading aid. It compares reader benefit against repetition, space, and reading-order cost. Leaving the prose alone is a valid outcome; component count is not a quality measure.

## Considered options

- **A uniform deterministic template over pre-cropped secondary assets:** rejected. It removes editorial composition, can place all figures before the narrative, may chop chart headings, and makes OCR text the authority over the original vectors.
- **Fixed JSON slots for every Tier 2 story:** rejected. Fixed slots produce repetitive cards and confuse supported editorial treatment with required filling.
- **Model-authored raw SVG coordinates and external claim ledgers:** rejected. Hand-calculated coordinates can clip text or distort scale; maintaining many external span bindings makes routine work brittle. Semantic primitives let the compiler own geometry and verification.
- **Silent tier fallback when compilation fails:** rejected. Removing a diagram or downgrading a story to plain text hides a defect and can degrade reading quality. Repair the smallest offending node when its source is clear; otherwise fail with a specific error.
- **A local workbench with external asset folders or embedded evidence bundles:** rejected. The reader receives one portable HTML artifact; source PDF, extracted evidence, and review reports stay in the external issue workspace.

## Consequences

- **Extract from the source PDF.** Read its character stream and font roles. For printed charts, crop from the original PDF using the union of the graphic and adjacent `Retina*` title/source lines. This preserves chart labels without treating OCR or an existing crop as authoritative.
- **Route using page evidence.** Use printed prominence, section, length, and figure density to choose a tier. Group short same-page items under a shared printed rubric into a Composite Column when that matches how readers encounter them. The issue determines its own counts and membership.
- **Let genre and evidence shape Tier 1 and Tier 2.** A figure-light mechanism story may use a declarative diagram. A photo-rich feature may place original figures in their natural `after pK` reading position. Tier 2 grammar adapts by genre: analysis takeaways, an opinion thesis and direct quote, a review work card, or a sidebar linked to its parent. Use only a treatment supported by the item.
- **Verify at paragraph scope.** Authored numbers must be present in their declared source paragraphs. A synthetic example: if `p2` says that a fleet has 120 buses, a module bound to `p2` may render that count; it cannot add a projection from elsewhere.
- **Repair narrowly or fail.** The compiler can insert a missing narrative anchor in the HTML tree and retry a specific factual node when the source is clear. It never silently drops a required tier or invents a replacement.
- **Pair original charts with concise bilingual guidance.** Anchor the WebP source chart in physical print order and bind its Chart Companion to the same chart vectors and cited prose. Chart labels come from `Retina*` vectors, not OCR.
- **Keep the Reader clean.** It owns the seven canonical sections, issue overview, immersive reading, and Chinese / English / bilingual switching. In bilingual mode the main prose pairs languages; SVG labels and micro-controls remain single-language where pairing would break geometry. Reports and source evidence stay outside the HTML.
