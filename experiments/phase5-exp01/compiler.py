#!/usr/bin/env python3
"""Phase 5 — Experiment 01: Source-referenced Editorial HTML Compiler & Integrity Auditor.

Uses `lxml.html` (libxml2 HTML AST) to perform:
1. Deterministic content injection for:
   - `data-ref`: Primary Narrative Flow (`title`, `dek`, `byline`, `p1`..`p20`, or sentence refs `p1.s1`..`p20.s2`, `ctx1`)
   - `data-derive`: Source-derived Visual Callouts (`q1`..`q4`, `m1`..`m8`, or repeated sentence/block refs)
   - `data-hl`: Exact substring highlighting (`<mark class="ed-hl">`) inside injected canonical text
2. Primary narrative flow completeness & strict monotonicity verification (`p1`..`p20`).
3. Reference ID validity check (loud failure on unknown IDs).
4. Character-by-character verbatim diff of rendered primary narrative blocks against `CanonicalSource`.
5. Separation & audit of:
   - Canonical Content (primary flow `data-ref`)
   - Source-derived Content (`data-derive`)
   - AI-generated Editorial Content (chapter headings, exhibit labels, SVG text, callout notes)
"""
from __future__ import annotations

import argparse
import difflib
import html
import json
import os
import re
from typing import Any

import lxml.html
from lxml import etree


class CompilerError(ValueError):
    pass


