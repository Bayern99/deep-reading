#!/usr/bin/env python3
"""WSJ 深读 · Phase 5 End-to-End Editorial Publisher (`editorial_publisher.py`).

Orchestrates:
  Canonical Content -> Art Direction & Source-Referenced HTML Generation ->
  Deterministic AST Compilation & Safety/Integrity Audit ->
  Targeted Auto-Repair (if needed) -> Artifact Store Persistence.

Model-agnostic: accepts any `ModelProvider` instance.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any

from artifact_store import ArtifactStore
from canonical_builder import load_canonical_for_issue
from editorial_compiler import (
    EditorialCompilationError,
    build_targeted_repair_prompt,
    compile_editorial_artifact,
)
from model_provider import GenerationConfig, ModelProvider


EDITORIAL_PUBLISHING_GUIDANCE = """You are the Editorial Director and Lead Interactive Designer at The Wall Street Journal (WSJ 深读 · Editorial Renaissance).
Your mission is to transform the provided WSJ report into a publication-grade, bilingual (Chinese + English) digital reading experience as a single self-contained HTML5 document (`<!DOCTYPE html><html lang="zh-CN">...</html>`).

## 1. Editorial Planning & Content-Conditioned Composition
Before writing markup, analyze the article's genre, narrative arc, core arguments, human scenes, data relationships, and evidence:
- **Do NOT apply a rigid template or fixed count of grids/cards/charts.**
- **For an investigative report** (e.g. financial schemes, corporate accountability): consider asymmetric forensic rails, capital-flow diagrams, participation/return comparisons, official response dossiers, and climactic verdict boxes.
- **For a macroeconomic or markets analysis** (e.g. bond yields, rate forecasts, fiscal deficits): center the composition around the key quantitative comparison (such as survey forecast shifts across time horizons), clear analytical section breaks, and opposing market views.
- **For a long-form narrative or cultural/technology essay** (e.g. AI, religion, human-interest features): prioritize literary reading rhythm, generous serif typography, atmospheric opening scenes, organic chapter pauses, cultural/historical sidebars, and strong pull-quotes—without inventing artificial financial charts where none belong.

## 2. Typography & WSJ Editorial Identity
- Load Google Fonts in `<head>`: `Playfair Display` (700/800), `Lora` (400/600/italic), `Noto Serif SC` (400/600/700), `Noto Sans SC` (400/500/700), `Inter` (400/500/600/700), `JetBrains Mono` (400/500/700).
- Warm editorial paper palette: `--paper: #faf8f4`, `--paper-card: #f3efe6`, `--ink: #141413`, `--body: #242220`, `--muted: #646059`, `--line: #e4dfd3`, `--accent: #b85d19`, `--navy-bg: #0f1d2b`.
- Chinese typography rules: NEVER use `text-wrap: pretty` on Chinese prose; NEVER use CSS `::first-letter` drop-caps on Chinese text (use lead paragraph scale/border-left instead).
- Include a sticky top masthead with a working Bilingual Toggle (`中文` / `EN`) calling `setLang('zh-CN')` and `setLang('en')`, backed by:
  `html[lang="zh-CN"] .lang-en { display: none !important; }`
  `html[lang="en"] .lang-cn { display: none !important; }`

## 3. Source-Referenced Content Protocol (MANDATORY)
You have 100% freedom over the HTML DOM structure, CSS Grid/Flexbox layouts, asymmetric rails, bespoke inline `<svg>` diagrams, and visual pacing.
To guarantee 100% verbatim accuracy without retyping long paragraphs, emit canonical text using **Source Anchors**:

