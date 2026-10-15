"""Full-issue composition: ~70 cohesive reading units from 86 raw fragments.

Every Tier 1/2 unit is composed over the canonical bilingual projection with
the genre-aware layer of ADR 0001; Tier 3 units use compact functional
formats (digest, composite columns, brief, photo caption, view-only market
tables).  All authored numbers are verified against ``data-src`` paragraphs
before assembly; unknown inventory types or unresolvable anchors raise
``TracerCompilationError`` — tiers are never silently downgraded.
"""
from __future__ import annotations

import base64
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import lxml.html

from . import charts, content
from .compose import (
    PilotData,
    anchor_figures,
    compose_article_unit,
    is_print_ad,
    prose_block,
    _el,
)
from .routing import (
    COMPOSITES,
    SIDEBAR_PARENT,
    TIER3_STANDALONE,
    VIEW_ONLY_TABLE_PAGES,
    route_issue,
)
from .shell import UnitEntry
from .vector import (
    chart_webp,
    crop_pdf_region,
    encode_webp,
    esc,
    extract_chart_vectors,
    media_sibling_bboxes,
    reencode_image_file,
)
from .verify import (
    TracerCompilationError,
    split_sentences,
    verify_element_numbers,
)
from .whatsnews import HEADER_PARAGRAPHS, deep_link_badge, resolve_whatsnews
from .numbers import extract_substantive_numbers, ground_numbers

_SENT_SPLIT_CN = "。！？；\n"

# Authored pull-quote CN renderings (verified against the canonical paragraph).
PULL_QUOTES_CN = {
    "PILOT-A16-WEALTH": "“整个国家，甚至全世界的人们都在密切关注这里发生的一切。”",
    "PILOT-A1-CHINA-YOUTH": "“放眼未来，实在看不到多少希望。”",
}


def _data_uri(webp: bytes) -> str:
    return "data:image/webp;base64," + base64.b64encode(webp).decode("ascii")


def _cn_first_sentence(text: str) -> str:
    for i, ch in enumerate(text or ""):
        if ch in _SENT_SPLIT_CN:
            return text[: i + 1]
    return (text or "").strip()


# --- inventory subheadings -----------------------------------------------------

def inventory_subheadings(data: PilotData, aid: str) -> tuple[dict[str, dict[str, str]], set[str]]:
    """Inventory ``subheading`` paragraphs become verbatim section heads."""
    units = data.units(aid)
    subs: dict[str, dict[str, str]] = {}
    skip: set[str] = set()
    for p in data.articles[aid]["paragraphs"]:
        if p.get("type") == "subheading" and p["id"] in units:
            pid = p["id"]
            subs[pid] = {"cn": units[pid]["cn"], "en": units[pid]["en"], "data_src": pid}
            skip.add(pid)
    return subs, skip


# --- rule-based genre layer (Tier 2) -------------------------------------------

def _prose_paragraphs_after_lede(data: PilotData, aid: str) -> list[str]:
    """Prose paragraph ids after the opening lede: restating p1 in a
    takeaway/thesis box is forbidden (FOUNDATION.md Invariant 5 — the reader
    reads p1 immediately below the box)."""
    units = data.units(aid)
    out = []
    for p in data.articles[aid]["paragraphs"]:
        if p.get("type") == "subheading" or p["id"] not in units:
            continue
        out.append(p["id"])
    return out[1:] if len(out) > 1 else out


def _numbered_first(pids: list[str], units: dict[str, dict[str, str]], limit: int) -> list[str]:
    """Paragraphs carrying substantive numbers first (findings over filler),
    original print order preserved within each class."""
    with_nums = [p for p in pids if extract_substantive_numbers(units[p]["en"])]
    ordered = with_nums + [p for p in pids if p not in with_nums]
    return ordered[:limit]


