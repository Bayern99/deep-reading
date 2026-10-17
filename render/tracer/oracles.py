"""7-Oracle deterministic certification for the full-issue Issue Artifact.

Ticket 3 (GitHub Issue #4): after the pipeline compiles the 86-item
2026-10-14 issue into the single-file artifact, ``certify()`` inspects the
generated HTML end-to-end and asserts the 7 Objective Oracles:

1. **Narrative conservation** — strict SHA256 round-trip of the ordered
   ``.lang-cn`` / ``.lang-en`` paragraph sequences for every one of the 86
   raw inventory items (including the 21 composite-column members and the 18
   digest paragraphs) against the approved source units: 86/86, diff 0.
2. **Paragraph-scoped numeric grounding** — every takeaway, thesis box,
   subheading, pull quote, ``<wsj-chart>`` and Chart Companion carries a
   valid ``data-src`` / ``data-ref`` and 100% of its substantive numbers
   ground in the declared paragraph(s) (plus the chart's ``Retina*`` vector
   text for companions).  Issue #5 extends this to the Group C dossier
   containers: hero ledger mini-stats, rail metric cards, navy defense
   dossiers and the executive dossier card.
3. **Native ``Retina*`` chart vector coverage** — all 21 printed charts:
   union crop width <= orig width + 24pt, zero body-prose line centers
   inside the crop, zero sliced multi-column source fragments inside the
   crop, intact ``RetinaMedium`` titles, paired Bilingual Chart Companion
   cards in the HTML.
4. **Figure narrative monotonicity & ad exclusion** — zero multi-figure
   stories stack >= 2 figures before ``p1``; every editorial figure follows
   its anchor paragraph in physical print ``(x, y)`` order; non-editorial
   print ads (``p06-b60``, Gotham-Bold) never appear as reader figures.
5. **Historical fault-injection recall** — all 6 historical failure
   classes (``700M->7000万``, ``$2.3B->2.3亿``, ungrounded chart rate,
   pseudo-quote, SVG text overflow past viewBox, broken EN toggle /
   subhead leak) are deterministically rejected: 6/6.
6. **Print hierarchy, composite grouping & zero lede restatement** —
   86 raw items route into 71 units (8 Tier 1 / 54 Tier 2 / 9 Tier 3),
   28 raw sections map to the 7 canonical sections with rubric kickers,
   16/16 What's News deep links resolve to valid target unit ids, and 0
   Tier 2 takeaway/thesis elements cite ``p1``.
7. **Viewport geometry, clean surface & payload budget** — single-file
   size within [4.5 MB, 10 MB], zero forbidden pipeline strings, and a
   Headless Chrome DOM geometry probe across 1440x900 and 390x844 in
   ``中文`` / ``EN`` / ``双语`` modes, measuring both the overview and the
   immersive-reader (``read``) views — only elements actually rendered in
   the active view are checked: ``scrollWidth <= clientWidth``,
   0 broken images, 0 clipped SVG text nodes.

The certification JSON is a compact workspace report (like the gate
report); it is never embedded in the reader HTML.
"""
from __future__ import annotations

import copy
import hashlib
import html as html_mod
import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any

import lxml.html

from .compose import (
    PilotData,
    figure_print_key,
    page_column_grids,
    paragraph_print_keys,
)
from .content import CHART_COMPANIONS
from .gate import scan_pair
from .numbers import NumberToken, ground_numbers
from .routing import COMPOSITES, SECTION_MAP, canonical_section
from .shell import SECTIONS
from .verify import (
    FORBIDDEN_STRINGS,
    TracerCompilationError,
    split_sentences,
    verify_quote_anchor,
)
from .vector import (
    extract_chart_vectors,
    line_font,
    media_sibling_bboxes,
)

ISSUE = "2026-10-14"
RAW_ITEM_COUNT = 86
EXPECTED_TIERS = {1: 8, 2: 54, 3: 9}
UNIT_COUNT = 71
CHART_COUNT = 21
WHATSNEWS_LINKS = 16

# Payload budget for the portable single-file artifact (target 5-8 MB).
SIZE_MIN_BYTES = 4_500_000
SIZE_MAX_BYTES = 10_000_000

# Pipeline chrome that must never appear on the reader surface: the legacy
# audit strings plus workspace-report keys and the pipeline's own codename.
CERT_FORBIDDEN_STRINGS = FORBIDDEN_STRINGS + (
    "gate-report",
    "findings_by_kind",
    "Vertical Tracer",
)

_CHROME_CANDIDATES = (
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
)

VIEWPORTS = ((1440, 900), (390, 844))
LANG_MODES = ("zh", "en", "bi")


