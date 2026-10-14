#!/usr/bin/env python3
"""Prompt builder for Phase 5 Experiment 01: Group B (Free HTML) vs Group C (Source-referenced HTML).

Both groups share the exact same Editorial Design Direction, article text, and typography/color guidance,
differing ONLY in how canonical text is emitted in the HTML.
"""
from __future__ import annotations
import json
from typing import Any


SHARED_EDITORIAL_DIRECTION = """You are the Editorial Director and Lead Interactive Designer at The Wall Street Journal (WSJ 深读 · Editorial Renaissance).
Your task is to transform a front-page investigative report into a world-class, publication-grade bilingual (Chinese + English) digital reading experience as a single self-contained HTML5 document (`<!DOCTYPE html>`).

## Editorial Design Philosophy & Visual Language
1. **Content-Conditioned Editorial Architecture**:
   - Read the entire investigation carefully: understand its human opening, institutional mechanism, arithmetic/yield gap, corporate defense, regulatory/commission incentives, and climactic verdict.
   - You have full creative freedom over the whole-article layout, visual pacing, CSS Grid/Flexbox composition, asymmetric rails, chapter transitions, callouts, and inline SVG diagrams/charts.
   - Do NOT follow a rigid component template or mechanical count of modules. Every visual intervention must earn its place by helping the reader grasp a real relationship in the reporting.

2. **Typography & Reading Craft**:
   - Load Google Fonts in `<head>`: `Playfair Display` (700/800), `Lora` (400/600/italic), `Noto Serif SC` (400/600/700), `Noto Sans SC` (400/500/700), `Inter` (400/500/600/700), `JetBrains Mono` (400/500/700).
   - Warm editorial paper palette: e.g., `--paper: #faf8f4`, `--paper-card: #f3efe6`, `--ink: #141413`, `--body: #242220`, `--muted: #646059`, `--line: #e4dfd3`, `--accent: #b85d19` (terracotta/amber), `--navy-bg: #0f1d2b`.
   - Chinese typography discipline: NEVER use `text-wrap: pretty` on Chinese body prose; NEVER use CSS `::first-letter` drop-caps on Chinese paragraphs (use lead paragraph stature/scale instead).
   - Provide a clean sticky top masthead with a working Bilingual Toggle (`中文` / `EN`) that switches `document.documentElement.lang` between `"zh-CN"` and `"en"`, paired with CSS rules:
     `html[lang="zh-CN"] .lang-en { display: none !important; }`
     `html[lang="en"] .lang-cn { display: none !important; }`

3. **Inline SVG Diagrams & Visual Evidence**:
   - Where the investigation explains structural capital flows, participation-rate ratchets, or return comparisons, you may craft bespoke inline `<svg viewBox="...">` diagrams or visual exhibits.
   - Ensure SVG text never overflows boxes, `<path>` connectors have `fill="none"`, and every number shown in a chart or exhibit is strictly grounded in the article's reported figures.

4. **Desktop (1440px) & Mobile (390px) Responsiveness**:
   - Desktop can use contextual asymmetric grids, sticky forensic rails, or full-bleed analytical sections.
   - At `390px` mobile width, all multi-column grids and rails must reflow cleanly into a single readable column with **zero horizontal overflow (`scrollWidth <= clientWidth`)** and no clipped/hidden text.
"""


def format_canonical_source_for_prompt(canonical: dict[str, Any], *, include_sentence_ids: bool = True) -> str:
    meta = canonical["metadata"]
    lines = [
        "## Canonical Article Source (E2-001 · WSJ A1 Investigation)",
        f"- **Title (CN)**: {meta['title_cn']}",
        f"- **Title (EN)**: {meta['title_en']}",
        f"- **Dek (CN)**: {meta['dek_cn']}",
        f"- **Dek (EN)**: {meta['dek_en']}",
        f"- **Byline**: {meta['byline']} ({meta['date_cn']} / {meta['date_en']})",
        "",
        "### Primary Narrative Paragraphs (p1 .. p20)",
    ]
    for b in canonical["blocks"]:
        pid = b["id"]
        lines.append(f"\n#### [{pid}]")
        lines.append(f"- **CN**: {b['text_cn']}")
        lines.append(f"- **EN**: {b['text_en']}")
        if include_sentence_ids and len(b.get("sentences", [])) > 1:
            lines.append("  *Sentence-level sub-anchors (optional, only if you wish to split this paragraph across different visual treatments):*")
            for s in b["sentences"]:
                lines.append(f"  - `[{s['id']}]` CN: {s['text_cn']} | EN: {s['text_en']}")

    lines.append("\n### Verified Quotes Library (for optional pull-quotes / callouts)")
    for q in canonical["derived_quotes"]:
        lines.append(f"- **`[{q['id']}]`** (from `{q['source_block']}`):")
        lines.append(f"  - Quote CN: {q['quote_cn']}")
        lines.append(f"  - Quote EN: {q['quote_en']}")
        lines.append(f"  - Speaker CN: {q['speaker_cn']} ({q['role_cn']})")
        lines.append(f"  - Speaker EN: {q['speaker_en']} ({q['role_en']})")

    lines.append("\n### Verified Metrics Library (for optional data callouts / exhibits)")
    for m in canonical["derived_metrics"]:
        lines.append(
            f"- **`[{m['id']}]`** (from `{m['source_block']}`): value=`{m['value']}` (`{m['value_cn']}`) — {m['label_cn']} / {m['label_en']} ({m['note_cn']} / {m['note_en']})"
        )

    ctx = canonical.get("context_dossier")
    if ctx:
        lines.append("\n### Reporter's Background Context (`[ctx1]`)")
        lines.append(f"- **CN**: {ctx['text_cn']}")
        lines.append(f"- **EN**: {ctx['text_en']}")

    return "\n".join(lines)