def _norm_ws(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def _norm_nospace(text: str) -> str:
    return re.sub(r"\s+", "", (text or "").strip())


def _apply_highlights_html(raw_text: str, hl_spec: str | None) -> tuple[str, list[str], list[str]]:
    """Escape raw_text and wrap exact matched substrings from `hl_spec` in `<mark class="ed-hl">`."""
    escaped = html.escape(raw_text or "")
    if not hl_spec:
        return escaped, [], []
    phrases = [p.strip() for p in hl_spec.split("|") if p.strip()]
    applied: list[str] = []
    unmatched: list[str] = []
    # Sort longer phrases first to avoid partial overlap issues
    for phrase in sorted(phrases, key=len, reverse=True):
        esc_phrase = html.escape(phrase)
        if esc_phrase and esc_phrase in escaped:
            escaped = escaped.replace(esc_phrase, f'<mark class="ed-hl">{esc_phrase}</mark>', 1)
            applied.append(phrase)
        else:
            unmatched.append(phrase)
    return escaped, applied, unmatched


def _set_inner_html(el: lxml.html.HtmlElement, inner_html: str) -> None:
    """Replace all children/text of `el` with parsed HTML fragments."""
    for child in list(el):
        el.remove(child)
    el.text = None
    if not inner_html:
        return
    fragments = lxml.html.fragments_fromstring(inner_html)
    for idx, frag in enumerate(fragments):
        if isinstance(frag, str):
            if idx == 0:
                el.text = (el.text or "") + frag
            else:
                el[-1].tail = (el[-1].tail or "") + frag
        else:
            el.append(frag)


def build_lookup_maps(canonical: dict[str, Any]) -> dict[str, Any]:
    blocks_by_id: dict[str, dict[str, Any]] = {}
    sentences_by_id: dict[str, dict[str, Any]] = {}
    for b in canonical["blocks"]:
        blocks_by_id[b["id"]] = b
        for s in b.get("sentences", []):
            sentences_by_id[s["id"]] = {**s, "parent_id": b["id"], "parent_index": b["index"]}

    quotes_by_id = {q["id"]: q for q in canonical.get("derived_quotes", [])}
    metrics_by_id = {m["id"]: m for m in canonical.get("derived_metrics", [])}
    meta = canonical["metadata"]
    ctx = canonical.get("context_dossier") or {}

    return {
        "blocks": blocks_by_id,
        "sentences": sentences_by_id,
        "quotes": quotes_by_id,
        "metrics": metrics_by_id,
        "meta": meta,
        "ctx": ctx,
    }


def resolve_ref_tokens(ref_attr: str, maps: dict[str, Any]) -> tuple[str, str, list[str]]:
    """Resolve comma-separated ref tokens (e.g. 'p1' or 'p1.s1,p1.s2' or 'title') into (cn_text, en_text, resolved_unit_ids)."""
    tokens = [t.strip() for t in ref_attr.split(",") if t.strip()]
    if not tokens:
        raise CompilerError("Empty data-ref attribute")

    cn_parts: list[str] = []
    en_parts: list[str] = []
    unit_ids: list[str] = []

    meta = maps["meta"]
    ctx = maps["ctx"]

    for tok in tokens:
        if tok == "title":
            cn_parts.append(meta["title_cn"])
            en_parts.append(meta["title_en"])
            unit_ids.append("meta:title")
        elif tok == "dek":
            cn_parts.append(meta["dek_cn"])
            en_parts.append(meta["dek_en"])
            unit_ids.append("meta:dek")
        elif tok == "byline":
            cn_parts.append(meta["byline"])
            en_parts.append(meta["byline"])
            unit_ids.append("meta:byline")
        elif tok == "kicker":
            cn_parts.append(meta["kicker_cn"])
            en_parts.append(meta["kicker_en"])
            unit_ids.append("meta:kicker")
        elif tok in ("ctx1", "context"):
            cn_parts.append(ctx.get("text_cn", ""))
            en_parts.append(ctx.get("text_en", ""))
            unit_ids.append("ctx1")
        elif tok in maps["blocks"]:
            b = maps["blocks"][tok]
            cn_parts.append(b["text_cn"])
            en_parts.append(b["text_en"])
            for s in b["sentences"]:
                unit_ids.append(s["id"])
        elif tok in maps["sentences"]:
            s = maps["sentences"][tok]
            cn_parts.append(s["text_cn"])
            en_parts.append(s["text_en"])
            unit_ids.append(s["id"])
        else:
            raise CompilerError(f"Unknown data-ref ID: '{tok}'")

    return "".join(cn_parts), " ".join(en_parts), unit_ids


def compile_and_inject(raw_html: str, canonical: dict[str, Any], *, strict: bool = True) -> tuple[str, dict[str, Any]]:
    """Compile a Source-referenced HTML document by deterministically injecting Canonical Content and auditing."""
    maps = build_lookup_maps(canonical)
    doc = lxml.html.fromstring(raw_html)

    injected_refs: list[dict[str, Any]] = []
    injected_derives: list[dict[str, Any]] = []
    highlight_log: list[dict[str, Any]] = []
    errors: list[str] = []

    # 1. Process all [data-ref] elements (Primary Narrative Flow & Metadata/Context)
    for el in doc.xpath("//*[@data-ref]"):
        ref_attr = (el.get("data-ref") or "").strip()
        try:
            cn_text, en_text, unit_ids = resolve_ref_tokens(ref_attr, maps)
        except CompilerError as e:
            errors.append(str(e))
            continue

        hl_cn_spec = el.get("data-hl-cn") or el.get("data-hl")
        hl_en_spec = el.get("data-hl-en") or el.get("data-hl")

        cn_html, app_cn, unm_cn = _apply_highlights_html(cn_text, hl_cn_spec)
        en_html, app_en, unm_en = _apply_highlights_html(en_text, hl_en_spec)

        if hl_cn_spec or hl_en_spec:
            highlight_log.append({
                "ref": ref_attr,
                "applied_cn": app_cn,
                "applied_en": app_en,
                "ignored_unmatched": [u for u in (unm_cn + unm_en) if u not in (app_cn + app_en)],
            })

        bilingual_markup = f'<span class="lang-cn">{cn_html}</span><span class="lang-en">{en_html}</span>'
        _set_inner_html(el, bilingual_markup)

        injected_refs.append({
            "ref": ref_attr,
            "tag": el.tag,
            "unit_ids": unit_ids,
            "cn_text": cn_text,
            "en_text": en_text,
        })

    # 2. Process all [data-derive] elements (Source-derived Quotes, Metrics, or Repeated Excerpts)
    for el in doc.xpath("//*[@data-derive]"):
        d_id = (el.get("data-derive") or "").strip()
        field_nodes = el.xpath(".//*[@data-field]")

        if d_id in maps["quotes"]:
            q = maps["quotes"][d_id]
            src_blk = q["source_block"]
            section_anc = el.xpath("ancestor::section[1]")
            if section_anc:
                sec = section_anc[0]
                same_sec_refs = sec.xpath(f'.//*[@data-ref="{src_blk}" or starts-with(@data-ref, "{src_blk}.")]')
                if any(
                    r.tag == "blockquote"
                    or "verdict" in (r.get("class") or "")
                    or "quote" in (r.get("class") or "")
                    or (r.getparent() is not None and ("verdict" in (r.getparent().get("class") or "") or "quote" in (r.getparent().get("class") or "")))
                    for r in same_sec_refs
                ):
                    parent = el.getparent()
                    if parent is not None:
                        parent.remove(el)
                    injected_derives.append({"id": d_id, "kind": "quote_deduped_removed", "source_block": src_blk})
                    continue
            if field_nodes:
                for fn in field_nodes:
                    f_name = (fn.get("data-field") or "").strip()
                    if f_name == "quote":
                        _set_inner_html(fn, f'<span class="lang-cn">{html.escape(q["quote_cn"])}</span><span class="lang-en">{html.escape(q["quote_en"])}</span>')
                    elif f_name == "speaker":
                        _set_inner_html(fn, f'<span class="lang-cn">{html.escape(q["speaker_cn"])}</span><span class="lang-en">{html.escape(q["speaker_en"])}</span>')
                    elif f_name == "role":
                        _set_inner_html(fn, f'<span class="lang-cn">{html.escape(q["role_cn"])}</span><span class="lang-en">{html.escape(q["role_en"])}</span>')
                    elif f_name == "attribution":
                        _set_inner_html(
                            fn,
                            f'<span class="lang-cn">— {html.escape(q["speaker_cn"])} · {html.escape(q["role_cn"])}</span>'
                            f'<span class="lang-en">— {html.escape(q["speaker_en"])}, {html.escape(q["role_en"])}</span>',
                        )
                    else:
                        errors.append(f"Unknown data-field '{f_name}' on quote '{d_id}'")
            else:
                _set_inner_html(
                    el,
                    f'<p class="quote-text"><span class="lang-cn">{html.escape(q["quote_cn"])}</span><span class="lang-en">{html.escape(q["quote_en"])}</span></p>'
                    f'<div class="quote-attrib"><span class="lang-cn">— {html.escape(q["speaker_cn"])} · {html.escape(q["role_cn"])}</span>'
                    f'<span class="lang-en">— {html.escape(q["speaker_en"])}, {html.escape(q["role_en"])}</span></div>',
                )
            injected_derives.append({"id": d_id, "kind": "quote", "source_block": q["source_block"]})

        elif d_id in maps["metrics"]:
            m = maps["metrics"][d_id]
            if field_nodes:
                for fn in field_nodes:
                    f_name = (fn.get("data-field") or "").strip()
                    if f_name == "value":
                        _set_inner_html(fn, f'<span class="lang-cn">{html.escape(m["value_cn"])}</span><span class="lang-en">{html.escape(m["value"])}</span>')
                    elif f_name == "value_raw":
                        _set_inner_html(fn, html.escape(m["value"]))
                    elif f_name == "label":
                        _set_inner_html(fn, f'<span class="lang-cn">{html.escape(m["label_cn"])}</span><span class="lang-en">{html.escape(m["label_en"])}</span>')
                    elif f_name == "note":
                        _set_inner_html(fn, f'<span class="lang-cn">{html.escape(m["note_cn"])}</span><span class="lang-en">{html.escape(m["note_en"])}</span>')
                    else:
                        errors.append(f"Unknown data-field '{f_name}' on metric '{d_id}'")
            else:
                _set_inner_html(
                    el,
                    f'<div class="metric-val"><span class="lang-cn">{html.escape(m["value_cn"])}</span><span class="lang-en">{html.escape(m["value"])}</span></div>'
                    f'<div class="metric-lbl"><span class="lang-cn">{html.escape(m["label_cn"])}</span><span class="lang-en">{html.escape(m["label_en"])}</span></div>'
                    f'<div class="metric-note"><span class="lang-cn">{html.escape(m["note_cn"])}</span><span class="lang-en">{html.escape(m["note_en"])}</span></div>',
                )
            injected_derives.append({"id": d_id, "kind": "metric", "source_block": m["source_block"]})

        elif d_id in maps["blocks"] or d_id in maps["sentences"]:
            cn_t, en_t, _ = resolve_ref_tokens(d_id, maps)
            _set_inner_html(el, f'<span class="lang-cn">{html.escape(cn_t)}</span><span class="lang-en">{html.escape(en_t)}</span>')
            injected_derives.append({"id": d_id, "kind": "excerpt", "source_block": d_id.split(".")[0]})
        else:
            errors.append(f"Unknown data-derive ID: '{d_id}'")

    compiled_html = lxml.html.tostring(doc, encoding="unicode", doctype="<!DOCTYPE html>")
    audit_report = audit_rendered_html(compiled_html, canonical, mode="source-referenced", pre_errors=errors, highlight_log=highlight_log, injected_derives=injected_derives)

    if strict and not audit_report["passed"]:
        raise CompilerError("Compilation failed integrity audit:\n" + json.dumps(audit_report["errors"], ensure_ascii=False, indent=2))

    return compiled_html, audit_report


def _extract_lang_text(el: lxml.html.HtmlElement) -> tuple[str, str]:
    """Extract concatenated text inside .lang-cn / .k-cn and .lang-en / .k-en, or fallback to plain text."""
    cn_nodes = el.xpath('.//*[contains(concat(" ", normalize-space(@class), " "), " lang-cn ") or contains(concat(" ", normalize-space(@class), " "), " k-cn ")]')
    en_nodes = el.xpath('.//*[contains(concat(" ", normalize-space(@class), " "), " lang-en ") or contains(concat(" ", normalize-space(@class), " "), " k-en ")]')
    if cn_nodes or en_nodes:
        cn = "".join(n.text_content() for n in cn_nodes).strip()
        en = "".join(n.text_content() for n in en_nodes).strip()
        return cn, en
    txt = el.text_content().strip()
    return txt, txt


def audit_rendered_html(
    rendered_html: str,
    canonical: dict[str, Any],
    *,
    mode: str = "auto",
    pre_errors: list[str] | None = None,
    highlight_log: list[dict[str, Any]] | None = None,
    injected_derives: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Audit any rendered HTML (Golden Baseline, Free HTML Group B, or Compiled Source-Referenced Group C) against CanonicalSource."""
    maps = build_lookup_maps(canonical)
    doc = lxml.html.fromstring(rendered_html)
    errors: list[str] = list(pre_errors or [])
    warnings: list[str] = []

    # Expected sentence stream in exact order
    expected_sentences: list[str] = []
    for b in canonical["blocks"]:
        for s in b["sentences"]:
            expected_sentences.append(s["id"])

    # Locate primary narrative blocks: either [data-ref] or [data-block]
    ref_elements = doc.xpath("//*[@data-ref or @data-block]")

    observed_sentence_stream: list[str] = []
    paragraph_reconstructions_cn: dict[str, list[str]] = {b["id"]: [] for b in canonical["blocks"]}
    paragraph_reconstructions_en: dict[str, list[str]] = {b["id"]: [] for b in canonical["blocks"]}

    for el in ref_elements:
        attr_val = (el.get("data-ref") or el.get("data-block") or "").strip()
        cn_dom, en_dom = _extract_lang_text(el)
        tokens = [t.strip() for t in attr_val.split(",") if t.strip()]
        for tok in tokens:
            if tok in ("title", "dek", "byline", "kicker", "ctx1", "context"):
                continue
            if tok in maps["blocks"]:
                b = maps["blocks"][tok]
                for s in b["sentences"]:
                    observed_sentence_stream.append(s["id"])
                if len(tokens) == 1:
                    paragraph_reconstructions_cn[tok].append(cn_dom)
                    paragraph_reconstructions_en[tok].append(en_dom)
                else:
                    # Multi-block token rare case
                    paragraph_reconstructions_cn[tok].append(b["text_cn"])
                    paragraph_reconstructions_en[tok].append(b["text_en"])
            elif tok in maps["sentences"]:
                s = maps["sentences"][tok]
                observed_sentence_stream.append(s["id"])
                pid = s["parent_id"]
                if len(tokens) == 1:
                    paragraph_reconstructions_cn[pid].append(cn_dom)
                    paragraph_reconstructions_en[pid].append(en_dom)
                else:
                    # If multiple sentences are combined in one element (e.g. data-ref="p1.s1,p1.s2"), record on the first token
                    if tok == tokens[0]:
                        paragraph_reconstructions_cn[pid].append(cn_dom)
                        paragraph_reconstructions_en[pid].append(en_dom)
            else:
                errors.append(f"Invalid narrative block identifier: '{tok}'")

    # Check completeness & ordering of the 20 paragraphs (via sentence stream)
    missing_units = [u for u in expected_sentences if u not in observed_sentence_stream]
    duplicate_units = [u for u in set(observed_sentence_stream) if observed_sentence_stream.count(u) > 1]

    if missing_units:
        errors.append(f"Missing canonical narrative units: {missing_units}")
    if duplicate_units:
        errors.append(f"Duplicate canonical narrative units in primary flow: {duplicate_units}")

    # Check monotonic order
    order_indices = [expected_sentences.index(u) for u in observed_sentence_stream if u in expected_sentences]
    is_monotonic = order_indices == sorted(order_indices)
    if not is_monotonic:
        errors.append("Primary narrative flow order is NOT monotonic relative to canonical source.")

    # Verbatim character-by-character comparison for each paragraph p1..p20
    verbatim_diffs: list[dict[str, Any]] = []
    exact_match_cn_count = 0
    exact_match_en_count = 0

    for b in canonical["blocks"]:
        pid = b["id"]
        exp_cn = b["text_cn"]
        exp_en = b["text_en"]
        act_cn = "".join(paragraph_reconstructions_cn.get(pid, []))
        act_en = " ".join(paragraph_reconstructions_en.get(pid, []))

        cn_exact = _norm_nospace(act_cn) == _norm_nospace(exp_cn)
        en_exact = _norm_ws(act_en) == _norm_ws(exp_en)

        if cn_exact:
            exact_match_cn_count += 1
        if en_exact:
            exact_match_en_count += 1

        if not cn_exact or not en_exact:
            cn_ratio = difflib.SequenceMatcher(None, _norm_nospace(exp_cn), _norm_nospace(act_cn)).ratio()
            en_ratio = difflib.SequenceMatcher(None, _norm_ws(exp_en), _norm_ws(act_en)).ratio()
            verbatim_diffs.append({
                "paragraph_id": pid,
                "cn_exact": cn_exact,
                "en_exact": en_exact,
                "cn_similarity": round(cn_ratio, 4),
                "en_similarity": round(en_ratio, 4),
                "expected_cn": exp_cn,
                "actual_cn": act_cn,
                "expected_en": exp_en,
                "actual_en": act_en,
            })
            if mode == "source-referenced":
                errors.append(f"Paragraph {pid} verbatim mismatch (CN exact={cn_exact}, EN exact={en_exact})")

    # Separate & inventory 3 categories of content in the DOM:
    # 1. Canonical Content ([data-ref] / [data-block])
    # 2. Source-derived Content ([data-derive])
    # 3. AI-generated Editorial Content (headings, exhibit cards without data-derive, SVG text nodes, captions)
    ai_editorial_items: list[dict[str, Any]] = []

    # Collect SVG text nodes
    for idx, svg_el in enumerate(doc.xpath("//svg")):
        svg_texts = [t.strip() for t in svg_el.xpath(".//text/text() | .//tspan/text()") if t.strip()]
        svg_joined = " | ".join(svg_texts)
        svg_numbers = re.findall(r"\$?\d+(?:,\d{3})*(?:\.\d+)?%?|\d+\s*(?:年|万美元|亿美元|years?)", svg_joined)
        ai_editorial_items.append({
            "category": "svg_graphic",
            "index": idx + 1,
            "aria_label": svg_el.get("aria-label") or "",
            "viewBox": svg_el.get("viewBox") or "",
            "text_labels": svg_texts,
            "numbers_found": svg_numbers,
        })

    # Collect section headings & exhibit titles that are not [data-ref] or [data-derive]
    for h_el in doc.xpath("//main//h2 | //main//h3 | //main//h4 | //main//figcaption"):
        if h_el.xpath("ancestor-or-self::*[@data-ref or @data-derive or @data-block]"):
            continue
        cn_t, en_t = _extract_lang_text(h_el)
        if cn_t or en_t:
            ai_editorial_items.append({
                "category": f"editorial_{h_el.tag}",
                "cn": cn_t,
                "en": en_t,
                "numbers_found": re.findall(r"\$?\d+(?:,\d{3})*(?:\.\d+)?%?", f"{cn_t} {en_t}"),
            })

    # Check numbers in AI-generated editorial items against source text numbers
    full_source_corpus = (
        canonical["metadata"]["title_cn"]
        + " "
        + canonical["metadata"]["title_en"]
        + " "
        + " ".join(b["text_cn"] + " " + b["text_en"] for b in canonical["blocks"])
        + " "
        + canonical.get("context_dossier", {}).get("text_cn", "")
    )
    source_numbers = set(re.findall(r"\d+(?:\.\d+)?", full_source_corpus.replace(",", "")))
    # Add structural/ordinal numbers (1, 2, 3, 4, I, II, III, IV, 6 min, 2026, 100%)
    allowed_structural_numbers = {"1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "100", "2026"}
    unverified_editorial_numbers: list[dict[str, Any]] = []

    for item in ai_editorial_items:
        for raw_num in item.get("numbers_found", []):
            clean_digits = re.findall(r"\d+(?:\.\d+)?", raw_num.replace(",", ""))
            for d in clean_digits:
                if d not in source_numbers and d not in allowed_structural_numbers:
                    unverified_editorial_numbers.append({
                        "item": item["category"],
                        "number": raw_num,
                        "context": item.get("cn") or " ".join(item.get("text_labels", [])[:5]),
                    })

    if unverified_editorial_numbers:
        warnings.append(f"Found {len(unverified_editorial_numbers)} numeric tokens in AI-generated editorial labels/SVGs requiring human review.")

    total_blocks = len(canonical["blocks"])
    return {
        "mode": mode,
        "passed": len(errors) == 0,
        "total_canonical_paragraphs": total_blocks,
        "observed_narrative_elements": len(ref_elements),
        "missing_units": missing_units,
        "duplicate_units": duplicate_units,
        "monotonic_order": is_monotonic,
        "exact_match_cn": f"{exact_match_cn_count}/{total_blocks}",
        "exact_match_en": f"{exact_match_en_count}/{total_blocks}",
        "verbatim_diffs": verbatim_diffs,
        "content_breakdown": {
            "canonical_ref_count": len(ref_elements),
            "source_derived_count": len(injected_derives or doc.xpath("//*[@data-derive]")),
            "highlights_applied": highlight_log or [],
            "ai_editorial_items_count": len(ai_editorial_items),
            "ai_editorial_items": ai_editorial_items,
            "unverified_editorial_numbers": unverified_editorial_numbers,
        },
        "errors": errors,
        "warnings": warnings,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compile and/or audit WSJ Editorial HTML against CanonicalSource.")
    parser.add_argument("--canonical", required=True, help="Path to canonical JSON")
    parser.add_argument("--input", required=True, help="Path to input HTML")
    parser.add_argument("--output", help="Path to write compiled HTML (for source-referenced mode)")
    parser.add_argument("--report", help="Path to write JSON audit report")
    parser.add_argument("--mode", choices=["compile", "audit-only"], default="compile")
    args = parser.parse_args()

    with open(args.canonical, encoding="utf-8") as f:
        canonical_data = json.load(f)
    with open(args.input, encoding="utf-8") as f:
        input_html = f.read()

    if args.mode == "compile":
        compiled, report = compile_and_inject(input_html, canonical_data, strict=False)
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(compiled)
    else:
        report = audit_rendered_html(input_html, canonical_data, mode="audit-only")

    if args.report:
        with open(args.report, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

    print(json.dumps({
        "mode": args.mode,
        "passed": report["passed"],
        "exact_match_cn": report["exact_match_cn"],
        "exact_match_en": report["exact_match_en"],
        "missing_units": report["missing_units"],
        "monotonic_order": report["monotonic_order"],
        "diff_count": len(report["verbatim_diffs"]),
        "errors": report["errors"],
        "warnings": report["warnings"],
    }, ensure_ascii=False, indent=2))
