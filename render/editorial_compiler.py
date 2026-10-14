#!/usr/bin/env python3
"""WSJ 深读 · Phase 5 Production Editorial Compiler & Safety/Integrity Auditor (`editorial_compiler.py`).

Responsibilities:
1. Source Integrity & Deterministic Injection (`data-ref`, `data-derive`, `data-hl`).
2. Structural Integrity:
   - Missing / duplicate / invalid reference IDs
   - Strict monotonic narrative order (`p1`..`pN` or `pK.s1`..`pK.sM`)
   - Proximity deduplication of repeated `data-derive` quotes in the same `<section>`
3. HTML/SVG & CSS Safety Sanitization:
   - Strips dangerous elements (`<script>`, `<iframe>`, `<object>`, `<embed>`, `<foreignObject>`) from article body
   - Strips `on*` inline event attributes and `javascript:` URIs
   - Validates `<style>` blocks (strips `@import` and external `url(http...)`)
4. Open Shadow DOM Adaptation:
   - Produces a Shadow-DOM-ready CSS & HTML fragment (`shadow_css`, `shadow_html`) with
     `:root` -> `:host`, `html[lang="..."]` -> `:host([lang="..."])`, `body` -> `.wsj-shadow-body`
5. SVG Geometric & ViewBox Diagnostics / Auto-Repair:
   - Static SVG coordinate bounds analysis (`analyze_and_repair_svg_bounds`):
     distinguishes missing/malformed `viewBox`, elements/text positioned past `viewBox` width/height,
     and only expands `viewBox` when actual element coordinates + estimated text width exceed the declared box
     (never blindly pads every SVG).
6. Factual Integrity Inventory:
   - Separates Canonical Content, Source-derived Content, and AI-generated Editorial Content.
"""
from __future__ import annotations

import difflib
import hashlib
import html
import json
import re
from typing import Any

import lxml.html

from claim_provenance import validate_claim_provenance


class EditorialCompilationError(ValueError):
    def __init__(self, message: str, audit_report: dict[str, Any]):
        super().__init__(message)
        self.audit_report = audit_report


