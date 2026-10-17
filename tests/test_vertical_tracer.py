"""Vertical Tracer acceptance tests — Ticket 1 (GitHub Issue #2).

Run with the system interpreter (has fitz/PIL):
    /opt/homebrew/bin/python3 -m unittest tests/test_vertical_tracer.py -v

The pinned pilot dataset is required: when it is absent these tests fail
rather than skip, so `make test` cannot report OK without checking the
product (set WSJ_ALLOW_MISSING_PILOT=1 to skip the data-backed classes
instead). PyMuPDF/PIL absent is a separate, legitimate skip.
"""
from __future__ import annotations

import hashlib
import os
import re
import sys
import unittest
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "render"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from pilot_prereq import require_pilot  # noqa: E402

from tracer import charts, content  # noqa: E402
from tracer.compose import (  # noqa: E402
    LETTERS_PAGE16,
    PDF_PATH,
    PILOT_ROOT,
    anchor_figures,
    composite_letters_unit,
    compose_article_unit,
    is_print_ad,
    load_pilot_data,
)
from tracer.shell import SECTIONS, build_issue_artifact  # noqa: E402
from tracer.vector import (  # noqa: E402
    chart_webp,
    extract_chart_vectors,
    load_native,
)
from tracer.verify import (  # noqa: E402
    FORBIDDEN_STRINGS,
    TracerCompilationError,
    assert_no_forbidden_strings,
    check_highlight_density,
    ground_numbers,
    surgical_narrative_completion,
    split_sentences,
    verify_element_numbers,
    verify_quote_anchor,
)

try:
    import fitz  # noqa: F401
    HAS_FITZ = True
except ImportError:
    HAS_FITZ = False
try:
    from PIL import Image  # noqa: F401
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

HAS_DATA = require_pilot()

BANKS_BOXES = {
    "p02-b78": [0.198, 0.736, 0.415, 0.822],
    "p02-b83": [0.43, 0.705, 0.646, 0.823],
}


@unittest.skipUnless(HAS_DATA, "2026-10-14 pilot dataset not present")
class TracerDataTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = load_pilot_data()
        cls.page_widths = {pg: n["width"] for pg, n in cls.data.natives.items()}
        cls.page_heights = {pg: n["height"] for pg, n in cls.data.natives.items()}
        cls.native2 = load_native(PILOT_ROOT / "evidence" / "p02-native.json")


class ChartVectorUnionCheck(TracerDataTestCase):
    """Union re-crop + companion recovery for p02-b78 / p02-b83."""

    def test_titles_and_sources_recovered(self):
        expect = {
            "p02-b78": {
                "title": "Fixed-income, currencies and commodities revenue, by bank",
                "source": "Source: the companies",
                "series": ["Wells Fargo", "Citigroup", "Goldman Sachs", "JPMorgan Chase"],
            },
            "p02-b83": {
                "title": "Third-quarter net proﬁt",
                "source": "",  # none printed below this chart
                "series": ["JPMorgan Chase", "Wells Fargo", "Goldman Sachs", "Citigroup"],
            },
        }
        for cid, box in BANKS_BOXES.items():
            cv = extract_chart_vectors(self.native2, cid, 2, box)
            self.assertEqual(cv.title_en, expect[cid]["title"], f"{cid} title")
            self.assertEqual(cv.source_en, expect[cid]["source"], f"{cid} source")
            self.assertEqual(cv.series_labels_en, expect[cid]["series"], f"{cid} series")
            # 100% of adjacent RetinaMedium title lines are inside the union.
            for line in self.native2["lines"]:
                text = re.sub(r"\s+", " ", line.get("text", "")).strip()
                font = (line.get("chars") or [{}])[0].get("font", "")
                if not text or not font.startswith("RetinaMedium"):
                    continue
                y0 = line["bbox"][1] / self.native2["height"]
                x_mid = (line["bbox"][0] + line["bbox"][2]) / 2 / self.native2["width"]
                if box[0] <= x_mid <= box[2] and 0.68 < y0 < 0.75:
                    self.assertIn(text, cv.retina_lines, f"{cid} missing title line {text!r}")

    def test_union_bbox_covers_chopped_lines(self):
        # p02-b78's inventory bbox chopped title (y=0.707) and source (y=0.825).
        cv = extract_chart_vectors(self.native2, "p02-b78", 2, BANKS_BOXES["p02-b78"])
        self.assertLessEqual(cv.union_bbox_norm[1], 0.707)
        self.assertGreaterEqual(cv.union_bbox_norm[3], 0.829)
        # union must contain the original inventory bbox
        self.assertLessEqual(cv.union_bbox_norm[0], 0.198)
        self.assertGreaterEqual(cv.union_bbox_norm[2], 0.415)

    def test_union_crop_webp(self):
        if not (HAS_FITZ and HAS_PIL):
            self.skipTest("fitz/PIL not available")
        for cid, box in BANKS_BOXES.items():
            cv = extract_chart_vectors(self.native2, cid, 2, box)
            webp = chart_webp(PDF_PATH, cv)
            self.assertTrue(webp[:4] == b"RIFF", f"{cid} is not WebP")
            self.assertGreater(len(webp), 8000, f"{cid} crop too small to be reading-grade")