1. **Primary Narrative Flow (`data-ref`)**:
   - Every canonical block `p1` through `pN` MUST appear in exact sequential order (`p1` -> `p2` -> ... -> `pN`) using `data-ref`.
   - **Whole-paragraph anchor (default)**:
     `<p class="prose-p" data-ref="p1"></p>`
     (Leave the element body empty; the deterministic compiler injects `<span class="lang-cn">...</span><span class="lang-en">...</span>`!)
   - **Sentence-level split anchor (optional, when a paragraph has multiple `pK.s1, pK.s2` sub-anchors)**:
     If you want to split a paragraph across two visual containers (e.g. `p20.s1` as narrative prose and `p20.s2` as a climactic quote box), reference each sentence in order:
     `<p class="prose-p" data-ref="p20.s1"></p>`
     `<blockquote class="verdict-quote" data-ref="p20.s2"></blockquote>`
   - If a block is marked `[subheading]` in the canonical source, render it as an `<h2 class="source-subhead" data-ref="pK"></h2>` in its exact sequence position!
   - You may also use `data-ref="title"`, `data-ref="dek"`, and `data-ref="ctx1"` (if context dossier exists).

2. **Exact Inline Highlighting (`data-hl`)**:
   - To highlight exact phrases or figures inside a `data-ref` block, add `data-hl="phrase 1 | phrase 2"`:
     `<p class="prose-p" data-ref="p1" data-hl="4 万美元 | $40,000"></p>`
   - Style `mark.ed-hl` cleanly in your CSS.

3. **Derived Visual Callouts (`data-derive`)**:
   - To display an evidence-reviewed pull-quote (`q1`..) or metric card (`m1`..) in a sidebar/callout:
     - Quote: `<blockquote class="pull-quote" data-derive="q1"><p class="quote-text" data-field="quote"></p><footer class="quote-attrib" data-field="attribution"></footer></blockquote>`
     - Metric: `<div class="metric-card" data-derive="m1"><div class="metric-val" data-field="value"></div><div class="metric-lbl" data-field="label"></div><div class="metric-note" data-field="note"></div></div>`
   - Do NOT place a `data-derive` quote in the same `<section>` if you already split that exact quote into a primary `blockquote` via `data-ref`.

4. **Bespoke Inline `<svg>` Diagrams & Responsive Mobile Reflow**:
   - Always set an explicit `viewBox="0 0 W H"` and `width="100%"` on `<svg>` elements. Leave at least 30px horizontal/vertical clearance inside the `viewBox` so text labels never clip at the edges.
   - At `390px` mobile width, all multi-column grids and sidebars must collapse cleanly into a single column with zero horizontal overflow (`scrollWidth <= clientWidth`).

## 4. Claim Provenance (MANDATORY FOR NEW PUBLICATION)
Canonical quotes/metrics are candidates, not verified facts. Do not reuse a rejected
candidate. Preserve design freedom, but ground every added factual claim in source
spans. Quotes must be verbatim; calculations must identify operands and units.
Label interpretations visibly as "Editorial analysis" / "编辑解读". SVG series,
labels, horizons and geometry require host semantic review. The host supplies a
source/claim-bound evidence sidecar to the compiler; HTML cannot approve itself.
Unreviewed additions are retained for review and cannot be promoted as verified.
Compose each intervention as ONE self-contained block (`<figure>`, `<aside>`,
`<section>`, `<table>`): its heading, copy, data labels and drawing are reviewed
together as a single unit, so keep one visual idea per block and do not scatter
bare numbers or quotations into loose wrappers outside it.

