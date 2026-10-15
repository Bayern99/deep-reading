#!/usr/bin/env python3
"""WSJ 深读 · Vertical Tracer CLI — compile the 2026-10-14 pilot Issue Artifact.

Usage:
    /opt/homebrew/bin/python3 render/tracer_pipeline.py [--output PATH]

Requires the pilot dataset and the original print PDF (see
``render/tracer/compose.py`` for the pinned paths and PDF SHA256).  Emits a
single self-contained HTML artifact with the five representative reading units:
PILOT-A1-BANKS, PILOT-A1-CONDO, PILOT-A1-NAVY, PILOT-A15-EDGEWORTH,
PILOT-A16-WEALTH and the COMPOSITE-A16-LETTERS column.
"""
from __future__ import annotations

import argparse
import base64
import html
import sys
from pathlib import Path

import lxml.html

sys.path.insert(0, str(Path(__file__).resolve().parent))

from tracer import charts, content
from tracer.compose import (
    LETTERS_PAGE16,
    PDF_PATH,
    PILOT_ROOT,
    anchor_figures,
    composite_letters_unit,
    compose_article_unit,
    load_pilot_data,
)
from tracer.shell import UnitEntry, build_issue_artifact
from tracer.vector import (
    chart_webp,
    crop_pdf_region,
    encode_webp,
    esc,
    extract_chart_vectors,
    reencode_image_file,
)
from tracer.verify import TracerCompilationError, split_sentences, verify_element_numbers

ISSUE_DATE_CN = "2026年10月14日 · 星期三"
ISSUE_DATE_EN = "Wednesday, October 14, 2026"
FRONT_DEK_CN = "利率阴影笼罩华尔街大行；比弗利山庄的豪宅项目向买家借钱；加州财富税公投逼近。"
DEFAULT_OUTPUT = "/tmp/wsj-2026-10-14-tracer.html"


def _data_uri(webp: bytes) -> str:
    return "data:image/webp;base64," + base64.b64encode(webp).decode("ascii")


def _bilingual_span(cn: str, en: str, en_cls: str = "lang-en-block") -> str:
    return f"<span class=\"lang-cn\">{esc(cn)}</span><span class=\"{en_cls}\">{esc(en)}</span>"


def build_companion_element(cv, spec, series_cn: list[str], title_cn: str, data_src: str,
                            paragraph_texts: dict[str, dict[str, str]]) -> str:
    """Bilingual Chart Companion card paired with one printed chart."""
    src_texts = []
    for ref in data_src.split():
        src_texts.append(paragraph_texts[ref]["en"])
        src_texts.append(paragraph_texts[ref]["cn"])
    verify_element_numbers(
        f"chart-companion[{cv.chart_id}]",
        spec["takeaway_cn"] + "\n" + spec["takeaway_en"],
        src_texts,
        extra_grounding=[cv.grounding_text()],
    )
    # The reader looks at an English printed chart, so the series key pairs the
    # English chart term with its Chinese translation (Citigroup · 花旗集团);
    # EN mode shows the chart term only.
    series_items = "".join(
        f'<li><span class="co-term">{esc(en)}</span><span class="co-cn"> · {esc(cn)}</span></li>'
        for cn, en in zip(series_cn, cv.series_labels_en)
    )
    source_line = ""
    if cv.source_en:
        source_line = f'<p class="co-src">{esc("来源：" + cv.source_en)}</p>'
    return (
        f'<aside class="companion" data-src="{esc(data_src)}" data-chart="{esc(cv.chart_id)}">'
        f'<h3>图表伴读 · Chart Companion</h3>'
        f'<p class="co-title"><span class="lang-cn">{esc(title_cn)}</span><span class="co-en">{esc(cv.title_en)}</span></p>'
        f'<p>{_bilingual_span(spec["takeaway_cn"], spec["takeaway_en"])}</p>'
        f'<ul>{series_items}</ul>'
        f'{source_line}'
        f'</aside>'
    )