class FigureNarrativeMonotonicityCheck(TracerDataTestCase):
    """PILOT-A1-NAVY: editorial figures woven across chapters in print order."""

    def test_anchors_monotonic_and_woven(self):
        navy = self.data.articles["PILOT-A1-NAVY"]
        anchored = anchor_figures(navy, self.page_widths, self.page_heights, self.data.natives)
        # p06-b60 is a Feeding America / Ad Council PSA, not an editorial figure
        self.assertEqual(len(anchored), 7)
        self.assertNotIn("p06-b60", [m["id"] for m in anchored])
        # print order == sorted by print key (column-major)
        keys = [m["print_key"] for m in anchored]
        self.assertEqual(keys, sorted(keys), "figures must follow physical print order")
        anchors = [int(m["anchor"][1:]) if m["anchor"] != "p0" else 0 for m in anchored]
        self.assertEqual(anchors, sorted(anchors), "after-pK anchors must be monotonic")
        # at most 1 lead figure before p2; never stacked before p1
        before_p2 = [a for a in anchors if a < 2]
        self.assertLessEqual(len(before_p2), 1, "at most one figure before p2")
        # woven across the 34-paragraph story, not dumped at the head
        self.assertGreater(anchors[-1], 20, "figures must reach deep into the story")
        self.assertGreaterEqual(len(set(anchors)), 2, "figures must span multiple chapters")

    def test_print_ad_detection(self):
        navy = self.data.articles["PILOT-A1-NAVY"]
        by_id = {m["id"]: m for m in navy["media"]}
        self.assertTrue(is_print_ad(by_id["p06-b60"], self.data.natives))
        self.assertFalse(is_print_ad(by_id["p06-b76"], self.data.natives))
        self.assertFalse(is_print_ad(by_id["p06-b80"], self.data.natives))

    def test_chart_companions_anchor_in_print_order(self):
        banks = self.data.articles["PILOT-A1-BANKS"]
        anchored = {m["id"]: m["anchor"] for m in anchor_figures(banks, self.page_widths, self.page_heights, self.data.natives)}
        self.assertEqual(set(anchored), {"p02-b78", "p02-b83"})
        k78 = int(anchored["p02-b78"][1:])
        k83 = int(anchored["p02-b83"][1:])
        self.assertLess(k78, k83, "b78 sits left of b83 on the printed page")