def _auto_pull_quote(data: PilotData, aid: str, used: set[str]) -> dict[str, Any] | None:
    """First verbatim quoted sentence of the story (EN) paired with the same
    paragraph's first quoted CN sentence; both must exist.  ``used`` holds
    whitespace-normalized EN sentences already spent on takeaways/thesis so
    a pull quote never restates them (Invariant 5)."""
    units = data.units(aid)
    for p in data.articles[aid]["paragraphs"]:
        pid = p["id"]
        if pid not in units:
            continue
        en = units[pid]["en"]
        for i, s in enumerate(split_sentences(en), 1):
            if "“" in s and "”" in s:
                norm = re.sub(r"\s+", " ", s).strip()
                if norm in used:
                    continue
                cn_para = units[pid]["cn"]
                start = cn_para.find("“")
                end = cn_para.find("”", start + 1)
                if start >= 0 and end > start:
                    cn = cn_para[start : end + 1]
                    return {"paragraph": pid, "sentence": i, "en": s, "cn": cn}
    return None


def genre_layer(data: PilotData, aid: str, genre: str) -> dict[str, Any]:
    """Deterministic genre-aware typographic layer for Tier 2 units.

    ``article`` / ``analysis``: opening 1-2-3 takeaway bullets (``data-src``
    first sentences, verbatim, from p2..pN with numbered paragraphs first —
    never the lede).  ``opinion`` / ``editorial``: core thesis box (first
    sentence of the first post-lede paragraph) + verbatim pull quote.  Every
    element is sourced from the canonical projection; nothing is invented,
    nothing restated.
    """
    layer: dict[str, Any] = {}
    units = data.units(aid)
    used: set[str] = set()
    if genre in ("article", "analysis"):
        takeaways = []
        for pid in _numbered_first(_prose_paragraphs_after_lede(data, aid), units, 3):
            en = units[pid]["en"]
            sentences = split_sentences(en)
            if not sentences:
                continue
            used.add(re.sub(r"\s+", " ", sentences[0]).strip())
            takeaways.append({
                "cn": _cn_first_sentence(units[pid]["cn"]),
                "en": sentences[0],
                "data_src": pid,
            })
        if takeaways:
            layer["takeaways"] = takeaways
    elif genre in ("opinion", "editorial"):
        after = _prose_paragraphs_after_lede(data, aid)
        if after:
            pid = after[0]
            sentences = split_sentences(units[pid]["en"])
            if sentences:
                used.add(re.sub(r"\s+", " ", sentences[0]).strip())
                layer["thesis"] = {
                    "cn": _cn_first_sentence(units[pid]["cn"]),
                    "en": sentences[0],
                    "data_src": pid,
                }
        pq = _auto_pull_quote(data, aid, used)
        if pq:
            layer["pull_quote"] = pq
    return layer


# --- figures: photos + printed-chart companions --------------------------------

def safe_anchor_figures(data: PilotData, aid: str) -> list[dict[str, Any]]:
    """anchor_figures with a deterministic fallback for items whose inventory
    paragraphs lack native regions (anchor after the final paragraph)."""
    article = data.articles[aid]
    page_widths = {pg: n["width"] for pg, n in data.natives.items()}
    page_heights = {pg: n["height"] for pg, n in data.natives.items()}
    try:
        return anchor_figures(article, page_widths, page_heights, data.natives)
    except TracerCompilationError:
        pids = [p["id"] for p in article["paragraphs"]]
        tail = pids[-1] if pids else "p1"
        out = []
        for m in article.get("media") or []:
            if is_print_ad(m, data.natives):
                continue
            out.append({**m, "anchor": tail, "print_key": (int(m["page"]), 0, 0.0)})
        return out


def build_photo_figures(data: PilotData, aid: str, root: Path, fast: bool) -> list[dict[str, Any]]:
    """Original editorial photos woven at their natural after-pK position."""
    article = data.articles[aid]
    units = data.units(aid)
    anchored = [m for m in safe_anchor_figures(data, aid) if m.get("type") == "image"]
    figures = []
    for n, m in enumerate(anchored, 1):
        caption_cn, caption_en = "", ""
        cap_unit = units.get(f"{m['id']}-caption")
        if cap_unit:
            caption_cn, caption_en = cap_unit["cn"], cap_unit["en"]
        elif m.get("caption_en"):
            caption_en = m["caption_en"]
        else:
            caption_cn = "刊载于印刷版的照片"
            caption_en = "Photograph from the printed edition"
        webp = b"" if fast else reencode_image_file(root / m["image"], max_dim=1100)
        label_cn = f"图 {n} · {caption_cn}" if caption_cn else f"图 {n}"
        fig = (
            f'<figure class="wsj-fig" data-ref="figure:{esc(m["id"])}">'
            f'<img src="{_data_uri(webp)}" alt="{esc(caption_cn or caption_en)}">'
            f'<figcaption><span class="lang-cn">{esc(label_cn)}</span>'
            f'<span class="lang-en-block">{esc(caption_en)}</span></figcaption>'
            f'</figure>'
        )
        figures.append({
            "anchor": m["anchor"],
            "element": lxml.html.fragment_fromstring(f"<div>{fig}</div>", create_parent=False),
        })
    return figures


