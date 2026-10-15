# WSJ 深读 · Domain language

The publication separates source journalism, editorial intervention and saved reading experiences. This vocabulary is independent of the English-to-Chinese terminology glossary used in translation.

## Language

**Issue（期号）**: One dated edition of the publication, containing source items and their editorial treatment.

**Source Item（来源条目）**: One item extracted from the newspaper; it may be an article, brief, letter, digest, caption, table or correction.
_Avoid_: Article when referring to every item in an issue.

**Final Source（内容定稿）**: The QA-approved English source and Chinese translation from which reading content is published.
_Avoid_: Draft, generated article.

**Canonical Source（规范来源）**: An ordered bilingual projection of an approved source item, with traceable narrative anchors and source-derived material.
_Avoid_: Summary, rewritten article.

**Integrity Gate（完整性门禁）**: The editorial safeguard classifying known source completeness risks as PASS, WARN or BLOCK. WARN remains an unresolved review decision.

**Full Editorial Composition（深度精编 / Tier 1）**: Complete model-authored art direction for lead and major feature stories, combining narrative pacing, documentary figure choreography or declarative visual diagrams, and typographic emphasis over canonical source anchors.
_Avoid_: Template rendering, unanchored summary.

**Typographic Editorial Composition（轻量排版精编 / Tier 2）**: Genre-aware model-authored typographic and structural art direction for standard articles, analyses, opinions and reviews—including takeaways or thesis boxes, subheadings, inline sentence highlights, pull quotes and key figures—without custom diagrams.
_Avoid_: Plain prose dump, rigid JSON slot template.

**Compact Functional Format（紧凑功能版式 / Tier 3）**: Restrained, type-appropriate presentation for briefs, digests, composite columns, corrections and view-only market tables without narrative art direction.
_Avoid_: Full article layout on non-narrative items.

**Declarative Visual Primitive（声明式视觉原语）**: Model-authored semantic markup specifying chart or mechanism structure, labels and paragraph-bound values (`data-src="pK"`), compiled deterministically into responsive SVG graphics.
_Avoid_: Hand-calculated raw SVG pixel coordinates.

**Chart Companion（图表伴读卡）**: A concise bilingual reading guide paired with an original printed WSJ chart, explaining its headline takeaway and key series labels without unverified machine table transcription or disclaimer banners.
_Avoid_: Engineering warning banner, unverified OCR table.

**Composite Column（复合专栏）**: A unified reading unit formed by grouping same-page short items of a recurring print rubric—such as Letters to the Editor, Stock Spotlight, U.S. Watch or World Watch—into one cohesive column.
_Avoid_: Single-paragraph standalone article fragments.

**Editorial Artifact（单篇编辑制品）**: A compiled reading experience generated from canonical source and verified for narrative and paragraph-scoped numeric integrity.
_Avoid_: Final Source, deterministic plain-prose wrapper.

**Issue Artifact（整期交付制品）**: The single, lightweight, self-contained HTML publication delivered to the reader for an issue, uniting the front-page edition overview and immersive article reading without operator chrome or embedded audit logs.
_Avoid_: Studio workbench, raw evidence bundle.

**Curation（策展）**: The editorial decision assigning each source item to its reading tier and prominence within the issue.
_Avoid_: Automatic approval.

**Source Library（来源库）**: The complete issue inventory, including items withheld from reader publication.
_Avoid_: Published newspaper.

**Reader（阅读器）**: The reader-facing experience inside the Issue Artifact for browsing the edition and reading bilingual articles.
_Avoid_: Operator console, pipeline inspector.

**Baseline（基线）**: A faithful comparison rendering using the same source projection and verified assets, without the compared editorial intervention.
_Avoid_: Old output that differs in source repair or image coverage.