class WsjChartCompileCheck(TracerDataTestCase):
    """Declarative <wsj-chart> compiler: valid SVG + 100% data-src grounding."""

    def setUp(self):
        b = self.data.bilingual("PILOT-A1-CONDO")
        self.para_texts = {pid: {"en": b[pid]["en"], "cn": b[pid]["cn"]} for pid in b}

    def test_all_four_types_compile(self):
        types = set()
        for spec in content.CONDO["wsj_charts"]:
            svg = charts.compile_wsj_chart(spec, self.para_texts)
            types.add(spec["type"])
            self.assertIn("viewBox=", svg)
            self.assertIn('width="100%"', svg)
            vb = re.search(r'viewBox="0 0 (\d+) (\d+)"', svg)
            w, h = int(vb.group(1)), int(vb.group(2))
            # clip-free: every x/y coordinate stays inside the viewBox
            for x in re.findall(r'x="([\d.]+)"', svg):
                self.assertLessEqual(float(x), w + 1)
            for y in re.findall(r'y="([\d.]+)"', svg):
                self.assertLessEqual(float(y), h + 1)
            # clip-free text: estimated rendered width of every <text> node,
            # including CJK width, stays inside [0, viewBox_width]
            import html as html_mod
            for m in charts._TEXT_RE.finditer(svg):
                x = float(m.group(1))
                attrs = m.group(3)
                size = int(re.search(r'font-size="(\d+)"', attrs).group(1))
                anchor_m = re.search(r'text-anchor="(\w+)"', attrs)
                anchor = anchor_m.group(1) if anchor_m else "start"
                text = html_mod.unescape(re.sub(r"<[^>]+>", "", m.group(4)))
                tw = charts._est_text_width(text, size)
                left = x - (tw / 2 if anchor == "middle" else tw if anchor == "end" else 0.0)
                right = x + (tw / 2 if anchor == "middle" else 0.0 if anchor == "end" else tw)
                self.assertGreaterEqual(left, -1.0, f"{spec['id']} text {text[:24]!r} left edge")
                self.assertLessEqual(right, w + 1.0, f"{spec['id']} text {text[:24]!r} right edge")
        self.assertEqual(types, {"comparison", "flow", "timeline", "matrix"})

    def test_grounding_rejects_invented_number(self):
        spec = {
            "id": "bad", "type": "comparison", "title_cn": "x", "title_en": "y",
            "data_src": "p14",
            "items": [
                {"label_cn": "已募集", "label_en": "Raised", "value": 412000000,
                 "display_cn": "4.12亿美元", "display_en": "$41.2 million", "emphasis": False},
            ],
        }
        with self.assertRaises(TracerCompilationError):
            charts.compile_wsj_chart(spec, self.para_texts)

    def test_bar_value_must_match_display_label(self):
        # scale/display divergence: bar says 1.6e9 but the label says 350M
        spec = {
            "id": "skew", "type": "comparison", "title_cn": "x", "title_en": "y",
            "data_src": "p14",
            "items": [
                {"label_cn": "已募集", "label_en": "Raised", "value": 1600000000,
                 "display_cn": "约3.5亿美元", "display_en": "~$350 million", "emphasis": False},
            ],
        }
        with self.assertRaises(TracerCompilationError):
            charts.compile_wsj_chart(spec, self.para_texts)

    def test_caption_numbers_are_grounded(self):
        spec = {
            "id": "badcap", "type": "matrix", "title_cn": "x", "title_en": "y",
            "data_src": "p5 p7",
            "caption_cn": "收益率一度达到9.99%。",
            "caption_en": "Yields reached 9.99%.",
            "cols": [{"label_cn": "A", "label_en": "A"}, {"label_cn": "B", "label_en": "B"}],
            "rows": [{"label_cn": "r", "label_en": "r", "cells": [{"cn": "5%", "en": "5%", "emphasis": False}, {"cn": "-", "en": "-"}]}],
        }
        with self.assertRaises(TracerCompilationError):
            charts.compile_wsj_chart(spec, self.para_texts)

    def test_comparison_bars_exactly_proportional(self):
        spec = next(s for s in content.CONDO["wsj_charts"] if s["type"] == "comparison")
        svg = charts.compile_wsj_chart(spec, self.para_texts)
        bars = [float(m) for m in re.findall(r'<rect x="[\d.]+" y="[\d.]+" width="([\d.]+)" height="22" fill="#(?:111111|fa9000)"/>', svg)]
        self.assertEqual(len(bars), 2)
        ratio = bars[0] / bars[1]
        self.assertAlmostEqual(ratio, 350000000 / 1600000000, places=3)


