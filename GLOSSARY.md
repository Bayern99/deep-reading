# WSJ 深读 · Domain language

The publication turns a print Issue into one Issue Artifact the reader opens. This vocabulary is independent of the English-to-Chinese terminology glossary used in translation.

Studio-era terms (Final Source, Canonical Source as a sidecar store, Integrity Gate, Editorial Artifact, Source Library, Baseline) are historical. They survive in dated evidence, not here.

## Language

**Issue（期号）**: One dated edition of the print newspaper, containing source items and their editorial treatment.

**Source Item（来源条目）**: One item extracted from the newspaper; it may be an article, brief, letter, digest, caption, table or correction.
_Avoid_: Article when referring to every item in an issue.

**Primary Vector Signal（主向量信号）**: The lossless PDF character stream and Dow Jones font roles (`native.json`), including `Retina*` chart titles, series labels, ticks and sources.
_Avoid_: OCR, secondary PNG crop, pdftotext dump.

**Curation（策展）**: The assignment of each source item to a reading tier and prominence from print-page signals (position, rubric, length, figure density), including grouping fragments into a Composite Column.
_Avoid_: Automatic approval, per-article Studio queue admission.

**Full Editorial Composition（深度精编 / Tier 1）**: Complete model-authored art direction for lead and major feature stories: narrative pacing, documentary figure choreography or declarative visual diagrams, and typographic emphasis over paragraph anchors.
_Avoid_: Template rendering, unanchored summary.

**Typographic Editorial Composition（轻量排版精编 / Tier 2）**: Genre-aware typographic and structural art direction for standard articles, analyses, opinions and reviews — takeaways or thesis boxes, subheadings, inline highlights, pull quotes — without custom diagrams.
_Avoid_: Plain prose dump, rigid JSON slot template.

**Compact Functional Format（紧凑功能版式 / Tier 3）**: Restrained, type-appropriate presentation for briefs, digests, composite columns, corrections and view-only market tables without narrative art direction.
_Avoid_: Full article layout on non-narrative items.

**Forensic Dossier（法医卷宗）**: A Full Editorial Composition grammar for investigation and mechanism stories: a hero ledger, rail metrics, and when the story needs it a navy defense panel or closing verdict, all paragraph-grounded.
_Avoid_: Fourth reading tier, pipeline inspector, Studio evidence sidecar.

**Declarative Visual Primitive（声明式视觉原语）**: Model-authored semantic markup (`<wsj-chart data-src="pK">`) for chart or mechanism structure, labels and paragraph-bound values, compiled into responsive SVG.
_Avoid_: Hand-calculated raw SVG pixel coordinates.

**Chart Companion（图表伴读卡）**: A concise bilingual reading guide paired with an original printed WSJ chart, using lossless `Retina*` labels and paragraph-grounded takeaways.
_Avoid_: Engineering warning banner, unverified OCR table.

**Composite Column（复合专栏）**: A unified reading unit formed by grouping same-page short items of a recurring print rubric — Letters, Stock Spotlight, U.S. Watch, World Watch, Corrections — into one column.
_Avoid_: Single-paragraph standalone article fragments.

**Issue Artifact（整期交付制品）**: The single, lightweight, self-contained HTML publication delivered to the reader for an issue, uniting the edition overview and immersive article reading without operator chrome or embedded audit logs.
_Avoid_: Studio workbench, Editorial Artifact, whole-issue `dist/index.html`, raw evidence bundle.

**Reader（阅读器）**: The reader-facing experience inside the Issue Artifact for browsing the edition and reading bilingual articles.
_Avoid_: Operator console, pipeline inspector.

**LQA Funnel（语言质量漏斗）**: The two-stage bilingual gate over every paragraph pair: a deterministic five-invariant radar, then spot-check of flagged paragraphs and every Tier 1 flagship. It records dispositions; it never rewrites narrative. The report stays in the workspace, not in the Issue Artifact.
_Avoid_: Integrity Gate, claim-evidence sidecar.

**Certification Oracle（认证神谕）**: One of the seven deterministic end-to-end checks over the compiled Issue Artifact (narrative conservation, numeric grounding, chart vectors, figure order, fault-injection recall, print hierarchy, geometry and payload). Reports stay in the workspace, not in the Issue Artifact.
_Avoid_: Host evidence record, browser-metrics pending check.