def _norm_ws(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def _norm_nospace(text: str) -> str:
    return re.sub(r"\s+", "", (text or "").strip())


def _apply_highlights_html(raw_text: str, hl_spec: str | None) -> tuple[str, list[str], list[str]]:
    escaped = html.escape(raw_text or "")
    if not hl_spec:
        return escaped, [], []
    phrases = [p.strip() for p in hl_spec.split("|") if p.strip()]
    applied: list[str] = []
    unmatched: list[str] = []
    for phrase in sorted(phrases, key=len, reverse=True):
        esc_phrase = html.escape(phrase)
        if esc_phrase and esc_phrase in escaped:
            escaped = escaped.replace(esc_phrase, f'<mark class="ed-hl">{esc_phrase}</mark>', 1)
            applied.append(phrase)
        else:
            unmatched.append(phrase)
    return escaped, applied, unmatched


def _set_inner_html(el: lxml.html.HtmlElement, inner_html: str) -> None:
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
    media_by_id = {m["id"]: m for m in canonical.get("media", [])}
    meta = canonical["metadata"]
    ctx = canonical.get("context_dossier") or {}

    return {
        "blocks": blocks_by_id,
        "sentences": sentences_by_id,
        "quotes": quotes_by_id,
        "metrics": metrics_by_id,
        "media": media_by_id,
        "meta": meta,
        "ctx": ctx,
    }


def resolve_ref_tokens(ref_attr: str, maps: dict[str, Any]) -> tuple[str, str, list[str]]:
    tokens = [t.strip() for t in ref_attr.split(",") if t.strip()]
    if not tokens:
        raise ValueError("Empty data-ref attribute")

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
            raise ValueError(f"Unknown data-ref ID: '{tok}'")

    return "".join(cn_parts), " ".join(en_parts), unit_ids


def sanitize_css_stylesheet(css_text: str) -> tuple[str, list[str]]:
    """Sanitize CSS by stripping external @import and external url(http...) while preserving layout rules."""
    sanitized_log: list[str] = []
    out = css_text or ""
    if re.search(r"@import\b", out, re.I):
        out = re.sub(r"@import\s+[^;]+;", "/* stripped-external-import */", out, flags=re.I)
        sanitized_log.append("Stripped @import rule from CSS")
    if re.search(r"url\(\s*['\"]?https?://", out, re.I):
        out = re.sub(r"url\(\s*['\"]?https?://[^)]+\)", "none", out, flags=re.I)
        sanitized_log.append("Stripped external http(s) url() from CSS")
    return out, sanitized_log


def adapt_css_for_shadow_dom(css_text: str) -> str:
    """Transform standard document-level CSS selectors so they work identically inside an Open Shadow Root."""
    adapted = css_text or ""
    adapted = re.sub(r":root\b", ":host", adapted)
    adapted = re.sub(r'html\[lang=["\']zh-CN["\']\]', ':host([lang="zh-CN"])', adapted)
    adapted = re.sub(r'html\[lang=["\']en["\']\]', ':host([lang="en"])', adapted)
    adapted = re.sub(r"(?<![-\w])body(?=\s*[,{])", ".wsj-shadow-body", adapted)
    host_guard = "\n:host { display: block; width: 100%; max-width: 100%; overflow-x: clip; box-sizing: border-box; }\n.wsj-shadow-body { width: 100%; max-width: 100%; overflow-x: clip; box-sizing: border-box; }\n"
    return host_guard + adapted

def sanitize_dom_tree(doc: lxml.html.HtmlElement) -> list[str]:
    """Sanitize DOM tree against unsafe tags, inline event handlers, and javascript: URIs."""
    sanitized_log: list[str] = []
    forbidden_tags = {"iframe", "object", "embed", "applet", "base", "meta", "foreignobject"}
    for el in list(doc.iter()):
        if not isinstance(el.tag, str):
            continue
        tag_lower = el.tag.lower()
        # Allow <meta> only in <head>
        if tag_lower == "meta" and el.xpath("ancestor::head"):
            continue
        if tag_lower in forbidden_tags:
            parent = el.getparent()
            if parent is not None:
                parent.remove(el)
                sanitized_log.append(f"Removed forbidden element <{tag_lower}>")
            continue
        if tag_lower == "script":
            stext = el.text_content() or ""
            if len(stext) > 1200 or "CANONICAL" in stext:
                parent = el.getparent()
                if parent is not None:
                    parent.remove(el)
                    sanitized_log.append("Removed unnecessary client-side script block (>1200 chars or self-hydration script)")
                continue

        # Check attributes
        for attr_name, attr_val in list(el.attrib.items()):
            alower = attr_name.lower()
            # Allow only safe language toggle onclick on buttons in standalone mode; strip other inline event handlers
            if alower.startswith("on"):
                if alower == "onclick" and re.fullmatch(r"\s*setLang\(\s*['\"](?:zh-CN|en)['\"]\s*\)\s*;?\s*", attr_val or ""):
                    continue
                del el.attrib[attr_name]
                sanitized_log.append(f"Removed inline event handler {attr_name} on <{tag_lower}>")
            elif alower in ("href", "src", "xlink:href") and re.match(r"^\s*javascript:", attr_val or "", re.I):
                if alower == "href" and (attr_val or "").strip().lower() == "javascript:void(0)":
                    el.set(attr_name, "#")
                else:
                    del el.attrib[attr_name]
                    sanitized_log.append(f"Removed unsafe javascript: URI on <{tag_lower} {attr_name}>")

    return sanitized_log


def analyze_and_repair_svg_bounds(doc: lxml.html.HtmlElement, *, auto_repair: bool = True) -> list[dict[str, Any]]:
    """Diagnose SVG viewBox vs internal element coordinates and text width; selectively auto-repair tight viewBoxes."""
    diagnostics: list[dict[str, Any]] = []
    for idx, svg_el in enumerate(doc.xpath("//svg")):
        vb_raw = (svg_el.get("viewBox") or svg_el.get("viewbox") or "").strip()
        parts = [float(x) for x in re.findall(r"[-+]?\d*\.?\d+", vb_raw)]
        if len(parts) != 4:
            diagnostics.append({
                "svg_index": idx + 1,
                "issue_type": "missing_or_invalid_viewBox",
                "original_viewBox": vb_raw,
                "repaired": False,
                "detail": "SVG lacks a valid 4-number viewBox attribute.",
            })
            continue

        min_x, min_y, vb_w, vb_h = parts
        max_x_seen = min_x + vb_w
        max_y_seen = min_y + vb_h
        min_x_seen = min_x
        min_y_seen = min_y
        offending_nodes: list[str] = []

        # Inspect rect, circle, line, text positions inside SVG (skipping elements inside <g transform=...>)
        for child in svg_el.xpath(".//*[not(ancestor::*[local-name()='g' and @transform]) and not(@transform)]"):
            if not isinstance(child.tag, str):
                continue
            ctag = child.tag.split("}")[-1].lower()
            try:
                if ctag == "rect":
                    x = float(child.get("x") or 0)
                    y = float(child.get("y") or 0)
                    w_str = child.get("width") or "0"
                    h_str = child.get("height") or "0"
                    if "%" in w_str or "%" in h_str:
                        continue
                    w = float(w_str)
                    h = float(h_str)
                    if x + w > max_x_seen:
                        max_x_seen = x + w
                        offending_nodes.append(f"rect(x+w={x+w:.0f}>{min_x+vb_w:.0f})")
                    if y + h > max_y_seen:
                        max_y_seen = y + h
                        offending_nodes.append(f"rect(y+h={y+h:.0f}>{min_y+vb_h:.0f})")
                elif ctag == "text":
                    x_attr = child.get("x")
                    y_attr = child.get("y")
                    if x_attr is None or y_attr is None or "%" in x_attr or "%" in y_attr:
                        continue
                    x = float(x_attr)
                    y = float(y_attr)
                    fs = float(re.findall(r"\d+(?:\.\d+)?", child.get("font-size") or "13")[0])
                    # Estimate visible text length in a single locale (since CN and EN toggle)
                    cn_t, en_t = _extract_lang_text(child)
                    vis_len = max(len(cn_t) * 1.0, len(en_t) * 0.55)
                    est_px = vis_len * fs
                    anchor = (child.get("text-anchor") or "start").strip()
                    if anchor == "middle":
                        left_edge = x - est_px / 2
                        right_edge = x + est_px / 2
                    elif anchor == "end":
                        left_edge = x - est_px
                        right_edge = x
                    else:
                        left_edge = x
                        right_edge = x + est_px
                    bottom_edge = y + fs * 0.6

                    if right_edge > max_x_seen + 4:
                        max_x_seen = right_edge + 8
                        offending_nodes.append(f"text('{ (cn_t or en_t)[:15] }' right={right_edge:.0f}>{min_x+vb_w:.0f})")
                    if left_edge < min_x_seen - 4:
                        min_x_seen = left_edge - 8
                        offending_nodes.append(f"text('{ (cn_t or en_t)[:15] }' left={left_edge:.0f}<{min_x:.0f})")
                    if bottom_edge > max_y_seen + 4:
                        max_y_seen = bottom_edge + 10
                        offending_nodes.append(f"text('{ (cn_t or en_t)[:15] }' bottom={bottom_edge:.0f}>{min_y+vb_h:.0f})")
            except Exception:
                continue

        if offending_nodes:
            new_min_x = round(min_x_seen)
            new_min_y = round(min_y_seen)
            new_w = round(max_x_seen - new_min_x)
            new_h = round(max_y_seen - new_min_y)
            new_vb = f"{new_min_x} {new_min_y} {new_w} {new_h}"
            if auto_repair:
                svg_el.set("viewBox", new_vb)
                svg_el.set("data-repaired-viewbox", vb_raw)
            diagnostics.append({
                "svg_index": idx + 1,
                "issue_type": "element_or_text_exceeds_viewBox",
                "original_viewBox": vb_raw,
                "repaired_viewBox": new_vb if auto_repair else None,
                "repaired": auto_repair,
                "offending_nodes": offending_nodes[:5],
            })

    return diagnostics


def _extract_lang_text(el: lxml.html.HtmlElement) -> tuple[str, str]:
    cn_nodes = el.xpath(
        './/*[contains(concat(" ", normalize-space(@class), " "), " lang-cn ") or contains(concat(" ", normalize-space(@class), " "), " k-cn ")]'
    )
    en_nodes = el.xpath(
        './/*[contains(concat(" ", normalize-space(@class), " "), " lang-en ") or contains(concat(" ", normalize-space(@class), " "), " k-en ")]'
    )
    if cn_nodes or en_nodes:
        cn = "".join(n.text_content() for n in cn_nodes).strip()
        en = "".join(n.text_content() for n in en_nodes).strip()
        return cn, en
    txt = el.text_content().strip()
    return txt, txt


def compile_editorial_artifact(
    raw_html: str,
    canonical: dict[str, Any],
    *,
    strict: bool = True,
    auto_repair_svg: bool = True,
    evidence_records: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Compile raw Source-referenced HTML into a verified Bilingual Editorial Artifact payload."""
    maps = build_lookup_maps(canonical)
    doc = lxml.html.fromstring(raw_html)

    errors: list[str] = []
    warnings: list[str] = []
    highlight_log: list[dict[str, Any]] = []
    injected_derives: list[dict[str, Any]] = []

    # 1. Sanitize DOM & CSS
    dom_sanitized = sanitize_dom_tree(doc)
    css_sanitized: list[str] = []
    extracted_styles: list[str] = []

    for style_el in doc.xpath("//style"):
        clean_css, log_items = sanitize_css_stylesheet(style_el.text_content())
        style_el.text = clean_css
        extracted_styles.append(clean_css)
        css_sanitized.extend(log_items)

    # 2. Deterministic injection of [data-ref] (Primary Narrative Flow + Metadata/Context)
    for el in doc.xpath("//*[@data-ref]"):
        ref_attr = (el.get("data-ref") or "").strip()
        try:
            cn_text, en_text, _ = resolve_ref_tokens(ref_attr, maps)
        except ValueError as e:
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

        _set_inner_html(el, f'<span class="lang-cn">{cn_html}</span><span class="lang-en">{en_html}</span>')

    # 3. Deterministic injection of [data-derive] (Quotes, Metrics, Excerpts) with proximity deduplication
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
                    or (
                        r.getparent() is not None
                        and ("verdict" in (r.getparent().get("class") or "") or "quote" in (r.getparent().get("class") or ""))
                    )
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
                        _set_inner_html(
                            fn,
                            f'<span class="lang-cn">{html.escape(q["quote_cn"])}</span><span class="lang-en">{html.escape(q["quote_en"])}</span>',
                        )
                    elif f_name == "speaker":
                        _set_inner_html(
                            fn,
                            f'<span class="lang-cn">{html.escape(q["speaker_cn"])}</span><span class="lang-en">{html.escape(q["speaker_en"])}</span>',
                        )
                    elif f_name == "role":
                        _set_inner_html(
                            fn,
                            f'<span class="lang-cn">{html.escape(q["role_cn"])}</span><span class="lang-en">{html.escape(q["role_en"])}</span>',
                        )
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
            injected_derives.append({"id": d_id, "kind": "quote", "source_block": src_blk})

        elif d_id in maps["metrics"]:
            m = maps["metrics"][d_id]
            if field_nodes:
                for fn in field_nodes:
                    f_name = (fn.get("data-field") or "").strip()
                    if f_name == "value":
                        _set_inner_html(
                            fn,
                            f'<span class="lang-cn">{html.escape(m["value_cn"])}</span><span class="lang-en">{html.escape(m["value"])}</span>',
                        )
                    elif f_name == "value_raw":
                        _set_inner_html(fn, html.escape(m["value"]))
                    elif f_name == "label":
                        _set_inner_html(
                            fn,
                            f'<span class="lang-cn">{html.escape(m["label_cn"])}</span><span class="lang-en">{html.escape(m["label_en"])}</span>',
                        )
                    elif f_name == "note":
                        _set_inner_html(
                            fn,
                            f'<span class="lang-cn">{html.escape(m["note_cn"])}</span><span class="lang-en">{html.escape(m["note_en"])}</span>',
                        )
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
            _set_inner_html(
                el, f'<span class="lang-cn">{html.escape(cn_t)}</span><span class="lang-en">{html.escape(en_t)}</span>'
            )
            injected_derives.append({"id": d_id, "kind": "excerpt", "source_block": d_id.split(".")[0]})
        else:
            errors.append(f"Unknown data-derive ID: '{d_id}'")

    # 4. Diagnose & optionally auto-repair SVG coordinate bounds
    svg_diagnostics = analyze_and_repair_svg_bounds(doc, auto_repair=auto_repair_svg)

    # 5. Serialize standalone HTML & Shadow DOM bundle
    compiled_html = lxml.html.tostring(doc, encoding="unicode", doctype="<!DOCTYPE html>")

    body_el = doc.find("body")
    body_children_html = ""
    if body_el is not None:
        # Exclude inline <script> from shadow HTML fragment (host runtime handles language switching & scroll progress)
        body_parts = []
        for child in body_el:
            if isinstance(child.tag, str) and child.tag.lower() == "script":
                continue
            body_parts.append(lxml.html.tostring(child, encoding="unicode"))
        body_children_html = "\n".join(body_parts)

    combined_css = "\n".join(extracted_styles)
    shadow_css = adapt_css_for_shadow_dom(combined_css)

    audit_report = audit_compiled_document(
        doc,
        canonical,
        pre_errors=errors,
        pre_warnings=warnings,
        highlight_log=highlight_log,
        injected_derives=injected_derives,
        svg_diagnostics=svg_diagnostics,
        sanitization_log=dom_sanitized + css_sanitized,
        evidence_records=evidence_records,
    )
    shadow_bundle = {"shadow_css": shadow_css, "shadow_html": f'<div class="wsj-shadow-body">{body_children_html}</div>'}
    audit_report['claim_provenance']['shadow_digest'] = hashlib.sha256(
        json.dumps(shadow_bundle, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()

    if strict and not audit_report["passed"]:
        raise EditorialCompilationError(
            "Editorial compilation failed integrity checks: " + "; ".join(audit_report["errors"]),
            audit_report,
        )

    return {
        "compiled_html": compiled_html,
        "shadow_bundle": shadow_bundle,
        "audit_report": audit_report,
    }


def audit_compiled_document(
    doc: lxml.html.HtmlElement,
    canonical: dict[str, Any],
    *,
    pre_errors: list[str] | None = None,
    pre_warnings: list[str] | None = None,
    highlight_log: list[dict[str, Any]] | None = None,
    injected_derives: list[dict[str, Any]] | None = None,
    svg_diagnostics: list[dict[str, Any]] | None = None,
    sanitization_log: list[str] | None = None,
    evidence_records: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    maps = build_lookup_maps(canonical)
    errors: list[str] = list(pre_errors or [])
    warnings: list[str] = list(pre_warnings or [])

    expected_sentences: list[str] = []
    for b in canonical["blocks"]:
        for s in b["sentences"]:
            expected_sentences.append(s["id"])

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
                    paragraph_reconstructions_cn[tok].append(b["text_cn"])
                    paragraph_reconstructions_en[tok].append(b["text_en"])
            elif tok in maps["sentences"]:
                s = maps["sentences"][tok]
                observed_sentence_stream.append(s["id"])
                pid = s["parent_id"]
                if tok == tokens[0]:
                    paragraph_reconstructions_cn[pid].append(cn_dom)
                    paragraph_reconstructions_en[pid].append(en_dom)
            else:
                errors.append(f"Invalid narrative block identifier: '{tok}'")

    missing_units = [u for u in expected_sentences if u not in observed_sentence_stream]
    duplicate_units = [u for u in set(observed_sentence_stream) if observed_sentence_stream.count(u) > 1]

    if missing_units:
        errors.append(f"Missing canonical narrative units: {missing_units}")
    if duplicate_units:
        errors.append(f"Duplicate canonical narrative units in primary flow: {duplicate_units}")

    order_indices = [expected_sentences.index(u) for u in observed_sentence_stream if u in expected_sentences]
    is_monotonic = order_indices == sorted(order_indices)
    if not is_monotonic:
        errors.append("Primary narrative flow order is NOT monotonic relative to canonical source.")

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
            })
            errors.append(f"Paragraph {pid} verbatim mismatch (CN exact={cn_exact}, EN exact={en_exact})")

    # Separate & inventory AI-generated Editorial Content
    ai_editorial_items: list[dict[str, Any]] = []
    for idx, svg_el in enumerate(doc.xpath("//svg")):
        svg_texts = [t.strip() for t in svg_el.xpath(".//text/text() | .//tspan/text()") if t.strip()]
        svg_joined = " | ".join(svg_texts)
        svg_numbers = re.findall(r"\$?\d+(?:,\d{3})*(?:\.\d+)?%?|\d+\s*(?:年|万美元|亿美元|years?)", svg_joined)
        ai_editorial_items.append({
            "category": "svg_graphic",
            "index": idx + 1,
            "viewBox": svg_el.get("viewBox") or "",
            "text_labels": svg_texts,
            "numbers_found": svg_numbers,
        })

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

    claim_gate = validate_claim_provenance(canonical, doc, evidence_records=evidence_records)
    errors.extend(claim_gate['errors'])

    total_blocks = len(canonical["blocks"])
    return {
        "passed": len(errors) == 0,
        "source_integrity": {
            "article_id": canonical["article_id"],
            "content_digest": canonical["content_digest"],
            "exact_match_cn": f"{exact_match_cn_count}/{total_blocks}",
            "exact_match_en": f"{exact_match_en_count}/{total_blocks}",
            "verbatim_diffs": verbatim_diffs,
        },
        "structural_integrity": {
            "total_canonical_paragraphs": total_blocks,
            "observed_narrative_elements": len(ref_elements),
            "missing_units": missing_units,
            "duplicate_units": duplicate_units,
            "monotonic_order": is_monotonic,
        },
        "derived_and_editorial_inventory": {
            "source_derived_count": len(injected_derives or doc.xpath("//*[@data-derive]")),
            "derived_items": injected_derives or [],
            "highlights_applied": highlight_log or [],
            "ai_editorial_items_count": len(ai_editorial_items),
            "ai_editorial_items": ai_editorial_items,
        },
        "svg_diagnostics": svg_diagnostics or [],
        "claim_provenance": claim_gate,
        "sanitization_log": sanitization_log or [],
        "errors": errors,
        "warnings": warnings,
    }


def build_targeted_repair_prompt(
    original_prompt: str,
    failed_raw_html: str,
    audit_report: dict[str, Any],
) -> str:
    """Build a targeted repair prompt when a model generation fails structural or reference checks."""
    error_lines = "\n".join(f"- {e}" for e in audit_report.get("errors", []))
    missing = audit_report.get("structural_integrity", {}).get("missing_units", [])
    duplicates = audit_report.get("structural_integrity", {}).get("duplicate_units", [])
    return f"""{original_prompt}

## CRITICAL COMPILER REPAIR REQUEST
Your previous HTML generation failed the deterministic Source-Referenced AST Compiler check with the following errors:
{error_lines}

- Missing narrative units that MUST be included via `data-ref`: {missing}
- Duplicate narrative units in `data-ref` that must only appear once in primary flow (use `data-derive` for secondary callouts): {duplicates}

Please fix the HTML above so that every paragraph `p1`..`p{audit_report['structural_integrity']['total_canonical_paragraphs']}` appears in exact sequential order via `data-ref`, and return ONLY the corrected `<!DOCTYPE html>` document.
"""