def build_group_b_prompt(canonical: dict[str, Any]) -> str:
    source_text = format_canonical_source_for_prompt(canonical, include_sentence_ids=False)
    return f"""{SHARED_EDITORIAL_DIRECTION}

{source_text}

## Output Contract for Group B (Free HTML Mode)
1. Output a complete, self-contained HTML5 document (`<!DOCTYPE html><html lang="zh-CN">...</html>`).
2. Write out the full bilingual text of every paragraph (`p1` through `p20`) directly inside your HTML elements using `<span class="lang-cn">...</span>` and `<span class="lang-en">...</span>`.
3. Add `data-block="p1"` .. `data-block="p20"` on the primary narrative paragraph containers in sequential order (`p1` through `p20`) so the document structure can be inspected, while keeping full freedom over their surrounding containers, classes, and visual treatments.
4. Preserve every paragraph (`p1`..`p20`) verbatim in both Chinese and English—do not omit, truncate, or rewrite any part of any paragraph.
5. Return ONLY the raw HTML document (no markdown fences or commentary outside the HTML).
"""


def build_group_c_prompt(canonical: dict[str, Any]) -> str:
    source_text = format_canonical_source_for_prompt(canonical, include_sentence_ids=True)
    return f"""{SHARED_EDITORIAL_DIRECTION}

{source_text}

## Output Contract for Group C (Source-Referenced HTML Mode)
You have the exact same 100% freedom to design the HTML DOM hierarchy, CSS Grid/Flexbox layouts, asymmetric rails, bespoke inline `<svg>` diagrams, typography, and visual pacing.
However, instead of manually re-typing the long canonical article text into the HTML, you reference canonical content via **Source Anchors** so the deterministic compiler can inject the exact bilingual text:

1. **Primary Narrative Flow (`data-ref`)**:
   - Every paragraph `p1` through `p20` MUST appear in document order (`p1` -> `p2` -> ... -> `p20`) using `data-ref`.
   - **Whole-paragraph anchor (default)**:
     `<p class="prose-p" data-ref="p1"></p>`
     (Leave the element body empty; the compiler injects `<span class="lang-cn">...</span><span class="lang-en">...</span>` automatically!)
   - **Sentence-level split anchor (when you want finer visual expression)**:
     For example, in `p4` or `p20`, if you want the reporter's narrative sentence rendered as normal prose (`p20.s1`) and the speaker's punchline rendered right below it inside a climactic verdict box (`p20.s2`), write:
     ```html
     <p class="prose-p" data-ref="p20.s1"></p>
     <div class="verdict-box">
       <div class="verdict-kicker"><span class="lang-cn">调查终局裁决</span><span class="lang-en">Investigative Verdict</span></div>
       <blockquote class="verdict-quote" data-ref="p20.s2"></blockquote>
     </div>
     ```
     As long as all sentences of `pK` (`pK.s1`, `pK.s2`, ...) are covered in order, the compiler verifies `pK` as 100% complete!
   - **Header & Context anchors**:
     You can also use `data-ref="title"`, `data-ref="dek"`, and `data-ref="ctx1"` (for the background dossier), or style header elements freely.

2. **Exact Inline Text Highlighting (`data-hl`)**:
   - To emphasize key phrases or numbers inside any `data-ref` paragraph without retyping the paragraph, add `data-hl="phrase 1 | phrase 2"`:
     `<p class="prose-p lead-paragraph" data-ref="p1" data-hl="4 万美元 | 无损失风险 | $40,000 | no risk of loss"></p>`
   - The compiler wraps matched phrases in `<mark class="ed-hl">`. Style `mark.ed-hl` in your CSS (e.g., subtle warm highlight or underline).

3. **Derived Visual Callouts (`data-derive`)**:
   - To place a pull-quote (`q1`..`q4`) or a key metric card (`m1`..`m8`) in a sidebar, rail, or callout without duplicating the primary narrative flow:
     - Quote callout:
       ```html
       <blockquote class="pull-quote" data-derive="q1">
         <p class="quote-text" data-field="quote"></p>
         <footer class="quote-attrib" data-field="attribution"></footer>
       </blockquote>
       ```
     - Metric callout:
       ```html
       <div class="metric-card" data-derive="m3">
         <div class="metric-val" data-field="value"></div>
         <div class="metric-lbl" data-field="label"></div>
         <div class="metric-note" data-field="note"></div>
       </div>
       ```
   - You may ALSO create bespoke inline `<svg>` diagrams, comparison bars, and structural flowcharts directly in HTML/SVG!

4. Return ONLY the raw HTML document (`<!DOCTYPE html><html lang="zh-CN">...</html>`), with no markdown fences or outer commentary.
"""