def build_chart_figure(cv, webp: bytes, title_cn: str) -> str:
    return (
        f'<figure class="wsj-fig" data-chart="{esc(cv.chart_id)}">'
        f'<img src="{_data_uri(webp)}" alt="{esc(title_cn)}">'
        f'<figcaption><span class="lang-cn">{esc(title_cn)}</span>'
        f'<span class="lang-en-block">{esc(cv.title_en)}</span></figcaption>'
        f'</figure>'
    )


def build_companion_element(cv, spec, series_cn: list[str], title_cn: str, data_src: str,
                            paragraph_texts: dict[str, dict[str, str]]) -> str:
    """Bilingual Chart Companion card paired with one printed chart."""
    src_texts = []
    for ref in data_src.split():
        if ref not in paragraph_texts:
            raise TracerCompilationError(f"chart-companion[{cv.chart_id}]: unknown data-src {ref}")
        src_texts.append(paragraph_texts[ref]["en"])
        src_texts.append(paragraph_texts[ref]["cn"])
    verify_element_numbers(
        f"chart-companion[{cv.chart_id}]",
        str(spec["takeaway_cn"]) + "\n" + str(spec["takeaway_en"]),
        src_texts,
        extra_grounding=[cv.grounding_text()],
    )
    series_items = "".join(
        f'<li><span class="co-term">{esc(en)}</span><span class="co-cn"> · {esc(cn)}</span></li>'
        for cn, en in zip(series_cn, cv.series_labels_en)
    )
    source_line = ""
    if cv.source_en:
        prefix = "" if cv.source_en.lower().startswith(("source", "note", "sources")) else "来源："
        source_line = f'<p class="co-src">{esc(prefix + cv.source_en)}</p>'
    return (
        f'<aside class="companion" data-src="{esc(data_src)}" data-chart="{esc(cv.chart_id)}">'
        f'<h3>图表伴读 · Chart Companion</h3>'
        f'<p class="co-title"><span class="lang-cn">{esc(title_cn)}</span>'
        f'<span class="co-en">{esc(cv.title_en)}</span></p>'
        f'<p><span class="lang-cn">{esc(str(spec["takeaway_cn"]))}</span>'
        f'<span class="lang-en-block">{esc(str(spec["takeaway_en"]))}</span></p>'
        f'<ul>{series_items}</ul>'
        f'{source_line}'
        f'</aside>'
    )


def _topic_matched_data_src(
    cv,
    takeaway_text: str,
    paragraph_texts: dict[str, dict[str, str]],
    fallback_pid: str,
) -> str:
    """Pick the paragraph that best matches the chart's Retina title/series
    keywords and numbers AND grounds the authored takeaway (Reviewer-G: the
    youth-unemployment chart anchors the unemployment-rate paragraph, not Li's
    job applications; the UnitedHealth revenue chart anchors the revenue
    paragraph, not EPS)."""
    from .whatsnews import _keywords

    chart_kw = _keywords(cv.title_en + " " + " ".join(cv.series_labels_en))
    chart_nums = {(t.value, t.kind) for t in extract_substantive_numbers(cv.grounding_text())}
    scored = []
    for pid, texts in paragraph_texts.items():
        if not re.fullmatch(r"p\d+", pid):
            continue
        para_kw = _keywords(texts["en"])
        para_nums = {(t.value, t.kind) for t in extract_substantive_numbers(texts["en"])}
        score = 2 * len(chart_kw & para_kw) + 6 * len(chart_nums & para_nums)
        scored.append((score, int(pid[1:]), pid))
    scored.sort(key=lambda s: (-s[0], s[1]))
    for score, _, pid in scored:
        if score <= 0:
            break
        if not ground_numbers(
            takeaway_text,
            [paragraph_texts[pid]["en"], paragraph_texts[pid]["cn"]],
            extra_grounding=[cv.grounding_text()],
        ):
            return pid
    return fallback_pid