class CompositeColumnCheck(TracerDataTestCase):
    """All 9 page-16 letters merge with 100% verbatim paragraph conservation."""

    def test_nine_letters_merged_verbatim(self):
        unit = composite_letters_unit(self.data, LETTERS_PAGE16)
        letters = unit.xpath(".//section[contains(@class,'letter')]")
        self.assertEqual(len(letters), 9)
        # shared sub-header for the 5 diesel letters, once
        group_titles = unit.xpath(".//*[contains(@class,'letter-group-title')]")
        self.assertEqual(len(group_titles), 1)
        self.assertEqual(group_titles[0].text, "Readers Revolt Against Trump’s Diesel Plan")
        # verbatim paragraph conservation per letter, CN and EN
        total = 0
        for lid in LETTERS_PAGE16:
            bilingual = self.data.bilingual(lid)
            expected = self.data.paragraph_ids(lid)
            total += len(expected)
            got_cn, got_en = [], []
            for pid in expected:
                ref = f"{lid}:{pid}"
                spans = unit.xpath(f".//p[@data-ref='{ref}']/span")
                self.assertEqual(len(spans), 2, f"{ref} missing bilingual spans")
                got_cn.append(spans[0].text or "")
                got_en.append(spans[1].text or "")
            src_cn = "\n\n".join(bilingual[p]["cn"] for p in expected)
            src_en = "\n\n".join(bilingual[p]["en"] for p in expected)
            self.assertEqual(
                hashlib.sha256("\n\n".join(got_cn).encode()).hexdigest(),
                hashlib.sha256(src_cn.encode()).hexdigest(),
                f"{lid} CN paragraphs not verbatim",
            )
            self.assertEqual(
                hashlib.sha256("\n\n".join(got_en).encode()).hexdigest(),
                hashlib.sha256(src_en.encode()).hexdigest(),
                f"{lid} EN paragraphs not verbatim",
            )
        self.assertEqual(total, 21)


class NarrativeConservationCheck(TracerDataTestCase):
    """CN + EN narrative matches source in count, order and SHA256 (diff == 0)."""

    UNITS = ["PILOT-A1-BANKS", "PILOT-A1-CONDO", "PILOT-A1-NAVY", "PILOT-A15-EDGEWORTH", "PILOT-A16-WEALTH"]

    def _roundtrip(self, unit_el, article_id):
        pids = self.data.paragraph_ids(article_id)
        rows = unit_el.xpath(".//p[@data-ref and contains(@class,'prose-p')]")
        self.assertEqual(len(rows), len(pids), f"{article_id} paragraph count")
        got = {"cn": [], "en": []}
        for row, pid in zip(rows, pids):
            self.assertEqual(row.get("data-ref"), pid, f"{article_id} paragraph order")
            spans = row.xpath("./span")
            self.assertEqual(len(spans), 2)
            got["cn"].append(spans[0].text_content())
            got["en"].append(spans[1].text_content())
        bilingual = self.data.bilingual(article_id)
        for lang, key in (("cn", "cn"), ("en", "en")):
            src = "\n\n".join(bilingual[p][key] for p in pids)
            self.assertEqual(
                hashlib.sha256("\n\n".join(got[lang]).encode()).hexdigest(),
                hashlib.sha256(src.encode()).hexdigest(),
                f"{article_id} {lang} narrative diverged",
            )

    def test_five_reading_units_conserve_narrative(self):
        for aid in self.UNITS:
            with self.subTest(unit=aid):
                unit = compose_article_unit(self.data, aid, tier=1, genre="article", kicker="K")
                self._roundtrip(unit, aid)


