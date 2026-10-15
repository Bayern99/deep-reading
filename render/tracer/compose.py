"""Reading-unit composition: canonical projection, natural figure anchoring,
tier routing and composite columns.

The canonical source is the ordered bilingual projection of an approved source
item (GLOSSARY): inventory paragraph ids mapped to reviewed translation units.
Figures anchor at their natural ``after pK`` narrative position following
physical print reading order — paragraph print positions come from each
paragraph's last ``native_line_ids`` region (page, column, y); figure print
positions from their PDF page + normalized bbox.  Physical order on a page is
column-major: column index from the story's printed column origins, then
vertical position.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import lxml.html

from .verify import (
    TracerCompilationError,
    check_highlight_density,
    surgical_narrative_completion,
    verify_element_numbers,
)

PILOT_ROOT = Path("/Users/dmus/Documents/deep-reading/wsj-deep-read-bakeoff/experiments/pdf-parser-bakeoff/first-issue-pilot")
PDF_PATH = Path("/Users/dmus/Documents/deep-reading/WSJ Row/RZuKHuduV9Bwqu9z5TqB-WSJNewsPaper-10-14-2026.pdf")
PDF_SHA256 = "71201cc5c4ed0f3f9bae1a7fbed3e0d25c9207851d4a44713caf846494596f35"

LETTERS_PAGE16 = [
    "PILOT-A16-DIESEL-DOUG", "PILOT-A16-DIESEL-BOB", "PILOT-A16-DIESEL-STEVEN",
    "PILOT-A16-DIESEL-CHARLES", "PILOT-A16-DIESEL-DAN", "PILOT-A16-EDUCATION",
    "PILOT-A16-PERMITTING", "PILOT-A16-SHAPIRO", "PILOT-A16-NOBEL",
]


@dataclass
class PilotData:
    inventory: dict[str, Any]
    articles: dict[str, dict[str, Any]]
    translations: dict[str, dict[str, dict[str, str]]]  # article -> unit id -> {en, cn}
    natives: dict[int, dict[str, Any]]

    def units(self, article_id: str) -> dict[str, dict[str, str]]:
        return self.translations[article_id]

    def paragraph_ids(self, article_id: str) -> list[str]:
        return [p["id"] for p in self.articles[article_id]["paragraphs"]]

    def bilingual(self, article_id: str) -> dict[str, dict[str, str]]:
        """Paragraph id -> {en, cn} from the reviewed translation units."""
        units = self.units(article_id)
        out: dict[str, dict[str, str]] = {}
        for pid in self.paragraph_ids(article_id):
            u = units.get(pid)
            if u is None:
                raise TracerCompilationError(f"{article_id}: reviewed translation missing {pid}")
            out[pid] = u
        return out

    def narrative_sha256(self, article_id: str, lang: str) -> str:
        key = "cn" if lang == "cn" else "en"
        text = "\n\n".join(self.bilingual(article_id)[pid][key] for pid in self.paragraph_ids(article_id))
        return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_pilot_data(root: Path | str = PILOT_ROOT) -> PilotData:
    root = Path(root)
    inventory = json.loads((root / "inventory.json").read_text("utf-8"))
    articles = {a["id"]: a for a in inventory["articles"]}
    translations: dict[str, dict[str, dict[str, str]]] = {}
    wanted = [
        "PILOT-A1-BANKS", "PILOT-A1-CONDO", "PILOT-A1-NAVY", "PILOT-A15-EDGEWORTH",
        "PILOT-A16-WEALTH", *LETTERS_PAGE16,
    ]
    for aid in wanted:
        t = json.loads((root / "translations-reviewed" / f"{aid}.json").read_text("utf-8"))
        translations[aid] = {u["id"]: {"en": u["en"], "cn": u["zh_CN"]} for u in t["units"]}
    natives: dict[int, dict[str, Any]] = {}
    for aid in ("PILOT-A1-BANKS", "PILOT-A1-NAVY", "PILOT-A15-EDGEWORTH"):
        for pg in articles[aid]["all_pages"]:
            p = root / "evidence" / f"p{pg:02d}-native.json"
            if p.exists() and pg not in natives:
                natives[pg] = json.loads(p.read_text("utf-8"))
    return PilotData(inventory=inventory, articles=articles, translations=translations, natives=natives)


# --- physical print order ----------------------------------------------------

def _column_origins(article: dict[str, Any]) -> dict[int, list[float]]:
    """Printed column x-origins (points) per page, from the story's regions."""
    origins: dict[int, set[float]] = {}
    for r in article.get("regions", []):
        origins.setdefault(int(r["page"]), set()).add(float(r["column_origin"]))
    return {pg: sorted(v) for pg, v in origins.items()}