def build_chart_companion_figures(data: PilotData, aid: str, pdf_path: Path,
                                  fast: bool) -> list[dict[str, Any]]:
    """Union re-crop + bilingual companion for every printed chart of a unit."""
    article = data.articles[aid]
    bilingual = data.bilingual(aid)
    para_texts = {pid: {"en": u["en"], "cn": u["cn"]} for pid, u in bilingual.items()}
    anchored = {m["id"]: m["anchor"] for m in safe_anchor_figures(data, aid) if m.get("type") == "chart"}
    figures = []
    for m in article.get("media") or []:
        if m.get("type") != "chart":
            continue
        cid = m["id"]
        native = data.natives.get(int(m["page"]))
        if native is None:
            raise TracerCompilationError(f"{aid}: chart {cid} has no native vector page")
        sibs = media_sibling_bboxes(
            article.get("media") or [], int(m["page"]), cid,
            float(native["width"]), float(native["height"]),
        )
        cv = extract_chart_vectors(native, cid, int(m["page"]), m["bbox_normalized_top_left"], sibs)
        authored = content.CHART_COMPANIONS.get(cid, {})
        if authored.get("use_authored") == "BANKS":
            spec = next(s for s in content.BANKS["companions"] if s["chart_id"] == cid)
            title_cn = content.BANKS["chart_title_cn"][cid]
            series_cn = content.BANKS["chart_series_cn"][cid]
            data_src = spec["data_src"]
            comp_spec = {"takeaway_cn": spec["takeaway_cn"], "takeaway_en": spec["takeaway_en"]}
        else:
            title_cn = str(authored.get("title_cn") or cv.title_en)
            series_cn = list(authored.get("series_cn", []))
            comp_spec = {"takeaway_cn": authored["takeaway_cn"], "takeaway_en": authored["takeaway_en"]}
            takeaway_text = str(authored["takeaway_cn"]) + "\n" + str(authored["takeaway_en"])
            fallback = str(anchored.get(cid) or next(iter(bilingual)))
            data_src = str(authored.get("data_src") or _topic_matched_data_src(cv, takeaway_text, para_texts, fallback))
        webp = b"" if fast else chart_webp(pdf_path, cv)
        anchor = anchored.get(cid) or data_src.split()[0]
        figure_html = "" if fast else build_chart_figure(cv, webp, title_cn)
        companion_html = build_companion_element(cv, comp_spec, series_cn, title_cn, data_src, para_texts)
        frag = (figure_html + companion_html) if figure_html else companion_html
        figures.append({
            "anchor": anchor,
            "element": lxml.html.fragment_fromstring(f"<div>{frag}</div>", create_parent=False),
        })
    return figures


# --- Tier 3 unit builders -------------------------------------------------------

def compose_composite_column(data: PilotData, unit_id: str) -> lxml.html.HtmlElement:
    """Merge same-page recurring short fragments into one cohesive column."""
    spec = COMPOSITES[unit_id]
    members = list(spec["members"])
    article_el = _el("article", "unit unit-tier3", data_unit=unit_id)
    head = _el("header", "unit-head")
    kicker = _el("p", "kicker")
    kicker.text = str(spec["kicker"])
    head.append(kicker)
    h1 = _el("h1")
    h1.set("data-ref", "title")
    h1.text = str(spec["title_cn"])
    en = _el("span", "lang-en-block")
    en.text = str(spec["title_en"])
    h1.append(en)
    head.append(h1)
    dek = _el("p", "dek")
    dek.text = str(spec["dek_cn"])
    head.append(dek)
    article_el.append(head)

    if spec["kind"] == "letters":
        groups: dict[str, list[str]] = {}
        for mid in members:
            groups.setdefault(data.articles[mid]["original_title"], []).append(mid)
        for title, lids in groups.items():
            shared = len(lids) > 1
            if shared:
                sh = _el("h2", "letter-group-title")
                sh.set("data-ref", f"title:{lids[0]}")
                sh.text = title
                article_el.append(sh)
            for lid in lids:
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
                sig.text = data.articles[lid].get("byline", "")
                block.append(sig)
                article_el.append(block)
    else:  # briefs: every member keeps its own title
        for mid in members:
            block = _el("section", "letter", data_letter=mid)
            title = _el("h2", "letter-title")
            title.set("data-ref", f"title:{mid}")
            title.text = data.units(mid)["title"]["cn"]
            t_en = _el("span", "letter-title-en")
            t_en.text = data.units(mid)["title"]["en"]
            title.append(t_en)
            block.append(title)
            bilingual = data.bilingual(mid)
            for pid in data.paragraph_ids(mid):
                block.append(prose_block(f"{mid}:{pid}", bilingual[pid]["cn"], bilingual[pid]["en"]))
            article_el.append(block)
    return article_el