class GenreAwareTier2Check(TracerDataTestCase):
    def test_review_metadata_and_pacing(self):
        unit = compose_article_unit(
            self.data, "PILOT-A15-EDGEWORTH", tier=2, genre="review",
            kicker=content.EDGEWORTH["kicker"], book_details=content.EDGEWORTH["book_details"],
            subheadings=content.EDGEWORTH["subheadings"], highlights=content.EDGEWORTH["highlights"],
        )
        self.assertIsNotNone(unit.xpath(".//aside[contains(@class,'book-details')]"))
        self.assertEqual(len(unit.xpath(".//h2[contains(@class,'sec-h')]")), 3)
        density = check_highlight_density(unit)
        self.assertLessEqual(density, 0.12)

    def test_editorial_thesis_pullquote_no_bullets(self):
        b = self.data.bilingual("PILOT-A16-WEALTH")
        s1 = split_sentences(b["p2"]["en"])[0]
        unit = compose_article_unit(
            self.data, "PILOT-A16-WEALTH", tier=2, genre="editorial",
            kicker=content.WEALTH["kicker"], thesis=content.WEALTH["thesis"],
            subheadings=content.WEALTH["subheadings"],
            pull_quote={"paragraph": "p2", "sentence": 1, "en": s1, "cn": "“整个国家，甚至全世界的人们都在密切关注这里发生的一切。”"},
            highlights=content.WEALTH["highlights"],
        )
        self.assertIsNotNone(unit.xpath(".//div[contains(@class,'thesis-box')]"))
        pq = unit.xpath(".//blockquote[contains(@class,'pull-quote')]")
        self.assertEqual(len(pq), 1)
        self.assertEqual(pq[0].get("data-ref"), "p2.s1")
        # opinion editorials carry no mechanical 1-2-3 takeaway bullets
        self.assertEqual(unit.xpath(".//ul[contains(@class,'takeaways')]"), [])
        density = check_highlight_density(unit)
        self.assertLessEqual(density, 0.12)