def _col_index(x: float, origins: list[float]) -> int:
    if not origins:
        return 0
    return min(range(len(origins)), key=lambda i: abs(x - origins[i]))


def paragraph_print_keys(
    article: dict[str, Any],
    page_heights: dict[int, float] | None = None,
) -> dict[str, tuple[int, int, float]]:
    """Print-order key per paragraph: max over its native regions.

    The key is (page, column, y) under column-major physical reading order, so
    the value marks where reading of that paragraph finishes on the printed
    page.  ``y`` is normalized to the page height so keys are comparable with
    figure bboxes (which are normalized in the inventory).
    """
    origins = _column_origins(article)
    heights = page_heights or {}
    keys: dict[str, tuple[int, int, float]] = {}
    for p in article["paragraphs"]:
        best: tuple[int, int, float] | None = None
        for r in p.get("native_regions") or []:
            b = r.get("bbox_points_top_left")
            if not b or r.get("page") is None:
                continue
            pg = int(r["page"])
            H = heights.get(pg)
            y_norm = float(b[1]) / H if H else float(b[1])
            key = (pg, _col_index(float(b[0]), origins.get(pg, [])), y_norm)
            if best is None or key > best:
                best = key
        if best is None:
            raise TracerCompilationError(f"{article['id']}: paragraph {p['id']} has no native regions")
        keys[p["id"]] = best
    return keys


def figure_print_key(
    media: dict[str, Any],
    article: dict[str, Any],
    page_widths: dict[int, float] | None = None,
) -> tuple[int, int, float]:
    origins = _column_origins(article)
    pg = int(media["page"])
    x0, y0, x1, _ = [float(v) for v in media["bbox_normalized_top_left"]]
    W = (page_widths or {}).get(pg)
    if W and origins.get(pg):
        center_pt = (x0 + x1) / 2 * W
        col = _col_index(center_pt, origins[pg])
    else:
        col = 0
    return (pg, col, y0)


# Markers that identify non-editorial print advertisements (PSAs) placed in a
# story's column; such regions are excluded from reader figures.  Ad copy is
# set in non-Dow-Jones fonts (e.g. Gotham) and never carries editorial
# captions or credits; photo regions of genuine figures contain only Dow Jones
# print families (Exchange/DJ5/Escrow/Retina/Dispatch) or no text at all.
AD_MARKERS = ("Ad Council", "FeedingAmerica", "Feeding America", "feedingamerica", "ad council")
WSJ_FONT_PREFIXES = ("Exchange", "DJ5", "Escrow", "Retina", "Dispatch", "Archer", "Steed", "Bell")


def is_print_ad(media: dict[str, Any], natives: dict[int, dict[str, Any]] | None) -> bool:
    """A print ad has ad copy (non-WSJ fonts or ad markers) in its region."""
    if media.get("type") not in ("photo", "image"):
        return False
    native = (natives or {}).get(int(media["page"]))
    if not native:
        return False
    W, H = float(native["width"]), float(native["height"])
    x0, y0, x1, y1 = [float(v) for v in media["bbox_normalized_top_left"]]
    bx0, by0, bx1, by1 = x0 * W, y0 * H, x1 * W, y1 * H
    non_wsj_lines = 0
    for line in native["lines"]:
        b = line["bbox"]
        if b[3] < by0 - 5 or b[1] > by1 + 5 or b[2] < bx0 - 5 or b[0] > bx1 + 5:
            continue
        text = line.get("text", "")
        if any(marker in text for marker in AD_MARKERS):
            return True
        chars = line.get("chars") or []
        if not chars:
            continue
        font = chars[0].get("font", "")
        if not font.startswith(WSJ_FONT_PREFIXES):
            non_wsj_lines += 1
    return non_wsj_lines >= 2