def compose_digest(data: PilotData, links: dict[str, Any]) -> lxml.html.HtmlElement:
    """What's News: column heads + 16 bullets, each with a deep-link badge."""
    units = data.units("PILOT-A1-WHATSNEWS")
    article_el = _el("article", "unit unit-tier3", data_unit="PILOT-A1-WHATSNEWS")
    head = _el("header", "unit-head")
    kicker = _el("p", "kicker")
    kicker.text = str(TIER3_STANDALONE["PILOT-A1-WHATSNEWS"]["kicker"])
    head.append(kicker)
    h1 = _el("h1")
    h1.set("data-ref", "title")
    h1.text = units["title"]["cn"]
    en = _el("span", "lang-en-block")
    en.text = units["title"]["en"]
    h1.append(en)
    head.append(h1)
    article_el.append(head)
    body = _el("div", "unit-body digest")
    for pid in sorted(units, key=lambda p: (len(p), p)):
        if not pid.startswith("p") or pid == "title":
            continue
        if pid in HEADER_PARAGRAPHS:
            h = _el("h2", "sec-h")
            h.set("data-ref", pid)
            h_cn = _el("span", "lang-cn")
            h_cn.text = units[pid]["cn"]
            h.append(h_cn)
            h_en = _el("span", "sec-h-en")
            h_en.text = units[pid]["en"]
            h.append(h_en)
            body.append(h)
            continue
        body.append(prose_block(pid, units[pid]["cn"], units[pid]["en"]))
        link = links.get(pid)
        if link:
            body.append(lxml.html.fragment_fromstring(f"<div>{deep_link_badge(link)}</div>", create_parent=False))
    article_el.append(body)
    return article_el


def compose_brief_unit(data: PilotData, aid: str, kicker: str,
                       figures: list | None = None) -> lxml.html.HtmlElement:
    """Standalone brief (compact functional format, one paragraph)."""
    units = data.units(aid)
    article_el = _el("article", "unit unit-tier3", data_unit=aid)
    head = _el("header", "unit-head")
    k = _el("p", "kicker")
    k.text = kicker
    head.append(k)
    h1 = _el("h1")
    h1.set("data-ref", "title")
    h1.text = units["title"]["cn"]
    en = _el("span", "lang-en-block")
    en.text = units["title"]["en"]
    h1.append(en)
    head.append(h1)
    article_el.append(head)
    body = _el("div", "unit-body")
    bilingual = data.bilingual(aid)
    pids = data.paragraph_ids(aid)
    by_anchor: dict[str, list] = {}
    for fig in figures or []:
        by_anchor.setdefault(fig["anchor"], []).append(fig)
    for pid in pids:
        body.append(prose_block(pid, bilingual[pid]["cn"], bilingual[pid]["en"]))
        for fig in by_anchor.get(pid, []):
            body.append(fig["element"])
    for fig in by_anchor.get("p0", []):
        body.append(fig["element"])
    for anchor, figs in by_anchor.items():
        if anchor not in pids and anchor != "p0":
            for fig in figs:
                body.append(fig["element"])
    article_el.append(body)
    return article_el


