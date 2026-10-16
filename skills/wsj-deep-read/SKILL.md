---
name: wsj-deep-read
description: Compile a daily WSJ print PDF into a portable single-file bilingual Issue Artifact and certify it with the LQA Funnel and seven Certification Oracles. Use when a cloud agent or bot VM needs to build and validate the WSJ 深读 Issue Artifact as a CLI or Skill.
---

# WSJ 深读 · Lightweight Full-Issue Pipeline

Compiles one WSJ print issue into a single self-contained HTML Issue Artifact
(target 5–8 MB) from Primary Vector Signals — no operator workbench, no queue
daemon, no evidence sidecar, no external asset directories on the reader surface.

## Run

```bash
python3 render/tracer_pipeline.py --mode full \
    --output wsj-2026-10-14.html \
    --gate-report gate-report.json \
    --certify oracle-certification.json
```

- `--mode full` compiles all 86 raw inventory items into 71 reading units.
  `--mode tracer` keeps the five-unit pilot slice; `--units id,...` filters;
  `--fast` skips PDF raster work (smoke; certification then skips the
  payload-budget check).
- Requires the issue dataset (inventory + reviewed translations + native
  vector streams) and the original print PDF at the pinned paths in
  `render/tracer/compose.py`. Python 3.11+, `lxml` always; `fitz` (PyMuPDF)
  + `PIL` for real (non-`--fast`) runs.
- Exit code is non-zero when any of the 7 oracles fails.
- `gate-report.json` and `oracle-certification.json` are workspace reports;
  they are never embedded in the reader HTML.

## Three-tier editorial composition (ADR 0001)

Print signals (page position, rubric, item type, multi-page jumps) route
every raw item into exactly one unit — never silently downgraded:

- **Tier 1 (8 flagships)** — sub-mode composition: `<wsj-chart>` declarative
  SVG primitives and/or original figures anchored at their natural
  `after pK` print position; printed charts re-cropped from the PDF (union
  bbox of the graphic + adjacent `Retina*` title/source lines) and paired
  with bilingual Chart Companion cards.
- **Tier 2 (54 units)** — genre-aware layer: `article/analysis` get 1-2-3
  takeaway bullets from numbered post-lede paragraphs; `opinion/editorial`
  get a thesis box (never the lede) + verbatim pull quote; `review` gets a
  work-metadata card; `sidebar` cross-links its parent story.
- **Tier 3 (9 units)** — compact functional formats: the What's News digest
  with 16 deep links, 5 Composite Columns (Letters, Stock Spotlight,
  U.S./World Watch, Corrections), briefs, a photo caption and view-only
  market tables.

Every authored element carries `data-src="pK"`; all of its substantive
numbers must ground in the referenced paragraph(s) (plus the chart's
`Retina*` vector text), and the 86-item narrative round-trips byte-for-byte
(SHA256) into the artifact.

## 7-Oracle certification (`--certify`)

Deterministic, programmatic checks over the generated HTML
(`render/tracer/oracles.py`):

1. **Narrative conservation** — SHA256 round-trip of the ordered CN/EN
   paragraph sequences for all 86 raw items (86/86, diff 0).
2. **Numeric grounding** — 100% of substantive numbers in every authored
   element are grounded in its declared paragraph(s).
3. **Chart vector coverage** — all 21 printed charts: union crop within the
   chart column, zero body prose or sliced multi-column source fragments
   inside crops, intact `RetinaMedium` titles, paired companions.
4. **Figure monotonicity & ad exclusion** — figures follow physical print
   order after their anchor paragraph; print ads never appear.
5. **Fault-injection recall** — 6/6 historical failure classes rejected.
6. **Print hierarchy** — 86→71 units, 7 canonical sections, 16/16 deep
   links resolve, zero Tier 2 takeaway/thesis cites the lede.
7. **Geometry & payload** — size within [4.5 MB, 10 MB], zero forbidden
   pipeline strings, Headless Chrome probe (1440x900 and 390x844 ×
   中文/EN/双语) with no horizontal overflow, broken images or clipped SVG
   text.