def anchor_figures(
    article: dict[str, Any],
    page_widths: dict[int, float] | None = None,
    page_heights: dict[int, float] | None = None,
    natives: dict[int, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Natural narrative anchor for every editorial figure: ``after pK`` in
    print order.

    Returns media entries enriched with ``anchor`` (paragraph id) and
    ``print_key``, sorted by physical print order.  Print advertisements are
    excluded.  Anchors are monotonic by construction; at most one lead figure
    may land before ``p2`` when a photo genuinely sits above the second
    paragraph on the printed page.
    """
    pkeys = paragraph_print_keys(article, page_heights)
    pids = [p["id"] for p in article["paragraphs"]]
    out = []
    media = [m for m in (article.get("media") or []) if not is_print_ad(m, natives)]
    for m in sorted(media, key=lambda m: m["id"]):
        fkey = figure_print_key(m, article, page_widths)
        anchor = None
        for pid in pids:
            if pkeys[pid] <= fkey:
                anchor = pid
        if anchor is None:
            anchor = "p0"  # lead image physically before the first paragraph
        out.append({**m, "anchor": anchor, "print_key": fkey})
    out.sort(key=lambda m: m["print_key"])
    return out


# --- AST builders ------------------------------------------------------------

def _el(tag: str, cls: str | None = None, **attrs: str) -> lxml.html.HtmlElement:
    e = lxml.html.Element(tag)
    if cls:
        e.set("class", cls)
    for k, v in attrs.items():
        e.set(k.replace("_", "-"), v)
    return e


PROSE_CLS = "prose-p"


def prose_block(pid: str, cn: str, en: str, hl_cn: str = "", hl_en: str = "") -> lxml.html.HtmlElement:
    p = _el("p", PROSE_CLS, data_ref=pid)
    for cls, text, hl in (("lang-cn", cn, hl_cn), ("lang-en", en, hl_en)):
        span = _el("span", cls)
        span.text = text
        if hl:
            span.set("data-hl", hl)
        p.append(span)
    _apply_mark_tails(p)
    return p


def _append_text(node: lxml.html.HtmlElement, text: str) -> None:
    if len(node):
        last = node[-1]
        last.tail = (last.tail or "") + text
    else:
        node.text = (node.text or "") + text


def _apply_mark_tails(p: lxml.html.HtmlElement) -> None:
    """Apply every pipe-separated ``data-hl`` phrase to the span text.

    Each matched phrase is wrapped in ``<mark class="ed-hl">`` at its first
    occurrence; overlapping matches are resolved left-to-right (longer phrase
    wins at the same offset).  Unmatched phrases are ignored; the density cap
    is enforced over all applied marks by ``check_highlight_density``.
    """
    for span in p.xpath("./span[contains(@class,'lang-cn') or contains(@class,'lang-en')]"):
        cls = span.get("class")
        hl = span.get("data-hl") or ""
        text = span.text or ""
        for child in list(span):
            span.remove(child)
        span.text = None
        phrases = [x.strip() for x in hl.split("|") if x.strip()]
        matches: list[tuple[int, int]] = []
        for phrase in phrases:
            idx = text.find(phrase)
            if idx >= 0:
                matches.append((idx, len(phrase)))
        matches.sort(key=lambda m: (m[0], -m[1]))
        chosen: list[tuple[int, int]] = []
        end = 0
        for idx, ln in matches:
            if idx >= end:
                chosen.append((idx, ln))
                end = idx + ln
        pos = 0
        for idx, ln in chosen:
            if idx > pos:
                _append_text(span, text[pos:idx])
            mark = _el("mark", "ed-hl")
            mark.text = text[idx:idx + ln]
            span.append(mark)
            pos = idx + ln
        if pos < len(text):
            _append_text(span, text[pos:])
        span.set("class", cls)


def prose_block(pid: str, cn: str, en: str, hl_cn: str = "", hl_en: str = "") -> lxml.html.HtmlElement:
    p = _el("p", PROSE_CLS, data_ref=pid)
    for cls, text, hl in (("lang-cn", cn, hl_cn), ("lang-en", en, hl_en)):
        span = _el("span", cls)
        span.text = text
        if hl:
            span.set("data-hl", hl)
        p.append(span)
    _apply_mark_tails(p)
    return p


def section_subheading(doc: lxml.html.HtmlElement, pid: str, cn: str, en: str,
                       data_src: str) -> lxml.html.HtmlElement:
    h = _el("h2", "sec-h")
    h.set("data-ref", pid)
    h.set("data-src", data_src)
    h_cn = _el("span", "lang-cn")
    h_cn.text = cn
    h.append(h_cn)
    h_en = _el("span", "sec-h-en")
    h_en.text = en
    h.append(h_en)
    doc.append(h)
    return h


# --- composite column ----------------------------------------------------------

def composite_letters_unit(data: PilotData, letter_ids: list[str] | None = None) -> lxml.html.HtmlElement:
    """Merge same-page letters into one cohesive composite column.

    Letters sharing a printed title are grouped under one shared sub-header;
    every letter's paragraphs and signature are conserved verbatim.
    """
    letter_ids = letter_ids or LETTERS_PAGE16
    article_el = _el("article", "unit unit-tier3", data_unit="COMPOSITE-A16-LETTERS")
    head = _el("header", "unit-head")
    kicker = _el("p", "kicker")
    kicker.text = "来信 · LETTERS TO THE EDITOR · A16"
    head.append(kicker)
    h1 = _el("h1")
    h1.set("data-ref", "title")
    h1.text = "读者来信"
    en = _el("span", "lang-en-block")
    en.text = "Letters to the Editor"
    h1.append(en)
    head.append(h1)
    article_el.append(head)

    groups: dict[str, list[str]] = {}
    for lid in letter_ids:
        title = data.articles[lid]["original_title"]
        groups.setdefault(title, []).append(lid)

    for title, lids in groups.items():
        shared = len(lids) > 1
        if shared:
            sh = _el("h2", "letter-group-title")
            sh.set("data-ref", f"title:{lids[0]}")
            sh.text = title
            article_el.append(sh)
        for lid in lids:
            letter = data.articles[lid]
            block = _el("section", "letter", data_letter=lid)
            if not shared:
                lt = _el("h2", "letter-title")
                lt.set("data-ref", "title")
                lt.text = title
                block.append(lt)
            bilingual = data.bilingual(lid)
            for pid in data.paragraph_ids(lid):
                block.append(prose_block(f"{lid}:{pid}", bilingual[pid]["cn"], bilingual[pid]["en"]))
            sig = _el("p", "letter-sig")
            sig.text = letter.get("byline", "")
            block.append(sig)
            article_el.append(block)
    return article_el


# --- full article unit composition ---------------------------------------------

def compose_article_unit(
    data: PilotData,
    article_id: str,
    *,
    tier: int,
    genre: str,
    kicker: str,
    takeaways: list[dict[str, str]] | None = None,
    thesis: dict[str, str] | None = None,
    subheadings: dict[str, dict[str, str]] | None = None,
    highlights: dict[str, dict[str, str]] | None = None,
    pull_quote: dict[str, Any] | None = None,
    book_details: dict[str, str] | None = None,
    wsj_charts: list[dict[str, Any]] | None = None,
    chart_companions: list[dict[str, Any]] | None = None,
    figures: list[dict[str, Any]] | None = None,
    body_elements: list[lxml.html.HtmlElement] | None = None,
) -> lxml.html.HtmlElement:
    """Compose one Tier 1/2 reading unit over the canonical bilingual source.

    Every authored intervention (takeaway, subheading, chart, companion) is
    numerically verified against its ``data-src`` paragraphs before assembly;
    narrative blocks are surgically completed; highlight density is enforced.
    """
    article = data.articles[article_id]
    bilingual = data.bilingual(article_id)
    pids = list(bilingual.keys())
    para_texts = {pid: {"en": bilingual[pid]["en"], "cn": bilingual[pid]["cn"]} for pid in pids}

    def src_texts(refs: str) -> list[str]:
        return [bilingual[r]["en"] for r in refs.split() if r in bilingual] + [
            bilingual[r]["cn"] for r in refs.split() if r in bilingual
        ]

    # verify authored interventions up-front (zero silent fallback)
    for i, tk in enumerate(takeaways or [], 1):
        verify_element_numbers(f"{article_id} takeaway[{i}]", tk["cn"] + "\n" + tk["en"], src_texts(tk["data_src"]))
    if thesis:
        verify_element_numbers(f"{article_id} thesis", thesis["cn"] + "\n" + thesis["en"], src_texts(thesis["data_src"]))
    for pid, sub in (subheadings or {}).items():
        verify_element_numbers(f"{article_id} subheading[{pid}]", sub["cn"] + "\n" + sub["en"], src_texts(sub.get("data_src", pid)))
    for pid, hl in (highlights or {}).items():
        if pid not in bilingual:
            raise TracerCompilationError(f"{article_id}: highlight references unknown paragraph {pid}")

    root = _el("article", f"unit-inner unit-tier{tier} genre-{genre}", data_unit=article_id)
    head = _el("header", "unit-head")
    k = _el("p", "kicker")
    k.text = kicker
    head.append(k)
    title = _el("h1")
    title.set("data-ref", "title")
    title.text = data.units(article_id)["title"]["cn"]
    t_en = _el("span", "lang-en-block")
    t_en.text = data.units(article_id)["title"]["en"]
    title.append(t_en)
    head.append(title)
    dek = data.units(article_id).get("dek")
    if dek and dek.get("cn"):
        d = _el("p", "dek")
        d.text = dek["cn"]
        d_en = _el("span", "lang-en-block")
        d_en.text = dek["en"]
        d.append(d_en)
        head.append(d)
    byline = (article.get("byline") or "").strip()
    if byline:
        b = _el("p", "byline")
        b.text = byline.title()
        head.append(b)
    root.append(head)

    if thesis:
        box = _el("div", "thesis-box")
        box.set("data-src", thesis["data_src"])
        box.text = thesis["cn"]
        box_en = _el("span", "lang-en-block")
        box_en.text = thesis["en"]
        box.append(box_en)
        root.append(box)

    if takeaways:
        ul = _el("ul", "takeaways")
        for tk in takeaways:
            li = _el("li", "takeaway")
            li.set("data-src", tk["data_src"])
            li.text = tk["cn"]
            li_en = _el("span", "lang-en-block")
            li_en.text = tk["en"]
            li.append(li_en)
            ul.append(li)
        root.append(ul)

    if book_details:
        bd = _el("aside", "book-details")
        bd.set("data-ref", "caption:book-details")
        for line in ("title_cn", "title_en", "author", "imprint"):
            div = _el("div", f"bd-{line}")
            div.text = book_details.get(line, "")
            bd.append(div)
        root.append(bd)

    # body: merge authored elements with canonical narrative in paragraph order
    highlights = highlights or {}
    subheadings = subheadings or {}
    charts_by_anchor: dict[str, list[dict[str, Any]]] = {}
    for ch in wsj_charts or []:
        refs = ch["data_src"].split()
        anchor = max((r for r in refs if r in bilingual), key=lambda r: pids.index(r))
        charts_by_anchor.setdefault(anchor, []).append(ch)
    companions_by_anchor: dict[str, list[dict[str, Any]]] = {}
    for comp in chart_companions or []:
        companions_by_anchor.setdefault(comp["anchor"], []).append(comp)
    figures_by_anchor: dict[str, list[dict[str, Any]]] = {}
    for fig in figures or []:
        figures_by_anchor.setdefault(fig["anchor"], []).append(fig)

    body = _el("div", "unit-body")
    for pid in pids:
        if pid in subheadings:
            sub = subheadings[pid]
            h = _el("h2", "sec-h")
            h.set("data-ref", pid)
            h.set("data-src", sub.get("data_src", pid))
            h_cn = _el("span", "lang-cn")
            h_cn.text = sub["cn"]
            h.append(h_cn)
            h_en = _el("span", "sec-h-en")
            h_en.text = sub["en"]
            h.append(h_en)
            body.append(h)
        hl = highlights.get(pid, {})
        body.append(prose_block(pid, bilingual[pid]["cn"], bilingual[pid]["en"], hl.get("cn", ""), hl.get("en", "")))
        for fig in figures_by_anchor.get(pid, []):
            body.append(fig["element"])
        for comp in companions_by_anchor.get(pid, []):
            body.append(comp["element"])
        for ch in charts_by_anchor.get(pid, []):
            body.append(ch["element"])
    for extra in body_elements or []:
        body.append(extra)
    root.append(body)

    if pull_quote:
        m = int(pull_quote["sentence"])
        from .verify import verify_quote_anchor
        verify_quote_anchor(bilingual[pull_quote["paragraph"]]["en"], m, pull_quote["en"])
        pq = _el("blockquote", "pull-quote")
        pq.set("data-ref", f"{pull_quote['paragraph']}.s{m}")
        pq.text = pull_quote["cn"]
        pq_en = _el("span", "lang-en-block")
        pq_en.text = pull_quote["en"]
        pq.append(pq_en)
        root.append(pq)

    # AST surgical completion + highlight density, then report repairs
    repairs = surgical_narrative_completion(root, pids, {pid: (bilingual[pid]["cn"], bilingual[pid]["en"]) for pid in pids})
    root.set("data-repairs", ";".join(repairs))
    check_highlight_density(root)
    return root