def compose_caption_unit(data: PilotData, aid: str, kicker: str, root: Path,
                         fast: bool) -> lxml.html.HtmlElement:
    """Standalone photo caption: the verified photo with its caption."""
    units = data.units(aid)
    article_el = _el("article", "unit unit-tier3", data_unit=aid)
    head = _el("header", "unit-head")
    k = _el("p", "kicker")
    k.text = kicker
    head.append(k)
    article_el.append(head)
    body = _el("div", "unit-body")
    media = (data.articles[aid].get("media") or [None])[0]
    if media and media.get("type") == "image":
        webp = b"" if fast else reencode_image_file(root / media["image"], max_dim=1100)
        fig = (
            f'<figure class="wsj-fig" data-ref="figure:{esc(media["id"])}">'
            f'<img src="{_data_uri(webp)}" alt="{esc(units["title"]["cn"])}"></figure>'
        )
        body.append(lxml.html.fragment_fromstring(f"<div>{fig}</div>", create_parent=False))
    bilingual = data.bilingual(aid)
    for pid in data.paragraph_ids(aid):
        body.append(prose_block(pid, bilingual[pid]["cn"], bilingual[pid]["en"]))
    article_el.append(body)
    return article_el


def compose_view_only_tables(pdf_path: Path, fast: bool) -> lxml.html.HtmlElement:
    """Dense market tables stay view-only originals (no machine transcription)."""
    article_el = _el("article", "unit unit-tier3", data_unit="VIEW-MARKET-TABLES")
    head = _el("header", "unit-head")
    kicker = _el("p", "kicker")
    kicker.text = "市场数据 · MARKET DATA · B9–B13"
    head.append(kicker)
    h1 = _el("h1")
    h1.text = "市场数据"
    en = _el("span", "lang-en-block")
    en.text = "Market Data (view-only print pages)"
    h1.append(en)
    head.append(h1)
    article_el.append(head)
    body = _el("div", "unit-body")
    if not fast:
        for pg in VIEW_ONLY_TABLE_PAGES:
            pix = crop_pdf_region(pdf_path, pg, _full_page_bbox(pdf_path, pg), dpi=110)
            webp = encode_webp(pix, quality=70)
            label = f"B{pg - 18}" if pg > 18 else f"A{pg}"
            fig = (
                f'<figure class="wsj-fig view-only" data-ref="print-page:{pg}">'
                f'<img src="{_data_uri(webp)}" alt="市场数据 第{label}版">'
                f'<figcaption><span class="lang-cn">原版第 {label} 版 · 仅供查阅</span>'
                f'<span class="lang-en-block">Original print page {label} · view only</span></figcaption>'
                f'</figure>'
            )
            body.append(lxml.html.fragment_fromstring(f"<div>{fig}</div>", create_parent=False))
    article_el.append(body)
    return article_el


_FULL_PAGE_CACHE: dict[Path, dict[int, list[float]]] = {}


def _full_page_bbox(pdf_path: Path, page: int) -> list[float]:
    key = Path(pdf_path)
    if key not in _FULL_PAGE_CACHE:
        import fitz  # lazy

        doc = fitz.open(str(key))
        try:
            _FULL_PAGE_CACHE[key] = {
                i + 1: [0.0, 0.0, float(p.rect.width), float(p.rect.height)] for i, p in enumerate(doc)
            }
        finally:
            doc.close()
    return _FULL_PAGE_CACHE[key][page]


# --- unit assembly ---------------------------------------------------------------

def _unit_header_text(data: PilotData, aid: str) -> tuple[str, str]:
    units = data.units(aid)
    title = units.get("title", {"cn": "", "en": ""})
    dek = units.get("dek", {"cn": "", "en": ""})
    return title["cn"], dek["cn"]