def build_chart_figure(cv, webp: bytes, title_cn: str) -> str:
    return (
        f'<figure class="wsj-fig" data-chart="{esc(cv.chart_id)}">'
        f'<img src="{_data_uri(webp)}" alt="{esc(title_cn)}">'
        f'<figcaption><span class="lang-cn">{esc(title_cn)}</span>'
        f'<span class="lang-en-block">{esc(cv.title_en)}</span></figcaption>'
        f'</figure>'
    )


def build_wsj_chart_element(spec: dict, paragraph_texts: dict[str, dict[str, str]]) -> str:
    svg = charts.compile_wsj_chart(spec, paragraph_texts)
    caption = ""
    if spec.get("caption_cn"):
        caption = f'<p class="ch-caption">{_bilingual_span(spec["caption_cn"], spec.get("caption_en", ""))}</p>'
    return (
        f'<div class="wsj-chart" data-src="{esc(spec["data_src"])}" data-chart="{esc(spec["id"])}">'
        f'{svg}'
        f'{caption}'
        f'</div>'
    )


def build_photo_figure(anchor_id: str, img_bytes: bytes, caption_cn: str, caption_en: str,
                       n: int) -> str:
    return (
        f'<figure class="wsj-fig" data-ref="figure:{anchor_id}">'
        f'<img src="{_data_uri(img_bytes)}" alt="{esc(caption_cn)}">'
        f'<figcaption><span class="lang-cn">图 {n} · {esc(caption_cn)}</span>'
        f'<span class="lang-en-block">{esc(caption_en)}</span></figcaption>'
        f'</figure>'
    )


