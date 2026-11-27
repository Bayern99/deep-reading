[ English | [简体中文](0003-derived-article-map.zh-CN.md) ]

# Derive the Article Map from Print Signals, Review Semantic Judgements

**Status: accepted**

The article map records one issue's source-item ownership and placement. A Reading Pass identifies candidate items and the exact printed lines or blocks they own. Deterministic derivation then binds those answers to Primary Vector Signals and printed page structure.

The map carries `id`, `type`, `section`, `start_page`, `all_pages`, printed continuation evidence, title source, byline, media, paragraphs, and regions as available. It is issue-scoped input to translation and composition, not a list of fixed IDs or expected counts.

## Decision

Separate printed facts from human or model judgement. Derive fields from printed marks whenever the page carries them. Ask the Reading Pass only for content ownership or meaning that cannot be read from a print mark, and flag uncertain judgements for human review.

### Derived from printed evidence

- **`start_page`:** the page containing the item's first body block.
- **`all_pages`:** the start page plus continuation pages named by the printed forward and backward markers. Do not join stories by headline similarity.
- **`section`:** use the section head printed on the page. When a printed section is absent or ambiguous, the Reader Pass judgement is explicit and reviewed rather than guessed.
- **`continuation_evidence`:** keep the marker's `line_id`, text, page, and bounding box so the relationship can be audited.
- **Folio to PDF page:** cross-pair the forward and backward printed markers. Do not replace them with a hand-written page lookup table.
- **Title and byline:** preserve the printed title and byline lines as source material. A section label, caption, or running headline is not automatically an article title.

### Judgement and review

- **`type`:** printed layout can narrow the candidates, but the distinction between article, brief, caption, letter, and other reading units requires semantic judgement. Flag low-confidence items for host review.
- **Reading-item ownership:** the Agent identifies exact line IDs or block indexes and names the item kind. Its answer must bind to the supplied page bundle.
- **Paragraphs:** paragraph starts are derived from printed indents, type size, and drop caps once the item's owned lines are known ([ADR 0005](0005-paragraph-boundaries-from-printed-indents.md)).
- **Regions:** retain regions and their source/review metadata as an auditable draft. The composer does not use per-story regions as a compile input ([ADR 0004](0004-page-column-grid-not-story-regions.md)).

## Considered options

- **Generate every field with no review:** rejected. Meaning and ownership that the printed page does not encode still need a judgement, and uncertain cases must be visible.
- **Require a person to redraw every printed fact page by page:** rejected. Printed markers already provide auditable evidence for fields such as continuation and page location.
- **Generate only a small routing map:** rejected. Translation and composition also need paragraphs, media, title and byline sources, and placement evidence.
- **Infer continuation by headline similarity:** rejected. Printed continuation markers provide direct evidence; similarity can join unrelated items or miss renamed continuations.

## Consequences

- Each new issue gets a derived article-map draft from its own Reader Pass answers and vector pages. Counts and IDs come from the current issue.
- The Reader Pass is a semantic authority for item discovery, not a source of printed facts. The derivation binds its answer to the page and catches invalid line, block, and continuation references.
- The person preparing an issue reviews ambiguous ownership and every `needs_review` flag before translations and finalization. The tool must not claim that every page fact has been independently verified by a model.
- A page with no editorial reading items must have an explicit empty answer. This keeps absence distinct from a missing Agent response.