def build_tier1_entry(data: PilotData, aid: str, route, root: Path, pdf_path: Path,
                      fast: bool) -> UnitEntry:
    authored = content.CONTENT_BY_ID.get(aid, {})
    subs, skip = inventory_subheadings(data, aid)
    for pid in authored.get("subheading_paragraphs", []):
        if pid in data.units(aid):
            u = data.units(aid)[pid]
            subs[pid] = {"cn": u["cn"], "en": u["en"], "data_src": pid}
            skip.add(pid)

    pull_quote = None
    pq = authored.get("pull_quote")
    if isinstance(pq, dict):
        pid = pq["paragraph"]
        m = int(pq["sentence"])
        en = split_sentences(data.units(aid)[pid]["en"])[m - 1]
        cn = pq.get("cn") or PULL_QUOTES_CN.get(aid)
        if cn is None:
            raise TracerCompilationError(f"{aid}: authored pull quote needs a CN rendering")
        pull_quote = {"paragraph": pid, "sentence": m, "en": en, "cn": cn}

    figures = build_photo_figures(data, aid, root, fast)
    figures += build_chart_companion_figures(data, aid, pdf_path, fast)

    # authored <wsj-chart> primitives anchored after their last data-src paragraph
    bilingual = data.bilingual(aid)
    chart_elements = []
    for spec in authored.get("wsj_charts", []):
        svg = charts.compile_wsj_chart(spec, {pid: {"en": bilingual[pid]["en"], "cn": bilingual[pid]["cn"]} for pid in bilingual})
        caption = ""
        if spec.get("caption_cn"):
            caption = (f'<p class="ch-caption"><span class="lang-cn">{esc(spec["caption_cn"])}</span>'
                       f'<span class="lang-en-block">{esc(spec.get("caption_en", ""))}</span></p>')
        el = (f'<div class="wsj-chart" data-src="{esc(spec["data_src"])}" data-chart="{esc(spec["id"])}">'
              f'{svg}{caption}</div>')
        refs = [r for r in spec["data_src"].split() if r in bilingual]
        anchor = max(refs, key=lambda r: list(bilingual).index(r))
        chart_elements.append({"anchor": anchor, "element": lxml.html.fragment_fromstring(f"<div>{el}</div>", create_parent=False)})

    unit = compose_article_unit(
        data, aid, tier=1, genre=route.genre, kicker=route.kicker,
        takeaways=authored.get("takeaways"), thesis=authored.get("thesis"),
        subheadings=subs or None, highlights=authored.get("highlights"),
        pull_quote=pull_quote, book_details=authored.get("book_details"),
        figures=figures + chart_elements, skip_prose=skip or None,
    )
    title_cn, dek_cn = _unit_header_text(data, aid)
    return UnitEntry(
        unit_id=aid, section=route.section, kicker=route.kicker, title_cn=title_cn,
        dek_cn=dek_cn, element_html=lxml.html.tostring(unit, encoding="unicode"),
        tier=1, genre=route.genre, article_ids=[aid],
    )


def build_tier2_entry(data: PilotData, aid: str, route, root: Path, pdf_path: Path,
                      fast: bool) -> UnitEntry:
    authored = content.CONTENT_BY_ID.get(aid, {})
    layer = genre_layer(data, aid, route.genre)
    subs, skip = inventory_subheadings(data, aid)
    pull_quote = authored.get("pull_quote")
    if isinstance(pull_quote, dict) and "paragraph" in pull_quote:
        pid = pull_quote["paragraph"]
        m = int(pull_quote["sentence"])
        en = split_sentences(data.units(aid)[pid]["en"])[m - 1]
        pull_quote = {"paragraph": pid, "sentence": m, "en": en, "cn": PULL_QUOTES_CN[aid]}

    body_elements = []
    if route.genre == "sidebar":
        parent = SIDEBAR_PARENT.get(aid)
        if parent and parent in data.articles:
            p_title = data.units(parent)["title"]["cn"]
            aside = _el("aside", "sidebar-link")
            aside.set("data-ref", f"related:{parent}")
            aside.text = "相关报道 · Related: "
            a_el = _el("a")
            a_el.set("href", f"#u-{parent}")
            a_el.text = p_title
            aside.append(a_el)
            body_elements.append(aside)

    figures = build_photo_figures(data, aid, root, fast)
    figures += build_chart_companion_figures(data, aid, pdf_path, fast)

    unit = compose_article_unit(
        data, aid, tier=2, genre=route.genre, kicker=route.kicker,
        takeaways=authored.get("takeaways") or layer.get("takeaways"),
        thesis=authored.get("thesis") or layer.get("thesis"),
        subheadings={**subs, **authored.get("subheadings", {})} or None,
        highlights=authored.get("highlights"),
        pull_quote=pull_quote or layer.get("pull_quote"),
        book_details=authored.get("book_details"),
        figures=figures, body_elements=body_elements or None,
        skip_prose=skip or None,
    )
    title_cn, dek_cn = _unit_header_text(data, aid)
    return UnitEntry(
        unit_id=aid, section=route.section, kicker=route.kicker, title_cn=title_cn,
        dek_cn=dek_cn, element_html=lxml.html.tostring(unit, encoding="unicode"),
        tier=2, genre=route.genre, article_ids=[aid],
    )