Return ONLY the complete `<!DOCTYPE html>` document with no markdown fences.
"""


def format_canonical_for_generation(canonical: dict[str, Any]) -> str:
    meta = canonical["metadata"]
    total = len(canonical["blocks"])
    lines = [
        f"## Canonical Article Source ({canonical['article_id']} · {meta['section']} · Page {meta['page']})",
        f"- **Article Type**: {meta['type']} | **Total Canonical Blocks**: {total} (`p1` .. `p{total}`)",
        f"- **Title (CN)**: {meta['title_cn']}",
        f"- **Title (EN)**: {meta['title_en']}",
    ]
    if meta.get("dek_cn") or meta.get("dek_en"):
        lines.append(f"- **Dek (CN)**: {meta.get('dek_cn', '')}")
        lines.append(f"- **Dek (EN)**: {meta.get('dek_en', '')}")
    lines.append(f"- **Byline**: {meta['byline']} ({meta['date_cn']} / {meta['date_en']})")
    lines.append(f"\n### Primary Narrative Blocks (`p1` .. `p{total}` — MUST ALL BE REFERENCED IN ORDER VIA `data-ref`)")

    for b in canonical["blocks"]:
        pid = b["id"]
        role_tag = " [SOURCE SUBHEADING]" if b.get("role") == "source_head" else ""
        lines.append(f"\n#### [{pid}]{role_tag}")
        lines.append(f"- **CN**: {b['text_cn']}")
        lines.append(f"- **EN**: {b['text_en']}")
        if len(b.get("sentences", [])) > 1:
            lines.append("  *Sentence sub-anchors (optional, only if splitting this paragraph):*")
            for s in b["sentences"]:
                lines.append(f"  - `[{s['id']}]` CN: {s['text_cn']} | EN: {s['text_en']}")

    if canonical.get("derived_quotes"):
        lines.append("\n### Quote Candidates (`data-derive`; host evidence required)")
        for q in canonical["derived_quotes"]:
            verdict = next((c for c in canonical.get('claim_provenance', {}).get('claims', []) if c['target'] == f'derive:{q["id"]}'), {})
            if verdict.get('status') == 'rejected':
                lines.append(f"- `{q['id']}` REJECTED: {'; '.join(verdict.get('errors', []))}")
                continue
            lines.append(
                f"- **`[{q['id']}]`** (from `{q['source_block']}`): CN={q['quote_cn']} ({q['speaker_cn']}) | EN={q['quote_en']} ({q['speaker_en']})"
            )

    if canonical.get("derived_metrics"):
        lines.append("\n### Metric Candidates (`data-derive`; host evidence required)")
        for m in canonical["derived_metrics"]:
            verdict = next((c for c in canonical.get('claim_provenance', {}).get('claims', []) if c['target'] == f'derive:{m["id"]}'), {})
            if verdict.get('status') == 'rejected':
                lines.append(f"- `{m['id']}` REJECTED: {'; '.join(verdict.get('errors', []))}")
                continue
            lines.append(
                f"- **`[{m['id']}]`** (from `{m['source_block']}`): value=`{m['value']}` (`{m['value_cn']}`) — {m['label_cn']} / {m['label_en']} ({m['note_cn']})"
            )

    ctx = canonical.get("context_dossier")
    if ctx:
        lines.append("\n### Background Context Candidate (`data-ref=\"ctx1\"`; host evidence required)")
        lines.append(f"- **CN**: {ctx['text_cn']}")
        lines.append(f"- **EN**: {ctx['text_en']}")

    return "\n".join(lines)


def build_editorial_generation_prompt(canonical: dict[str, Any], custom_instructions: str = "") -> str:
    source_section = format_canonical_for_generation(canonical)
    extra = f"\n## Additional Art Direction Notes\n{custom_instructions}\n" if custom_instructions else ""
    return f"{EDITORIAL_PUBLISHING_GUIDANCE}\n{extra}\n{source_section}\n"


def _strip_markdown_fences(text: str) -> str:
    s = (text or "").strip()
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z]*\n", "", s)
        s = re.sub(r"\n```$", "", s.strip())
    return s.strip()


def publish_article(
    *,
    issue_dir: str,
    article_id: str,
    provider: ModelProvider,
    config: GenerationConfig | None = None,
    max_retries: int = 1,
    custom_instructions: str = "",
    notes: str = "",
    progress_callback: Any = None,
    evidence_records: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Run the full Generative Editorial Publishing pipeline for an article with automatic repair fallback."""
    def _notify(stage: str, detail: str = "") -> None:
        if callable(progress_callback):
            try:
                progress_callback(stage, detail)
            except Exception:
                pass

    _notify("building_canonical", f"Building Canonical Source for {article_id}…")
    canonical = load_canonical_for_issue(issue_dir, article_id=article_id)
    gate = canonical.get("integrity_gate") or {}
    if gate.get("status") == "block":
        raise ValueError(f"Article {article_id} is BLOCKED by Content Integrity Gate: {gate.get('issues')}")

    store = ArtifactStore(issue_dir)
    store.save_canonical(canonical)

    base_prompt = build_editorial_generation_prompt(canonical, custom_instructions=custom_instructions)
    current_prompt = base_prompt

    last_raw_html = ""
    last_audit: dict[str, Any] = {}

    for attempt in range(1, max_retries + 2):
        model_label = (config.model_id if config else "default")
        _notify(
            "calling_model" if attempt == 1 else "repairing_with_model",
            f"Attempt {attempt}/{max_retries + 1}: Generating Source-referenced HTML via {model_label}…",
        )
        try:
            gen_result = provider.generate(current_prompt, config=config)
        except Exception as gen_err:
            store.save_failed_attempt(
                canonical=canonical,
                raw_html="",
                audit_report={"passed": False, "errors": [f"Model provider error: {gen_err}"]},
                model_metadata=config.to_metadata() if config else {"model_id": model_label},
                error_message=f"Model provider error: {gen_err}",
            )
            raise

        raw_html = _strip_markdown_fences(gen_result.content)
        last_raw_html = raw_html

        _notify("compiling_and_auditing", f"Attempt {attempt}: Running AST compiler & verbatim content audit…")
        try:
            compiled_bundle = compile_editorial_artifact(raw_html, canonical, strict=True, auto_repair_svg=True, evidence_records=evidence_records)
            _notify("persisting_artifact", f"Saving verified artifact for {article_id}…")
            artifact_rec = store.save_verified_artifact(
                canonical=canonical,
                raw_html=raw_html,
                compiled_html=compiled_bundle["compiled_html"],
                shadow_bundle=compiled_bundle["shadow_bundle"],
                audit_report=compiled_bundle["audit_report"],
                model_metadata=gen_result.config.to_metadata(),
                usage_metadata=gen_result.usage.to_dict(),
                notes=notes or (f"Auto-repaired on attempt {attempt}" if attempt > 1 else "Primary generation"),
            )
            _notify("completed", f"Verified {artifact_rec['artifact_version']} saved.")
            return artifact_rec
        except EditorialCompilationError as comp_err:
            last_audit = comp_err.audit_report
            # Semantic review belongs to the host, not the generating model's repair loop.
            needs_review = any(c['active'] and c['status'] == 'needs_review' for c in last_audit.get('claim_provenance', {}).get('claims', []))
            if attempt <= max_retries and not needs_review:
                _notify("repair_needed", f"Attempt {attempt} had compiler errors ({'; '.join(last_audit.get('errors', [])[:2])}); running targeted repair…")
                current_prompt = build_targeted_repair_prompt(base_prompt, raw_html, last_audit)
            else:
                store.save_failed_attempt(
                    canonical=canonical,
                    raw_html=raw_html,
                    audit_report=last_audit,
                    model_metadata=gen_result.config.to_metadata(),
                    error_message=str(comp_err),
                )
                raise
    raise RuntimeError("Unreachable")