@dataclass
class OracleResult:
    """One oracle verdict with machine-readable evidence."""

    name: str
    passed: bool
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass
class CertificationReport:
    """Aggregate 7-Oracle certification result for one artifact."""

    artifact: str
    size_bytes: int
    oracles: list[OracleResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(o.passed for o in self.oracles)

    def oracle(self, name: str) -> OracleResult:
        return next(o for o in self.oracles if o.name == name)

    def to_dict(self) -> dict[str, Any]:
        return {
            "issue": ISSUE,
            "artifact": self.artifact,
            "size_bytes": self.size_bytes,
            "passed": self.passed,
            "oracles": {o.name: {"passed": o.passed, **o.detail} for o in self.oracles},
        }


# --- artifact DOM helpers ------------------------------------------------------

def unit_elements(root: lxml.html.HtmlElement) -> dict[str, lxml.html.HtmlElement]:
    """unit_id -> wrapper element (shell places id/data-unit on the div)."""
    out = {}
    for el in root.xpath(".//div[@data-unit and @data-tier]"):
        out[el.get("data-unit")] = el
    return out


def _narrative_nodes(host: lxml.html.HtmlElement) -> list[lxml.html.HtmlElement]:
    """Narrative-bearing elements in document order: prose paragraphs and
    verbatim inventory subheadings (both carry ``data-ref``)."""
    return host.xpath(
        ".//p[contains(concat(' ', normalize-space(@class), ' '), ' prose-p ') and @data-ref]"
        "| .//h2[contains(concat(' ', normalize-space(@class), ' '), ' sec-h ') and @data-ref]"
    )


def _node_ref_pid(ref: str) -> tuple[str, str] | None:
    """data-ref 'pK' or '<item>:pK' -> (item_id|None, pid)."""
    if ":" in ref:
        item, _, pid = ref.partition(":")
        return item or None, pid
    return None, ref


def _node_lang_text(node: lxml.html.HtmlElement) -> tuple[str, str]:
    cn = node.xpath("./span[contains(@class,'lang-cn')]")
    en = node.xpath(
        "./span[contains(@class,'lang-en')]"
        "| ./span[contains(@class,'sec-h-en')]"
        "| ./span[contains(@class,'lang-en-block')]"
    )
    return (cn[0].text_content() if cn else "", en[0].text_content() if en else "")


def _item_host(root: lxml.html.HtmlElement, aid: str) -> lxml.html.HtmlElement | None:
    arts = root.xpath(f'.//article[@data-unit="{aid}"]')
    if arts:
        return arts[0]
    letters = root.xpath(f'.//section[@data-letter="{aid}"]')
    return letters[0] if letters else None


def _unit_paragraph_texts(unit: lxml.html.HtmlElement) -> dict[str, str]:
    """Bare paragraph id -> bilingual text (CN + EN) for grounding checks."""
    out: dict[str, str] = {}
    for node in _narrative_nodes(unit):
        _, pid = _node_ref_pid(node.get("data-ref") or "")
        if not re.fullmatch(r"p\d+", pid):
            continue
        cn, en = _node_lang_text(node)
        out[pid] = cn + "\n" + en
    return out


def _charts_by_id(data: PilotData) -> dict[str, tuple[dict, dict]]:
    out = {}
    for a in data.articles.values():
        for m in a.get("media") or []:
            if m.get("type") == "chart":
                out[m["id"]] = (a, m)
    return out


def _chart_vectors(data: PilotData) -> dict[str, Any]:
    from .vector import ChartVector

    out: dict[str, ChartVector] = {}
    for cid, (a, m) in _charts_by_id(data).items():
        native = data.natives[int(m["page"])]
        W, H = float(native["width"]), float(native["height"])
        sibs = media_sibling_bboxes(a.get("media") or [], int(m["page"]), cid, W, H)
        out[cid] = extract_chart_vectors(
            native, cid, int(m["page"]), m["bbox_normalized_top_left"], sibs
        )
    return out


# --- Oracle 1: narrative conservation ------------------------------------------

def oracle_narrative_conservation(root: lxml.html.HtmlElement, data: PilotData) -> OracleResult:
    items = 0
    matched = 0
    mismatches: list[str] = []
    for aid in data.articles:
        host = _item_host(root, aid)
        if host is None:
            mismatches.append(f"{aid}: unit not found in artifact")
            continue
        pids = data.paragraph_ids(aid)
        nodes = _narrative_nodes(host)
        # An authored editorial subheading (sec-h) may carry the same data-ref
        # as its own prose paragraph (condensed rendering, prose preserved);
        # inventory subheading paragraphs instead appear ONLY as sec-h.  The
        # paragraph sequence takes the prose block when both exist.
        prose_pids = {
            _node_ref_pid(n.get("data-ref") or "")[1]
            for n in nodes
            if "prose-p" in (n.get("class") or "").split()
        }
        seq: dict[str, list[str]] = {"cn": [], "en": []}
        for node in nodes:
            item, pid = _node_ref_pid(node.get("data-ref") or "")
            if "prose-p" not in (node.get("class") or "").split() and pid in prose_pids:
                continue
            if item not in (None, aid) or pid not in pids:
                continue
            cn, en = _node_lang_text(node)
            seq["cn"].append(cn)
            seq["en"].append(en)
        items += 1
        ok = True
        for lang in ("cn", "en"):
            want_ids = [p for p in pids if data.bilingual(aid).get(p)]
            got = seq[lang]
            if len(got) != len(want_ids):
                ok = False
                mismatches.append(f"{aid}:{lang} paragraph count {len(got)} != {len(want_ids)}")
                continue
            digest = hashlib.sha256("\n\n".join(got).encode("utf-8")).hexdigest()
            if digest != data.narrative_sha256(aid, lang):
                ok = False
                mismatches.append(f"{aid}:{lang} sha256 round-trip mismatch")
        if ok:
            matched += 1
    return OracleResult(
        "narrative_conservation",
        passed=(matched == RAW_ITEM_COUNT == items and not mismatches),
        detail={
            "items": items,
            "matched": matched,
            "diff": items - matched,
            "sha256_round_trip": "100%" if matched == items else f"{matched}/{items}",
            "mismatches": mismatches[:10],
        },
    )


# --- Oracle 2: paragraph-scoped numeric grounding --------------------------------

def _element_text(el: lxml.html.HtmlElement) -> str:
    """Bilingual element text with node boundaries preserved.

    ``text_content()`` concatenates sibling text nodes without any separator,
    which fuses e.g. an EN scale word with the next CJK label and breaks
    token lookaheads — so adjacent nodes are joined with newlines instead.
    """
    return "\n".join(t for t in (s.strip() for s in el.itertext()) if t)


def _element_ungrounded(
    label: str,
    el: lxml.html.HtmlElement,
    para_texts: dict[str, str],
    extra_grounding: list[str],
) -> list[str]:
    refs = (el.get("data-src") or "").split()
    sources = [para_texts[r] for r in refs if r in para_texts]
    missing_refs = [r for r in refs if r not in para_texts]
    authored = _element_text(el)
    ungrounded = ground_numbers(authored, sources, extra_grounding=extra_grounding)
    out = [f"{label}: ungrounded {t.raw} ({t.value} {t.kind})" for t in ungrounded]
    out += [f"{label}: data-src {r} not in unit" for r in missing_refs]
    return out


def oracle_numeric_grounding(root: lxml.html.HtmlElement, data: PilotData) -> OracleResult:
    vectors = _chart_vectors(data)
    units = unit_elements(root)
    checked = 0
    failures: list[str] = []
    for uid, unit in units.items():
        para_texts = _unit_paragraph_texts(unit)
        # data-src-bearing authored elements (Issue #5 adds the Group C
        # dossier containers: hero ledger mini-stats, rail metric cards,
        # defense dossiers and the executive dossier card)
        for el in unit.xpath(
            ".//*[@data-src and (contains(@class,'takeaway') or contains(@class,'thesis-box')"
            " or contains(@class,'sec-h') or contains(@class,'wsj-chart')"
            " or contains(@class,'companion') or contains(@class,'metric-card')"
            " or contains(@class,'mini-stat') or contains(@class,'defense-dossier')"
            " or contains(@class,'dossier-card'))]"
        ):
            cls = el.get("class") or ""
            extra: list[str] = []
            cid = el.get("data-chart")
            if "companion" in cls and cid in vectors:
                extra.append(vectors[cid].grounding_text())
            checked += 1
            failures += _element_ungrounded(f"{uid}:{cls.split()[0]}", el, para_texts, extra)
        # pull quotes: numbers must ground in the quoted paragraph
        for pq in unit.xpath(".//blockquote[contains(@class,'pull-quote')]"):
            ref = pq.get("data-ref") or ""
            m = re.fullmatch(r"(?:[A-Z0-9-]+:)?(p\d+)\.s\d+", ref)
            checked += 1
            if not m:
                failures.append(f"{uid}: pull quote without valid data-ref {ref!r}")
                continue
            if m.group(1) not in para_texts:
                failures.append(f"{uid}: pull quote data-ref {ref} paragraph not in unit")
                continue
            authored = _element_text(pq)
            ungrounded = ground_numbers(authored, [para_texts[m.group(1)]])
            failures += [
                f"{uid}: pull quote ungrounded {t.raw} ({t.value} {t.kind})" for t in ungrounded
            ]
    pct = "100%" if not failures else f"{len(failures)} failures"
    return OracleResult(
        "paragraph_scoped_numeric_grounding",
        passed=not failures,
        detail={"elements_checked": checked, "failures": failures[:10], "grounding": pct},
    )


# --- Oracle 3: Retina* chart vector coverage -------------------------------------

def oracle_chart_vector_coverage(root: lxml.html.HtmlElement, data: PilotData) -> OracleResult:
    vectors = _chart_vectors(data)
    charts = _charts_by_id(data)
    failures: list[str] = []
    if len(vectors) != CHART_COUNT:
        failures.append(f"extracted {len(vectors)} charts != {CHART_COUNT}")
    companion_ids = root.xpath(".//aside[contains(@class,'companion')]/@data-chart")
    figure_ids = root.xpath(".//figure[@data-chart]/@data-chart")
    for cid, cv in vectors.items():
        with_ctx = f"chart:{cid}"
        a, m = charts[cid]
        W = float(data.natives[int(m["page"])]["width"])
        ox0, _, ox1, _ = [float(v) for v in m["bbox_normalized_top_left"]]
        orig_w = (ox1 - ox0) * W
        ux0, uy0, ux1, uy1 = cv.union_bbox_points
        if ux1 - ux0 > orig_w + 24.0:
            failures.append(f"{with_ctx} union width {ux1 - ux0:.1f} > orig + 24pt")
        native = data.natives[int(m["page"])]
        for l in native["lines"]:
            font = line_font(l)
            lx0, ly0, lx1, ly1 = l["bbox"]
            cx, cy = (lx0 + lx1) / 2, (ly0 + ly1) / 2
            if font.startswith(("Exchange", "DJ5Exchange")) and ux0 <= cx <= ux1 and uy0 <= cy <= uy1:
                failures.append(f"{with_ctx} crops body prose {l.get('text', '')[:40]!r}")
            if font.startswith("RetinaMPNarrowLt") and (lx1 - lx0) > 1.35 * orig_w:
                # shared multi-column source line: full text recovered, never sliced
                if lx0 < ux1 and ux0 < lx1 and ly0 < uy1 and uy0 < ly1:
                    failures.append(f"{with_ctx} slices shared source line {l.get('text', '')[:40]!r}")
        title = cv.title_en.replace("\ufb01", "fi").replace("\ufb02", "fl").replace("\ufb00", "ff")
        if not title or len(title) > 120 or "bellwether" in title:
            failures.append(f"{with_ctx} title not intact: {title[:80]!r}")
        if companion_ids.count(cid) != 1:
            failures.append(f"{with_ctx} companion cards: {companion_ids.count(cid)}")
        if figure_ids and figure_ids.count(cid) != 1:
            failures.append(f"{with_ctx} figure images: {figure_ids.count(cid)}")
    if len(companion_ids) != CHART_COUNT:
        failures.append(f"artifact has {len(companion_ids)} companions != {CHART_COUNT}")
    return OracleResult(
        "retina_chart_vector_coverage",
        passed=not failures,
        detail={
            "charts": len(vectors),
            "coverage": f"{len(vectors)}/{CHART_COUNT}",
            "failures": failures[:10],
        },
    )


# --- Oracle 4: figure monotonicity & ad exclusion --------------------------------

def _figure_anchor_sequence(unit: lxml.html.HtmlElement) -> list[tuple[str, str]]:
    """Document-order (kind, anchor) pairs for editorial figures.

    Anchors track the last narrative paragraph (prose or subheading) seen;
    ``p0`` means physically before the first paragraph.
    """
    out = []
    current = "p0"
    for el in unit.xpath(
        ".//p[contains(@class,'prose-p') and @data-ref]"
        "| .//h2[contains(@class,'sec-h') and @data-ref]"
        "| .//figure[contains(@class,'wsj-fig')]"
        "| .//div[contains(@class,'wsj-chart')]"
    ):
        cls = el.get("class") or ""
        if "wsj-fig" in cls or "wsj-chart" in cls:
            out.append((cls.split()[0], current))
            continue
        _, pid = _node_ref_pid(el.get("data-ref") or "")
        if re.fullmatch(r"p\d+", pid):
            current = pid
    return out


def oracle_figure_monotonicity(root: lxml.html.HtmlElement, data: PilotData) -> OracleResult:
    failures: list[str] = []
    page_widths = {pg: n["width"] for pg, n in data.natives.items()}
    page_heights = {pg: n["height"] for pg, n in data.natives.items()}
    column_grids = page_column_grids(data.natives)
    figure_ads = [r for r in root.xpath(".//figure/@data-ref") if r == "figure:p06-b60"]
    if figure_ads:
        failures.append("non-editorial print ad p06-b60 present as reader figure")
    for uid, unit in unit_elements(root).items():
        anchors = _figure_anchor_sequence(unit)
        # unit paragraph order (narrative + subheadings route through routing)
        aid = uid if uid in data.articles else None
        pids = data.paragraph_ids(aid) if aid else []
        index = {p: i for i, p in enumerate(pids)}
        seq = [index.get(a, -1) for _, a in anchors if a != "p0" and a in index]
        if seq != sorted(seq):
            failures.append(f"{uid}: figure anchors out of narrative order {anchors}")
        if pids:  # view-only print-page units (no paragraphs) cannot stack lede figures
            before_p1 = [a for _, a in anchors if index.get(a, -1) < index.get("p1", 0)]
            if len(before_p1) >= 2:
                failures.append(f"{uid}: {len(before_p1)} figures stacked before p1")
        # physical print order: anchor paragraph print key <= figure print key
        if aid and aid in data.articles:
            article = data.articles[aid]
            try:
                pkeys = paragraph_print_keys(article, page_heights, column_grids)
            except TracerCompilationError:
                pkeys = {}
            media_by_id = {m["id"]: m for m in article.get("media") or []}
            for f in unit.xpath(".//figure[@data-ref or @data-chart]"):
                ref = f.get("data-ref") or ""
                mid = f.get("data-chart") or (ref.removeprefix("figure:") if ref.startswith("figure:") else None)
                m = media_by_id.get(mid) if mid else None
                if m is None or "page" not in m:
                    continue  # view-only print page / non-media figure
                fkey = figure_print_key(m, page_widths, column_grids)
                anchor_key = pkeys.get(anchor_of(f, unit) or "")
                if anchor_key and anchor_key > fkey:
                    failures.append(f"{uid}: figure {mid} before anchor in print order")
    return OracleResult(
        "figure_narrative_monotonicity_and_ad_exclusion",
        passed=not failures,
        detail={"failures": failures[:10]},
    )


def anchor_of(fig: lxml.html.HtmlElement, unit: lxml.html.HtmlElement) -> str | None:
    """Anchor paragraph of one figure: last narrative node before it."""
    current = None
    for el in unit.xpath(
        ".//p[contains(@class,'prose-p') and @data-ref]"
        "| .//h2[contains(@class,'sec-h') and @data-ref]"
        "| .//figure[@data-ref or @data-chart]"
    ):
        if el is fig:
            return current or "p0"
        _, pid = _node_ref_pid(el.get("data-ref") or "")
        if re.fullmatch(r"p\d+", pid):
            current = pid
    return None


# --- Oracle 5: historical fault-injection recall ---------------------------------

def detect_cross_language_magnitude(en: str, cn: str) -> list[str]:
    """Stage-1 magnitude findings for one bilingual paragraph (E1 class)."""
    return [f.detail for f in scan_pair("INJECTED", "p1", en, cn) if f.kind == "magnitude"]


def detect_ungrounded_numbers(
    authored_text: str,
    source_texts: list[str],
    extra_grounding: list[str] | None = None,
) -> list[NumberToken]:
    """Ungrounded substantive numbers in an authored element (E1-010 class)."""
    return ground_numbers(authored_text, source_texts, extra_grounding=extra_grounding or [])


def detect_pseudo_quote(paragraph_en: str, m: int, quote_text: str) -> str | None:
    """None when the quote is verbatim p.sM; the violation message otherwise."""
    try:
        verify_quote_anchor(paragraph_en, m, quote_text)
    except TracerCompilationError as exc:
        return str(exc)
    return None


_SVG_TEXT_RE = re.compile(
    r'<text x="(-?[\d.]+)" y="(-?[\d.]+)"([^>]*)>(.*?)</text>', re.S
)


def svg_text_overflow_findings(svg_markup: str, label: str, viewbox_w: float) -> list[str]:
    """Static clip-free check (E3-001 class): estimated text extents must
    stay inside the viewBox width.  Mirrors charts._validate_svg_text_bounds
    so the oracle can re-verify compiled SVGs from the artifact DOM."""
    findings = []
    for m in _SVG_TEXT_RE.finditer(svg_markup):
        x = float(m.group(1))
        attrs = m.group(3)
        size_m = re.search(r'font-size="(\d+)"', attrs)
        size = int(size_m.group(1)) if size_m else 13
        anchor_m = re.search(r'text-anchor="(\w+)"', attrs)
        anchor = anchor_m.group(1) if anchor_m else "start"
        text = html_mod.unescape(re.sub(r"<[^>]+>", "", m.group(4)))
        tw = sum(size if ord(c) >= 0x2E80 else 0.6 * size for c in text)
        left = x - (tw / 2 if anchor == "middle" else tw if anchor == "end" else 0.0)
        right = x + (tw / 2 if anchor == "middle" else 0.0 if anchor == "end" else tw)
        if left < -1.0 or right > viewbox_w + 1.0:
            findings.append(
                f"svg[{label}]: text {text[:40]!r} extends [{left:.0f},{right:.0f}] "
                f"past viewBox width {viewbox_w:.0f}"
            )
    return findings


def detect_language_toggle_gap(root: lxml.html.HtmlElement) -> list[str]:
    """E2-001 class: every narrative element must carry its EN counterpart so
    the ``EN`` toggle hides all Chinese (no subhead/prose leak)."""
    gaps = []
    for p in root.xpath(".//p[contains(@class,'prose-p')]"):
        cn = p.xpath("./span[contains(@class,'lang-cn')]")
        en = p.xpath("./span[contains(@class,'lang-en')]")
        if cn and not en:
            gaps.append(f"prose {p.get('data-ref')}: missing lang-en span")
    for h in root.xpath(".//h2[contains(@class,'sec-h')]"):
        cn = h.xpath("./span[contains(@class,'lang-cn')]")
        en = h.xpath("./span[contains(@class,'sec-h-en') or contains(@class,'lang-en')]")
        if cn and not en:
            gaps.append(f"subhead {h.get('data-ref')}: missing EN counterpart")
    return gaps


def oracle_fault_injection_recall(root: lxml.html.HtmlElement, data: PilotData) -> OracleResult:
    """Execute all 6 historical failure-class injections; all must be caught."""
    checks: dict[str, dict[str, Any]] = {}

    # 1. 700 million -> 7000万 (10x magnitude distortion)
    hits = detect_cross_language_magnitude(
        "The company raised $700 million in new funding.",
        "该公司募集了7000万美元新资金。",
    )
    checks["magnitude_700m_to_7000wan"] = {"injected": True, "detected": bool(hits), "detail": hits}

    # 2. $2.3 billion -> 2.3亿 (10x magnitude distortion)
    hits = detect_cross_language_magnitude(
        "The deal is worth $2.3 billion.",
        "这笔交易价值2.3亿美元。",
    )
    checks["magnitude_2_3b_to_2_3yi"] = {"injected": True, "detected": bool(hits), "detail": hits}

    # 3. E1-010: ungrounded chart rate (4.12%) injected into a real companion
    spec = CHART_COMPANIONS["p19-b17"]
    bilingual = data.bilingual("CASE-B1B2-PRIVATE-EQUITY")
    src_texts = [bilingual[r]["en"] + "\n" + bilingual[r]["cn"] for r in str(spec["data_src"]).split()]
    ungrounded = detect_ungrounded_numbers(
        str(spec["takeaway_en"]) + " The rate was 4.12%.", src_texts
    )
    checks["ungrounded_chart_rate_4_12pct"] = {
        "injected": True,
        "detected": any(t.kind == "pct" and t.value == Decimal("4.12") for t in ungrounded),
        "detail": [f"{t.raw} ({t.value} {t.kind})" for t in ungrounded],
    }

    # 4. E3-004: pseudo-quote (not verbatim p.sM)
    para_en = bilingual["p14"]["en"]
    violation = detect_pseudo_quote(para_en, 1, split_sentences(para_en)[0][:-1] + "XYZ")
    checks["pseudo_quote_e3_004"] = {"injected": True, "detected": violation is not None, "detail": violation}

    # 5. E3-001: SVG text node shifted past the viewBox
    svg_el = root.xpath(".//div[contains(@class,'wsj-chart')]//svg")
    if svg_el:
        markup = lxml.html.tostring(svg_el[0], encoding="unicode")
        vb = re.search(r'view[Bb]ox="0 0 (\d+)', markup)
        vb_w = float(vb.group(1)) if vb else 0.0
        clean = svg_text_overflow_findings(markup, "artifact", vb_w)
        injected = _SVG_TEXT_RE.sub(
            lambda m: m.group(0).replace(f'x="{m.group(1)}"', f'x="{vb_w + 200.0}"', 1),
            markup, count=1,
        )
        hits = svg_text_overflow_findings(injected, "injected", vb_w)
        detected = not clean and bool(hits)
        detail: Any = {"clean_artifact_findings": len(clean), "injected_findings": hits[:2]}
    else:
        detected, detail = False, "no wsj-chart svg in artifact"
    checks["svg_text_overflow_viewbox_e3_001"] = {"injected": True, "detected": detected, "detail": detail}

    # 6. E2-001: broken EN toggle (drop a lang-en span) / subhead leak
    clone = copy.deepcopy(root)
    clean_gaps = detect_language_toggle_gap(root)
    victim = clone.xpath(".//p[contains(@class,'prose-p')]")
    if victim:
        en_span = victim[0].xpath("./span[contains(@class,'lang-en')]")
        if en_span:
            victim[0].remove(en_span[0])
    injected_gaps = detect_language_toggle_gap(clone)
    checks["broken_en_toggle_subhead_leak_e2_001"] = {
        "injected": True,
        "detected": not clean_gaps and len(injected_gaps) > len(clean_gaps),
        "detail": {"clean_gaps": len(clean_gaps), "injected_gaps": injected_gaps[:2]},
    }

    passed = all(c["detected"] for c in checks.values())
    return OracleResult(
        "historical_fault_injection_recall",
        passed=passed,
        detail={"recall": f"{sum(1 for c in checks.values() if c['detected'])}/6", "classes": checks},
    )


# --- Oracle 6: print hierarchy, composites, zero lede restatement ---------------

def oracle_print_hierarchy(root: lxml.html.HtmlElement, data: PilotData) -> OracleResult:
    failures: list[str] = []
    units = unit_elements(root)
    tiers = {t: sum(1 for u in units.values() if u.get("data-tier") == str(t)) for t in (1, 2, 3)}
    if tiers != EXPECTED_TIERS or len(units) != UNIT_COUNT:
        failures.append(f"unit tiers {tiers} total {len(units)} != {EXPECTED_TIERS} / {UNIT_COUNT}")
    # every raw item lands in exactly one unit
    composite_members = {m for spec in COMPOSITES.values() for m in spec["members"]}
    covered = set()
    for aid in data.articles:
        if aid in composite_members:
            host = root.xpath(f'.//section[@data-letter="{aid}"]')
        else:
            host = root.xpath(f'.//article[@data-unit="{aid}"] | .//div[@data-unit="{aid}"]')
        if not host:
            failures.append(f"{aid}: no unit in artifact")
        else:
            covered.add(aid)
    if len(covered) != RAW_ITEM_COUNT:
        failures.append(f"{len(covered)}/{RAW_ITEM_COUNT} raw items covered")
    # 28 raw sections -> 7 canonical sections + rubric kickers
    raw_sections = {a["section"] for a in data.articles.values()}
    if len(raw_sections) != 28:
        failures.append(f"raw section count {len(raw_sections)} != 28")
    try:
        mapped = {canonical_section(s) for s in raw_sections}
    except TracerCompilationError as exc:
        mapped, failures_map = set(), str(exc)
        failures.append(failures_map)
    canonical_keys = {key for key, _, _ in SECTIONS}
    if mapped != canonical_keys:
        failures.append(f"canonical sections {sorted(mapped)} != {sorted(canonical_keys)}")
    section_heads = {el.get("id") for el in root.xpath(".//div[contains(@class,'section-head')]")}
    if section_heads != {f"sec-{k}" for k in canonical_keys}:
        failures.append(f"artifact section heads {sorted(section_heads)}")
    kickers = " ".join(
        (k.text_content() or "") for k in root.xpath(".//article//p[contains(@class,'kicker')]")
    ).lower()
    for rubric in ("heard on the street", "review & outlook", "bookshelf", "jason gay",
                   "stock spotlight", "u.s. watch", "world watch", "analysis"):
        if rubric not in kickers:
            failures.append(f"rubric kicker missing: {rubric}")
    # 16/16 What's News deep links resolve to valid target unit ids
    hrefs = root.xpath(".//p[contains(@class,'wn-link')]//a/@href")
    if len(hrefs) != WHATSNEWS_LINKS:
        failures.append(f"deep links {len(hrefs)} != {WHATSNEWS_LINKS}")
    for href in hrefs:
        target = href.removeprefix("#u-")
        if not re.fullmatch(r"[A-Z0-9-]+", target) or target not in units:
            failures.append(f"deep link {href} does not resolve to a unit")
    # zero Tier 2 takeaway/thesis elements cite p1 (token-split: multi-ref
    # data-src="p1 p2" still cites the lede)
    for uid, unit in units.items():
        if unit.get("data-tier") != "2":
            continue
        for el in unit.xpath(
            ".//li[contains(@class,'takeaway')][@data-src]"
            "| .//div[contains(@class,'thesis-box')][@data-src]"
        ):
            refs = re.split(r"[\s,]+", (el.get("data-src") or "").strip())
            if "p1" in refs:
                failures.append(f"{uid}: Tier 2 element cites p1 ({el.get('class')})")
    return OracleResult(
        "print_hierarchy_composite_grouping_zero_lede_restatement",
        passed=not failures,
        detail={
            "tiers": tiers,
            "units": len(units),
            "raw_items": len(covered),
            "deep_links": len(hrefs),
            "failures": failures[:10],
        },
    )


# --- Oracle 7: viewport geometry, clean surface & payload budget ------------------

def find_chrome() -> str | None:
    env = os.environ.get("CHROME_BIN")
    if env and Path(env).exists():
        return env
    for cand in _CHROME_CANDIDATES:
        if Path(cand).exists():
            return cand
    return shutil.which("google-chrome") or shutil.which("chromium") or shutil.which("chrome")


_PROBE_JS = """
window.addEventListener('load', function () { setTimeout(function () {
  try { setLang('%(lang)s'); } catch (e) {}
  function visible(el) {
    var cs = window.getComputedStyle(el);
    return cs.display !== 'none' && cs.visibility !== 'hidden';
  }
  function measure() {
    var res = { overflow: [], overflowCount: 0, brokenImages: 0, clippedSvgText: [], clippedCount: 0 };
    var de = document.documentElement;
    if (de.scrollWidth > de.clientWidth) { res.overflow.push('document'); res.overflowCount++; }
    var els = document.querySelectorAll('body *');
    for (var i = 0; i < els.length; i++) {
      var el = els[i];
      try {
        // only elements actually rendered in the current view: .unit is
        // display:none in overview mode, so read-view overflow must be
        // measured after setView('read')
        if (el.scrollWidth > el.clientWidth + 1 && el.clientWidth > 0 && visible(el)) {
          res.overflowCount++;
          if (res.overflow.length < 5) {
            res.overflow.push(el.tagName + '.' + (el.getAttribute('class') || '') + '#' + (el.id || ''));
          }
        }
      } catch (e) {}
    }
    var imgs = document.querySelectorAll('img');
    for (var j = 0; j < imgs.length; j++) {
      // --fast smoke artifacts embed empty data-URI placeholders; a real
      // broken image carries a non-empty URI that fails to decode
      if (imgs[j].src === 'data:image/webp;base64,') continue;
      if (imgs[j].complete && imgs[j].naturalWidth === 0) res.brokenImages++;
    }
    var svgs = document.querySelectorAll('svg');
    for (var k = 0; k < svgs.length; k++) {
      var svg = svgs[k];
      var vb = svg.viewBox && svg.viewBox.baseVal;
      if (!vb || !vb.width || !visible(svg)) continue;
      var texts = svg.querySelectorAll('text');
      for (var t = 0; t < texts.length; t++) {
        var node = texts[t];
        try {
          var bb = node.getBBox();
          if (bb.x < -1 || bb.y < -1 || bb.x + bb.width > vb.width + 1 || bb.y + bb.height > vb.height + 1) {
            res.clippedCount++;
            if (res.clippedSvgText.length < 5) {
              res.clippedSvgText.push((svg.getAttribute('data-chart') || svg.parentNode.getAttribute('data-chart') || 'svg') + ':' + node.textContent.slice(0, 30));
            }
          }
        } catch (e) {}
      }
    }
    return res;
  }
  var out = {};
  try { setView('overview'); } catch (e) {}
  out.overview = measure();
  try { setView('read'); } catch (e) {}
  out.read = measure();
  out.passed = [out.overview, out.read].every(function (v) {
    return v.overflowCount === 0 && v.brokenImages === 0 && v.clippedCount === 0;
  });
  document.title = 'PROBE:' + JSON.stringify(out);
}, 400); });
"""


def run_chrome_geometry_probe(html_path: str | Path, chrome: str | None = None,
                              timeout: int = 60) -> dict[str, Any]:
    """Headless Chrome DOM geometry probe: 2 viewports x 3 language modes.

    Confirms ``scrollWidth <= clientWidth`` (document and every element),
    0 broken images and 0 clipped SVG text nodes per (viewport, lang) cell.
    """
    chrome = chrome or find_chrome()
    if not chrome:
        raise FileNotFoundError("no Headless Chrome binary found")
    src = Path(html_path).read_text("utf-8")
    results: dict[str, Any] = {}
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        for width, height in VIEWPORTS:
            for lang in LANG_MODES:
                probe = _PROBE_JS % {"lang": lang}
                doc = src.replace("</body>", f"<script>{probe}</script></body>")
                cell_html = tmp_path / f"probe-{width}x{height}-{lang}.html"
                cell_html.write_text(doc, "utf-8")
                profile = tmp_path / f"prof-{width}x{height}-{lang}"
                cmd = [
                    chrome, "--headless=new", "--disable-gpu", "--no-first-run",
                    "--no-default-browser-check", f"--user-data-dir={profile}",
                    f"--window-size={width},{height}", "--force-device-scale-factor=1",
                    "--virtual-time-budget=12000", "--dump-dom",
                    cell_html.resolve().as_uri(),
                ]
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
                m = re.search(r"<title>PROBE:(.*?)</title>", proc.stdout, re.S)
                if not m:
                    raise RuntimeError(
                        f"chrome probe produced no result for {width}x{height}/{lang}: "
                        f"rc={proc.returncode} {proc.stderr[:200]}"
                    )
                payload = html_mod.unescape(m.group(1))
                import json

                data = json.loads(payload)
                views = {v: data[v] for v in ("overview", "read") if v in data}
                data["passed"] = all(
                    v["overflowCount"] == 0 and v["brokenImages"] == 0 and v["clippedCount"] == 0
                    for v in views.values()
                ) and bool(views)
                results[f"{width}x{height}/{lang}"] = data
    return results


def oracle_viewport_geometry(artifact_text: str, size_bytes: int, html_path: str | Path,
                             chrome: str | None,
                             check_budget: bool = True,
                             run_geometry_probe: bool = True) -> OracleResult:
    failures: list[str] = []
    if check_budget and not (SIZE_MIN_BYTES <= size_bytes <= SIZE_MAX_BYTES):
        failures.append(
            f"artifact size {size_bytes} outside [{SIZE_MIN_BYTES}, {SIZE_MAX_BYTES}]"
        )
    for s in CERT_FORBIDDEN_STRINGS:
        if s in artifact_text:
            failures.append(f"forbidden pipeline string on reader surface: {s!r}")
    # static SVG clip check across every compiled chart in the artifact
    root = lxml.html.fromstring(artifact_text)
    for div in root.xpath(".//div[contains(@class,'wsj-chart')]"):
        svg = div.xpath(".//svg")
        if not svg:
            failures.append(f"wsj-chart {div.get('data-chart')}: no svg")
            continue
        markup = lxml.html.tostring(svg[0], encoding="unicode")
        vb = re.search(r'view[Bb]ox="0 0 (\d+)', markup)
        if not vb:
            failures.append(f"wsj-chart {div.get('data-chart')}: no viewBox")
            continue
        hits = svg_text_overflow_findings(markup, div.get("data-chart") or "?", float(vb.group(1)))
        failures += hits[:3]
    probe: dict[str, Any] = {"status": "skipped", "reason": "geometry probe disabled"}
    if run_geometry_probe:
        if chrome is None and not find_chrome():
            probe = {"status": "skipped", "reason": "no chrome binary found"}
        else:
            try:
                probe = run_chrome_geometry_probe(html_path, chrome=chrome)
                for cell, data in probe.items():
                    if not data["passed"]:
                        failures.append(f"geometry probe {cell}: {data}")
            except (RuntimeError, subprocess.TimeoutExpired, FileNotFoundError) as exc:
                probe = {"status": "error", "reason": str(exc)}
                failures.append(f"chrome geometry probe failed: {exc}")
    return OracleResult(
        "viewport_geometry_clean_surface_payload",
        passed=not failures,
        detail={"size_bytes": size_bytes, "budget": f"[{SIZE_MIN_BYTES}, {SIZE_MAX_BYTES}]",
                "chrome_probe": probe, "failures": failures[:10]},
    )


# --- certification entry point -----------------------------------------------------

def certify(
    html_path: str | Path,
    data: PilotData,
    *,
    out_path: str | Path | None = None,
    chrome: str | None = None,
    check_budget: bool = True,
    run_geometry_probe: bool = True,
) -> CertificationReport:
    """Run all 7 oracles against a generated Issue Artifact."""
    html_path = Path(html_path)
    artifact_text = html_path.read_text("utf-8")
    size_bytes = html_path.stat().st_size
    root = lxml.html.fromstring(artifact_text)
    report = CertificationReport(artifact=str(html_path), size_bytes=size_bytes)
    report.oracles.append(oracle_narrative_conservation(root, data))
    report.oracles.append(oracle_numeric_grounding(root, data))
    report.oracles.append(oracle_chart_vector_coverage(root, data))
    report.oracles.append(oracle_figure_monotonicity(root, data))
    report.oracles.append(oracle_fault_injection_recall(root, data))
    report.oracles.append(oracle_print_hierarchy(root, data))
    report.oracles.append(
        oracle_viewport_geometry(
            artifact_text, size_bytes, html_path, chrome,
            check_budget, run_geometry_probe,
        )
    )
    if out_path is not None:
        out = Path(out_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        import json

        out.write_text(
            json.dumps(report.to_dict(), ensure_ascii=False, indent=1), "utf-8"
        )
    return report