def build_units(data, root: Path, pdf_path: Path, fast: bool = False) -> list[UnitEntry]:
    entries: list[UnitEntry] = []
    page_widths = {pg: n["width"] for pg, n in data.natives.items()}
    page_heights = {pg: n["height"] for pg, n in data.natives.items()}

    # --- PILOT-A1-BANKS: printed charts, union re-crop + companions ----------
    banks = data.articles["PILOT-A1-BANKS"]
    bilingual = data.bilingual("PILOT-A1-BANKS")
    para_texts = {pid: {"en": bilingual[pid]["en"], "cn": bilingual[pid]["cn"]} for pid in bilingual}
    native2 = data.natives[2]
    anchors = {m["id"]: m["anchor"] for m in anchor_figures(banks, page_widths, page_heights, data.natives)}
    figures = []
    for spec in content.BANKS["companions"]:
        cid = spec["chart_id"]
        media = next(m for m in banks["media"] if m["id"] == cid)
        cv = extract_chart_vectors(native2, cid, int(media["page"]), media["bbox_normalized_top_left"])
        webp = b"" if fast else chart_webp(pdf_path, cv)
        anchor = spec["anchor"] or anchors[cid]
        figure_html = "" if fast else build_chart_figure(cv, webp, content.BANKS["chart_title_cn"][cid])
        companion_html = build_companion_element(
            cv, spec, content.BANKS["chart_series_cn"][cid],
            content.BANKS["chart_title_cn"][cid], spec["data_src"], para_texts,
        )
        frag = (figure_html + companion_html) if figure_html else companion_html
        container = lxml.html.fragment_fromstring(f"<div>{frag}</div>", create_parent=False)
        figures.append({"anchor": anchor, "element": container})
    unit = compose_article_unit(
        data, "PILOT-A1-BANKS", tier=1, genre="article",
        kicker=content.BANKS["kicker"], takeaways=content.BANKS["takeaways"],
        highlights=content.BANKS["highlights"], figures=figures,
    )
    entries.append(UnitEntry(
        unit_id="PILOT-A1-BANKS", section="a1", kicker=content.BANKS["kicker"],
        title_cn=data.translations["PILOT-A1-BANKS"]["title"]["cn"],
        dek_cn=data.translations["PILOT-A1-BANKS"].get("dek", {}).get("cn", ""),
        element_html=lxml.html.tostring(unit, encoding="unicode"),
        tier=1, genre="article",
    ))

    # --- PILOT-A1-CONDO: <wsj-chart> primitives --------------------------------
    chart_elements = []
    for spec in content.CONDO["wsj_charts"]:
        chart_elements.append(build_wsj_chart_element(spec, para_texts_condo(data)))
    # charts attach after their last data-src paragraph
    charts_by_anchor = {}
    b_condo = data.bilingual("PILOT-A1-CONDO")
    for spec, el in zip(content.CONDO["wsj_charts"], chart_elements):
        refs = [r for r in spec["data_src"].split() if r in b_condo]
        anchor = max(refs, key=lambda r: int(r[1:]))
        charts_by_anchor.setdefault(anchor, []).append(el)
    figures = [{"anchor": a, "element": lxml.html.fragment_fromstring(f"<div>{e}</div>", create_parent=False)}
               for a, els in charts_by_anchor.items() for e in els]
    unit = compose_article_unit(
        data, "PILOT-A1-CONDO", tier=1, genre="article",
        kicker=content.CONDO["kicker"], takeaways=content.CONDO["takeaways"],
        subheadings=content.CONDO["subheadings"], highlights=content.CONDO["highlights"],
        figures=figures,
    )
    entries.append(UnitEntry(
        unit_id="PILOT-A1-CONDO", section="us", kicker=content.CONDO["kicker"],
        title_cn=data.translations["PILOT-A1-CONDO"]["title"]["cn"],
        dek_cn=data.translations["PILOT-A1-CONDO"].get("dek", {}).get("cn", ""),
        element_html=lxml.html.tostring(unit, encoding="unicode"),
        tier=1, genre="article",
    ))

    # --- PILOT-A1-NAVY: natural after-pK figure anchoring ----------------------
    navy = data.articles["PILOT-A1-NAVY"]
    figures = []
    for n, m in enumerate(anchor_figures(navy, page_widths, page_heights, data.natives), 1):
        img_path = root / next(mm["image"] for mm in navy["media"] if mm["id"] == m["id"])
        webp = b"" if fast else reencode_image_file(img_path)
        fig = build_photo_figure(
            m["id"], webp, content.NAVY["figure_caption_cn"], content.NAVY["figure_caption_en"], n
        )
        figures.append({
            "anchor": m["anchor"],
            "element": lxml.html.fragment_fromstring(f"<div>{fig}</div>", create_parent=False),
        })
    unit = compose_article_unit(
        data, "PILOT-A1-NAVY", tier=1, genre="article",
        kicker=content.NAVY["kicker"], figures=figures,
    )
    entries.append(UnitEntry(
        unit_id="PILOT-A1-NAVY", section="us", kicker=content.NAVY["kicker"],
        title_cn=data.translations["PILOT-A1-NAVY"]["title"]["cn"],
        dek_cn=data.translations["PILOT-A1-NAVY"].get("dek", {}).get("cn", ""),
        element_html=lxml.html.tostring(unit, encoding="unicode"),
        tier=1, genre="article",
    ))

    # --- PILOT-A15-EDGEWORTH: genre-aware Tier 2 review -------------------------
    edgeworth_media = data.articles["PILOT-A15-EDGEWORTH"]["media"][0]
    edgeworth_fig = None
    if not fast:
        webp = reencode_image_file(root / edgeworth_media["image"])
        cap_cn = content.EDGEWORTH["figure_caption_cn"]
        cap_en = content.EDGEWORTH["figure_caption_en"]
        edgeworth_fig = [{
            "anchor": "p2",
            "element": lxml.html.fragment_fromstring(
                f"<div>{build_photo_figure(edgeworth_media['id'], webp, cap_cn, cap_en, 1)}</div>",
                create_parent=False,
            ),
        }]
    unit = compose_article_unit(
        data, "PILOT-A15-EDGEWORTH", tier=2, genre="review",
        kicker=content.EDGEWORTH["kicker"], book_details=content.EDGEWORTH["book_details"],
        subheadings=content.EDGEWORTH["subheadings"], highlights=content.EDGEWORTH["highlights"],
        figures=edgeworth_fig or [],
    )
    entries.append(UnitEntry(
        unit_id="PILOT-A15-EDGEWORTH", section="opinion", kicker=content.EDGEWORTH["kicker"],
        title_cn=data.translations["PILOT-A15-EDGEWORTH"]["title"]["cn"],
        dek_cn=data.translations["PILOT-A15-EDGEWORTH"].get("dek", {}).get("cn", ""),
        element_html=lxml.html.tostring(unit, encoding="unicode"),
        tier=2, genre="review",
    ))

    # --- PILOT-A16-WEALTH: genre-aware Tier 2 editorial -------------------------
    b_wealth = data.bilingual("PILOT-A16-WEALTH")
    s1 = split_sentences(b_wealth["p2"]["en"])[0]
    pull_quote = {
        "paragraph": "p2",
        "sentence": 1,
        "en": s1,
        "cn": "“整个国家，甚至全世界的人们都在密切关注这里发生的一切。”",
    }
    if pull_quote["cn"].strip("“”") not in b_wealth["p2"]["cn"]:
        raise TracerCompilationError("WEALTH pull quote CN sentence not found in reviewed translation")
    unit = compose_article_unit(
        data, "PILOT-A16-WEALTH", tier=2, genre="editorial",
        kicker=content.WEALTH["kicker"], thesis=content.WEALTH["thesis"],
        subheadings=content.WEALTH["subheadings"], pull_quote=pull_quote,
        highlights=content.WEALTH["highlights"],
    )
    entries.append(UnitEntry(
        unit_id="PILOT-A16-WEALTH", section="opinion", kicker=content.WEALTH["kicker"],
        title_cn=data.translations["PILOT-A16-WEALTH"]["title"]["cn"],
        dek_cn=data.translations["PILOT-A16-WEALTH"].get("dek", {}).get("cn", ""),
        element_html=lxml.html.tostring(unit, encoding="unicode"),
        tier=2, genre="editorial",
    ))

    # --- COMPOSITE-A16-LETTERS: Tier 3 composite column --------------------------
    composite = composite_letters_unit(data, LETTERS_PAGE16)
    entries.append(UnitEntry(
        unit_id="COMPOSITE-A16-LETTERS", section="opinion", kicker="来信 · LETTERS · A16",
        title_cn="读者来信",
        dek_cn="读者就柴油计划、教育创新、审批改革与和平奖评选发声。",
        element_html=lxml.html.tostring(composite, encoding="unicode"),
        tier=3, genre="letters",
    ))

    return entries


def para_texts_condo(data):
    b = data.bilingual("PILOT-A1-CONDO")
    return {pid: {"en": b[pid]["en"], "cn": b[pid]["cn"]} for pid in b}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Compile the 2026-10-14 vertical tracer Issue Artifact")
    ap.add_argument("--output", default=DEFAULT_OUTPUT)
    ap.add_argument("--fast", action="store_true", help="skip PDF raster work (smoke)")
    args = ap.parse_args(argv)

    data = load_pilot_data()
    entries = build_units(data, PILOT_ROOT, PDF_PATH, fast=args.fast)
    doc = build_issue_artifact(
        date_cn=ISSUE_DATE_CN, date_en=ISSUE_DATE_EN, units=entries,
        front_dek_cn=FRONT_DEK_CN,
    )
    out = Path(args.output)
    out.write_text(doc, "utf-8")
    print(f"artifact: {out} ({out.stat().st_size} bytes, {len(entries)} units)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