def import_raw_generation(
    *,
    issue_dir: str,
    article_id: str,
    raw_html: str,
    model_metadata: dict[str, Any],
    usage_metadata: dict[str, Any] | None = None,
    notes: str = "",
    evidence_records: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Compile, validate, and persist a raw Source-referenced HTML generation into the ArtifactStore."""
    canonical = load_canonical_for_issue(issue_dir, article_id=article_id)
    store = ArtifactStore(issue_dir)
    store.save_canonical(canonical)

    raw_clean = _strip_markdown_fences(raw_html)
    try:
        compiled_bundle = compile_editorial_artifact(raw_clean, canonical, strict=True, auto_repair_svg=True, evidence_records=evidence_records)
        return store.save_verified_artifact(
            canonical=canonical,
            raw_html=raw_clean,
            compiled_html=compiled_bundle["compiled_html"],
            shadow_bundle=compiled_bundle["shadow_bundle"],
            audit_report=compiled_bundle["audit_report"],
            model_metadata=model_metadata,
            usage_metadata=usage_metadata,
            notes=notes,
        )
    except EditorialCompilationError as comp_err:
        store.save_failed_attempt(
            canonical=canonical,
            raw_html=raw_clean,
            audit_report=comp_err.audit_report,
            model_metadata=model_metadata,
            error_message=str(comp_err),
        )
        raise