class HistoricalFaultInjectionRecallCheck(TracerDataTestCase):
    """(a)-(f): the historical failure modes must be detected deterministically."""

    def test_a_ungrounded_chart_takeaway_number(self):
        # 4.12% where the paragraph says 5%
        p1 = self.data.bilingual("PILOT-A16-WEALTH")["p1"]
        with self.assertRaises(TracerCompilationError):
            verify_element_numbers("takeaway", "提案将征收4.12%的税", [p1["en"], p1["cn"]])
        # control: the grounded 5% passes
        verify_element_numbers("takeaway", "提案将征收5%的税", [p1["en"], p1["cn"]])

    def test_b_fabricated_quote_not_in_pK(self):
        p1 = self.data.bilingual("PILOT-A16-WEALTH")["p1"]["en"]
        with self.assertRaises(TracerCompilationError):
            verify_quote_anchor(p1, 1, "This sentence appears nowhere in the source paragraph.")
        # control: verbatim sentence 1 passes
        verify_quote_anchor(p1, 1, split_sentences(p1)[0])

    def test_c_magnitude_mismatch_cross_language(self):
        src = ["Cain has raised around $700 million through this approach."]
        self.assertEqual(ground_numbers("Cain已通过这一方式募集约7亿美元", src), [])
        bad = ground_numbers("Cain已通过这一方式募集约7000万美元", src)
        self.assertEqual(len(bad), 1)
        self.assertEqual(bad[0].value, 70000000)

    def test_c2_bare_chinese_currency_mismatch(self):
        # 9.99美元 vs $5.57: bare Chinese currency amounts are substantive
        src = ["JPMorgan reported a profit of $15.31 billion, or $5.57 a share."]
        self.assertEqual(ground_numbers("每股5.57美元", src), [])
        bad = ground_numbers("每股9.99美元", src)
        self.assertEqual(len(bad), 1)
        self.assertEqual(bad[0].value, Decimal("9.99"))

    def test_d_missing_paragraph_fixed_by_ast_surgery(self):
        import lxml.html
        b = self.data.bilingual("PILOT-A16-WEALTH")
        pids = ["p1", "p2", "p3", "p4"]
        article = lxml.html.Element("article")
        for pid in ("p1", "p2", "p4"):  # p3 omitted by a faulty layout
            p = lxml.html.Element("p")
            p.set("class", "prose-p")
            p.set("data-ref", pid)
            article.append(p)
        repairs = surgical_narrative_completion(
            article, pids, {pid: (b[pid]["cn"], b[pid]["en"]) for pid in pids}
        )
        self.assertIn("insert:p3", repairs)
        refs = [p.get("data-ref") for p in article.xpath(".//p[@data-ref]")]
        self.assertEqual(refs, pids)
        inserted = article.xpath(".//p[@data-ref='p3']/span")
        self.assertEqual(inserted[0].text, b["p3"]["cn"], "surgical fill must restore canonical CN")
        self.assertEqual(inserted[1].text, b["p3"]["en"], "surgical fill must restore canonical EN")

    def test_d2_duplicate_data_ref_deduplicated(self):
        import lxml.html
        article = lxml.html.Element("article")
        for pid in ("p1", "p2", "p2", "p3"):  # faulty layout duplicates p2
            p = lxml.html.Element("p")
            p.set("class", "prose-p")
            p.set("data-ref", pid)
            article.append(p)
        repairs = surgical_narrative_completion(article, ["p1", "p2", "p3"])
        self.assertIn("dedup:p2", repairs)
        refs = [p.get("data-ref") for p in article.xpath(".//p[@data-ref]")]
        self.assertEqual(refs, ["p1", "p2", "p3"], "each pK appears exactly once")

    def test_d3_multi_phrase_data_hl_marks_all_phrases(self):
        from tracer.compose import prose_block
        p = prose_block("p1", "甲条款与乙条款都很重要", "Clause A and Clause B matter",
                        hl_cn="甲条款|乙条款", hl_en="Clause A|Clause B")
        marks_cn = [m.text_content() for m in p.xpath("./span[contains(@class,'lang-cn')]//mark")]
        marks_en = [m.text_content() for m in p.xpath("./span[contains(@class,'lang-en')]//mark")]
        self.assertEqual(marks_cn, ["甲条款", "乙条款"])
        self.assertEqual(marks_en, ["Clause A", "Clause B"])

    def test_e_highlight_density_cap(self):
        import lxml.etree
        import lxml.html
        article = lxml.html.Element("article")
        span = lxml.etree.SubElement(article, "span")
        span.set("class", "lang-cn")
        span.text = "短"
        mark = lxml.etree.SubElement(span, "mark")
        mark.set("class", "ed-hl")
        mark.text = "这是一个远远超过百分之十二密度上限的高亮片段"
        mark.tail = "文"
        density = check_highlight_density(article, cap=1.0)
        self.assertGreater(density, 0.12)
        with self.assertRaises(TracerCompilationError):
            check_highlight_density(article)
        # control: under the cap passes
        article2 = lxml.html.Element("article")
        span2 = lxml.etree.SubElement(article2, "span")
        span2.set("class", "lang-cn")
        mark2 = lxml.etree.SubElement(span2, "mark")
        mark2.set("class", "ed-hl")
        mark2.text = "一二三四五六七八"
        mark2.tail = "一" * 62  # 8 / 70 ≈ 11.4%
        self.assertLessEqual(check_highlight_density(article2), 0.12)

    def test_f_forbidden_pipeline_strings(self):
        for s in ("待审译稿", "未经逐格核准", "Inspect source", "已核验"):
            with self.assertRaises(TracerCompilationError, msg=s):
                assert_no_forbidden_strings(f"<div>{s}</div>")
        clean = "<article><p> faithful surface </p></article>"
        assert_no_forbidden_strings(clean)