def build_full_units(data: PilotData, root: Path, pdf_path: Path,
                     fast: bool = False) -> list[UnitEntry]:
    """Compile every Tier 1/2/3 unit of the issue; zero silent tier fallback."""
    routes = route_issue(data.articles)
    composite_members = {m for spec in COMPOSITES.values() for m in spec["members"]}
    links = resolve_whatsnews(data, composite_members)

    def print_order(route):
        article = data.articles[route.article_ids[0]]
        page = int(article.get("start_page") or article["all_pages"][0])
        return (page, route.tier, route.unit_id)

    entries: list[UnitEntry] = []
    for route in sorted(routes, key=print_order):
        if route.tier == 1:
            entries.append(build_tier1_entry(data, route.article_ids[0], route, root, pdf_path, fast))
        elif route.tier == 2:
            entries.append(build_tier2_entry(data, route.article_ids[0], route, root, pdf_path, fast))
        elif route.unit_id in COMPOSITES:
            element = compose_composite_column(data, route.unit_id)
            spec = COMPOSITES[route.unit_id]
            entries.append(UnitEntry(
                unit_id=route.unit_id, section=route.section, kicker=route.kicker,
                title_cn=str(spec["title_cn"]), dek_cn=str(spec["dek_cn"]),
                element_html=lxml.html.tostring(element, encoding="unicode"),
                tier=3, genre=route.genre, article_ids=list(route.article_ids),
            ))
        elif route.unit_id == "PILOT-A1-WHATSNEWS":
            element = compose_digest(data, links)
            title_cn, _ = _unit_header_text(data, route.unit_id)
            entries.append(UnitEntry(
                unit_id=route.unit_id, section=route.section, kicker=route.kicker,
                title_cn=title_cn, dek_cn="",
                element_html=lxml.html.tostring(element, encoding="unicode"),
                tier=3, genre="digest", article_ids=[route.unit_id],
            ))
        elif route.genre == "brief":
            figures = build_chart_companion_figures(data, route.unit_id, pdf_path, fast)
            element = compose_brief_unit(data, route.unit_id, route.kicker, figures)
            title_cn, _ = _unit_header_text(data, route.unit_id)
            entries.append(UnitEntry(
                unit_id=route.unit_id, section=route.section, kicker=route.kicker,
                title_cn=title_cn, dek_cn="",
                element_html=lxml.html.tostring(element, encoding="unicode"),
                tier=3, genre="brief", article_ids=[route.unit_id],
            ))
        elif route.genre == "photo_caption":
            element = compose_caption_unit(data, route.unit_id, route.kicker, root, fast)
            title_cn, _ = _unit_header_text(data, route.unit_id)
            entries.append(UnitEntry(
                unit_id=route.unit_id, section=route.section, kicker=route.kicker,
                title_cn=title_cn, dek_cn="",
                element_html=lxml.html.tostring(element, encoding="unicode"),
                tier=3, genre="photo_caption", article_ids=[route.unit_id],
            ))
        else:
            raise TracerCompilationError(f"no Tier 3 builder for route {route.unit_id}")

    # View-only market table pages (compact functional format).
    tables_el = compose_view_only_tables(pdf_path, fast)
    entries.append(UnitEntry(
        unit_id="VIEW-MARKET-TABLES", section="markets",
        kicker="市场数据 · MARKET DATA", title_cn="市场数据",
        dek_cn="股市、债市与利率参考表原版页面，仅供查阅。",
        element_html=lxml.html.tostring(tables_el, encoding="unicode"),
        tier=3, genre="tables", article_ids=[],
    ))
    return entries