@unittest.skipUnless(HAS_DATA, "2026-10-14 pilot dataset not present")
class ReaderShellArtifactCheck(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tracer_pipeline import ISSUE_DATE_CN, ISSUE_DATE_EN, build_units
        data = load_pilot_data()
        cls.entries = build_units(data, PILOT_ROOT, PDF_PATH, fast=not (HAS_FITZ and HAS_PIL))
        cls.doc = build_issue_artifact(date_cn=ISSUE_DATE_CN, date_en=ISSUE_DATE_EN, units=cls.entries)

    def test_canonical_sections_populated_only(self):
        # Partial issues omit empty sections entirely (no pipeline chrome).
        for key in ("a1", "us", "opinion"):
            self.assertIn(f'id="sec-{key}"', self.doc)
        for cn in ("A1 头版要闻", "U.S. 美国", "Opinion 社论与观点"):
            self.assertIn(cn, self.doc)
        for key in ("world", "bt", "markets", "life"):
            self.assertNotIn(f'id="sec-{key}"', self.doc)
        self.assertNotIn("未覆盖", self.doc)
        # authentic newspaper surface: no tracer/sample wording
        self.assertNotIn("Vertical Tracer", self.doc)
        self.assertNotIn("追踪样本", self.doc)
        self.assertNotIn("代表性阅读单元", self.doc)
        self.assertIn("星期三", self.doc)

    def test_units_and_language_switching(self):
        for uid in ("PILOT-A1-BANKS", "PILOT-A1-CONDO", "PILOT-A1-NAVY",
                    "PILOT-A15-EDGEWORTH", "PILOT-A16-WEALTH", "COMPOSITE-A16-LETTERS"):
            self.assertIn(f'id="u-{uid}"', self.doc)
        for lang in ('data-lang="zh"', 'data-lang="en"', 'data-lang="bi"'):
            self.assertIn(lang, self.doc)
        # rubric kickers
        self.assertIn("Bookshelf · A15", self.doc)
        self.assertIn("Review &amp; Outlook · A16", self.doc)

    def test_zero_pipeline_chrome(self):
        for s in FORBIDDEN_STRINGS:
            self.assertNotIn(s, self.doc)
        for s in ("待审译稿", "未经逐格核准", "Inspect source", "已核验"):
            self.assertNotIn(s, self.doc)

    def test_svg_single_language_layers(self):
        # SVG carries both .l-cn/.l-en layers; shell CSS hides exactly one.
        self.assertIn("svg .l-en{display:none}", self.doc)
        self.assertIn('html[lang="en"] svg .l-cn{display:none}', self.doc)
        self.assertIn("data-src=", self.doc)

    def test_narrative_sha256_conservation_through_artifact(self):
        """Parse narrative back out of the artifact: count/order/hash unchanged."""
        import lxml.html
        root = lxml.html.fromstring(self.doc)
        data = load_pilot_data()
        for aid in NarrativeConservationCheck.UNITS:
            with self.subTest(unit=aid):
                unit = root.xpath(f".//div[@id='u-{aid}']")[0]
                pids = data.paragraph_ids(aid)
                rows = unit.xpath(".//p[@data-ref and contains(@class,'prose-p')]")
                self.assertEqual(len(rows), len(pids), aid)
                bilingual = data.bilingual(aid)
                for lang, idx in (("cn", 0), ("en", 1)):
                    got = "\n\n".join(
                        (r.xpath("./span")[idx].text_content()) for r in rows
                    )
                    src = "\n\n".join(bilingual[p][lang] for p in pids)
                    self.assertEqual(
                        hashlib.sha256(got.encode()).hexdigest(),
                        hashlib.sha256(src.encode()).hexdigest(),
                        f"{aid} {lang} diff != 0",
                    )


if __name__ == "__main__":
    unittest.main()
