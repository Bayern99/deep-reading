"""Full-issue funnel gate, composite grouping, routing & three-tier CLI tests.

Ticket 2 (GitHub Issue #3) acceptance tests.  Run with the system interpreter
(has fitz/PIL):  /opt/homebrew/bin/python3 -m unittest tests/test_full_issue_gate_cli.py -v

The pinned pilot dataset is required: when it is absent these tests fail
rather than skip, so `make test` cannot report OK without checking the
product (set WSJ_ALLOW_MISSING_PILOT=1 to skip the data-backed classes
instead).
"""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import time
import unittest
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "render"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from pilot_prereq import require_pilot  # noqa: E402

from tracer import content  # noqa: E402
from tracer.compose import PILOT_ROOT, load_full_data  # noqa: E402
from tracer.gate import (  # noqa: E402
    KNOWN_ANOMALIES,
    run_gate,
    scan_pair,
    write_gate_report,
)
from tracer.numbers import extract_substantive_numbers  # noqa: E402
from tracer.routing import (  # noqa: E402
    COMPOSITES,
    SECTION_MAP,
    TIER1_IDS,
    canonical_section,
    route_issue,
)
from tracer.shell import SECTIONS, build_issue_artifact  # noqa: E402
from tracer.vector import extract_chart_vectors  # noqa: E402
from tracer.whatsnews import resolve_whatsnews  # noqa: E402
from tracer.full_compose import build_full_units  # noqa: E402

HAS_DATA = require_pilot()

EXPECTED_LINKS = {
    "p2": "PILOT-A1-BANKS", "p3": "CASE-B1B2-BOFA", "p4": "PILOT-B2-UNITEDHEALTH",
    "p5": "PILOT-B2-JNJ", "p6": "PILOT-B3-BUGGING", "p7": "PILOT-B3-STELLANTIS",
    "p8": "PILOT-B3-DOMINOS", "p9": "PILOT-B4-ALBERTSONS", "p11": "PILOT-A1-GREECE",
    "p12": "PILOT-A7-POPE", "p13": "PILOT-A7-DRONES", "p14": "PILOT-A7-MI5",
    "p15": "PILOT-A3-SPOKESWOMAN", "p16": "PILOT-A3-SHAKUR",
    "p17": "PILOT-A3-SIXFLAGS", "p18": "PILOT-A3-SHKRELI",
}


@unittest.skipUnless(HAS_DATA, "2026-10-14 pilot dataset not present")
class FullIssueDataTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = load_full_data()
        cls.articles = cls.data.articles
        cls.routes = route_issue(cls.articles)
        cls.entries = build_full_units(cls.data, PILOT_ROOT, __import__("tracer.compose", fromlist=["PDF_PATH"]).PDF_PATH, fast=True)
        cls.entries_by_id = {e.unit_id: e for e in cls.entries}


class GateRadarTimingAndRecall(FullIssueDataTestCase):
    """Stage 1: <0.5s over all 1,257 units; 100% recall on injected faults."""

    def test_scans_all_units_under_half_second(self):
        report = run_gate(self.data.translations, issue="2026-10-14", tier1_ids=TIER1_IDS)
        self.assertEqual(report.units_scanned, 1257)
        self.assertLess(report.duration_s, 0.5)
        self.assertEqual(len(report.spot_checked), len(TIER1_IDS))

    def _kinds(self, en: str, cn: str) -> set[str]:
        return {f.kind for f in scan_pair("INJECTED", "p1", en, cn)}

    def test_injected_magnitude_errors_recalled(self):
        # 700 million -> 7000万 (10x distortion)
        kinds = self._kinds(
            "The company raised $700 million in new funding.",
            "该公司募集了7000万美元新资金。",
        )
        self.assertIn("magnitude", kinds)
        # $2.3B -> 2.3亿 (10x distortion)
        kinds = self._kinds(
            "The deal is worth $2.3 billion.",
            "这笔交易价值2.3亿美元。",
        )
        self.assertIn("magnitude", kinds)
        # controls: correct magnitudes pass
        self.assertEqual(self._kinds("It raised $2.3 billion.", "募集了23亿美元。"), set())

    def test_injected_qualifier_errors_recalled(self):
        kinds = self._kinds(
            "The plan could create up to 10 million jobs.",
            "该计划可创造1000万个就业岗位。",
        )
        self.assertIn("qualifier", kinds)
        kinds = self._kinds(
            "Mortgage rates are in the mid-6% range.",
            "抵押贷款利率为6%。",
        )
        self.assertIn("qualifier", kinds)
        # control: qualifier retained
        self.assertEqual(
            self._kinds("Rates are in the mid-6% range.", "利率处于6%中段。"), set()
        )

    def test_injected_polarity_error_recalled(self):
        kinds = self._kinds(
            "The stock rose 8% on Tuesday after earnings.",
            "该股周二公布业绩后下跌8%。",
        )
        self.assertIn("polarity", kinds)
        # control: direction preserved
        self.assertEqual(
            self._kinds("The stock rose 8% on Tuesday.", "该股周二上涨8%。"), set()
        )

    def test_injected_length_ratio_truncation_recalled(self):
        en = "The committee announced a comprehensive review of the proposed merger between the two largest regional lenders late Thursday evening."
        kinds = self._kinds(en, "在审查。")
        self.assertIn("length-ratio", kinds)

    def test_injected_completeness_errors_recalled(self):
        kinds = self._kinds(
            "“The deal will close next quarter, the spokesman said.",
            "“该交易将于下季度完成。”发言人说。",
        )
        self.assertIn("completeness", kinds)

    def test_documented_anomaly_recorded_not_surfaced(self):
        self.assertIn("PILOT-B1-APPLECEO:p3", KNOWN_ANOMALIES)
        report = run_gate(self.data.translations, issue="2026-10-14")
        recorded = [f for f in report.findings if f.disposition == "recorded"]
        self.assertTrue(any(f.article_id == "PILOT-B1-APPLECEO" and f.paragraph_id == "p3" for f in recorded))
        escalate = [f for f in report.findings if f.disposition == "escalate"]
        self.assertTrue(all(f"documented" not in f.detail for f in escalate))

    def test_gate_report_written_to_workspace_not_html(self):
        import lxml.html
        report = run_gate(self.data.translations, issue="2026-10-14", tier1_ids=TIER1_IDS)
        with tempfile.TemporaryDirectory() as tmp:
            path = write_gate_report(report, Path(tmp) / "gate-report.json")
            loaded = json.loads(path.read_text("utf-8"))
            self.assertEqual(loaded["units_scanned"], 1257)
            doc = build_issue_artifact(
                date_cn="2026年10月14日 · 星期三", date_en="Wednesday, October 14, 2026",
                units=self.entries,
            )
            for finding in report.findings:
                self.assertNotIn(finding.detail, doc)
            self.assertNotIn("gate-report", doc)
            root = lxml.html.fromstring(doc)
            self.assertFalse(root.xpath(".//*[contains(@class,'audit')]"))


class NumbersDedupCheck(unittest.TestCase):
    """Reviewer-G duplicate-percent fix: one token per ASCII percent string."""

    def test_ascii_percent_extracted_once(self):
        toks = extract_substantive_numbers("The index fell 6.8% since June.")
        self.assertEqual([(str(t.value), t.kind) for t in toks], [("6.8", "pct")])

    def test_chinese_context_percent_kept(self):
        toks = extract_substantive_numbers("回报率为3.5%的项目")
        self.assertEqual([(str(t.value), t.kind) for t in toks], [("3.5", "pct")])

    def test_basis_points_both_languages(self):
        self.assertEqual(
            [(str(t.value), t.kind) for t in extract_substantive_numbers("利差扩大20个基点")],
            [("20", "bp")],
        )

    def test_scaled_magnitude_equivalence(self):
        self.assertEqual(
            extract_substantive_numbers("700 million")[0].value,
            extract_substantive_numbers("7亿")[0].value,
        )
        self.assertEqual(
            extract_substantive_numbers("5万亿")[0].value,
            extract_substantive_numbers("$5 trillion")[0].value,
        )

    def test_calendar_years_and_decades_are_not_counts(self):
        """Years/decades rendered as 「上世纪80年代」 must not flag magnitudes."""
        for text in ("in the 1980s", "in 1890", "the early 1900s", "上世纪80年代",
                     "19世纪90年代", "the mid-2010s", "1969-70"):
            toks = extract_substantive_numbers(text)
            self.assertEqual(toks, [], f"{text!r} should yield no tokens, got {toks}")
        # real counts stay substantive
        self.assertTrue(any(t.value == Decimal("47000") for t in extract_substantive_numbers("47000 vehicles")))

    def test_chinese_range_endpoints_share_trailing_unit(self):
        toks = extract_substantive_numbers("仅收取约20至50美元的人工费")
        self.assertEqual(
            sorted((str(t.value), t.kind) for t in toks),
            [("20", "money"), ("50", "money")],
        )

    def test_hyphenated_money_suffix(self):
        toks = extract_substantive_numbers("a $50,000-a-megawatt deposit")
        self.assertIn(("50000", "money"), [(str(t.value), t.kind) for t in toks])

    def test_verbal_fractions(self):
        toks = extract_substantive_numbers("roughly half a million followers")
        self.assertIn(("500000", "money"), [(str(t.value), t.kind) for t in toks])

    def test_sentence_final_scale_word_kept(self):
        toks = extract_substantive_numbers("Revenue rose 9% to $115 billion.")
        self.assertIn("115000000000", [str(t.value) for t in toks])


@unittest.skipUnless(HAS_DATA, "2026-10-14 pilot dataset not present")
class ChartUnionCropCheck(FullIssueDataTestCase):
    """Reviewer-G round 1: union crops locked to the chart's own column."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from tracer.vector import media_sibling_bboxes
        cls.extracted = {}
        for aid, a in cls.articles.items():
            for m in a.get("media", []):
                if m.get("type") != "chart":
                    continue
                native = cls.data.natives[int(m["page"])]
                W, H = float(native["width"]), float(native["height"])
                sibs = media_sibling_bboxes(a.get("media") or [], int(m["page"]), m["id"], W, H)
                cv = extract_chart_vectors(native, m["id"], int(m["page"]), m["bbox_normalized_top_left"], sibs)
                cls.extracted[m["id"]] = (m, native, cv)

    def test_all_21_charts_extracted(self):
        self.assertEqual(len(self.extracted), 21)

    def test_union_never_balloons_past_own_column(self):
        for cid, (m, native, cv) in self.extracted.items():
            with self.subTest(chart=cid):
                W = float(native["width"])
                ox0, _, ox1, _ = [float(v) for v in m["bbox_normalized_top_left"]]
                orig_w = (ox1 - ox0) * W
                ux0, _, ux1, _ = cv.union_bbox_points
                self.assertLessEqual(ux1 - ux0, orig_w + 24.0, f"{cid} union too wide")

    def test_zero_body_prose_inside_union_crops(self):
        from tracer.vector import line_font
        for cid, (m, native, cv) in self.extracted.items():
            with self.subTest(chart=cid):
                ux0, uy0, ux1, uy1 = cv.union_bbox_points
                for l in native["lines"]:
                    font = line_font(l)
                    if not (font.startswith("Exchange") or font.startswith("DJ5Exchange")):
                        continue
                    cx = (l["bbox"][0] + l["bbox"][2]) / 2
                    cy = (l["bbox"][1] + l["bbox"][3]) / 2
                    self.assertFalse(
                        ux0 <= cx <= ux1 and uy0 <= cy <= uy1,
                        f"{cid} crops body prose line {l.get('text', '')[:50]!r}",
                    )

    def test_clean_nonconcatenated_titles(self):
        def de_lig(s: str) -> str:
            return s.replace("\ufb01", "fi").replace("\ufb02", "fl").replace("\ufb00", "ff")

        titles = {cid: de_lig(cv.title_en) for cid, (_, _, cv) in self.extracted.items()}
        self.assertEqual(titles["p20-b72"], "Johnson & Johnson quarterly revenue")
        self.assertEqual(titles["p10-b59"], "Urban unemployment rate")
        self.assertEqual(titles["p10-b63"], "Urban disposable income per capita, year-over-year change")
        self.assertEqual(titles["p10-b68"], "Consumer confidence index")
        self.assertEqual(titles["p10-b57"], "Annual change in number of employed")
        for cid, title in titles.items():
            self.assertNotIn("bellwether", title, f"{cid} absorbed the photo caption")
            self.assertLessEqual(len(title), 120, f"{cid} title looks concatenated: {title!r}")


@unittest.skipUnless(HAS_DATA, "2026-10-14 pilot dataset not present")
class Tier2NoRestatementCheck(FullIssueDataTestCase):
    """FOUNDATION.md Invariant 5: no Tier 2 element restates the lede or a
    sentence already used by another element."""

    def test_takeaways_never_select_the_lede(self):
        from tracer.full_compose import genre_layer
        for aid in ("PILOT-A2-HOMES", "PILOT-A7-POPE", "PILOT-B4-ALBERTSONS", "PILOT-B2-JNJ"):
            layer = genre_layer(self.data, aid, "article")
            if "takeaways" not in layer:
                continue
            with self.subTest(unit=aid):
                pids = [tk["data_src"] for tk in layer["takeaways"]]
                self.assertNotIn("p1", pids, f"{aid} takeaway restates the lede")
                units = self.data.units(aid)
                for tk in layer["takeaways"]:
                    self.assertIn(tk["en"], units[tk["data_src"]]["en"])

    def test_thesis_box_not_the_lede(self):
        from tracer.full_compose import genre_layer
        layer = genre_layer(self.data, "PILOT-A15-FRANK", "opinion")
        if "thesis" in layer:
            self.assertNotEqual(layer["thesis"]["data_src"], "p1")

    def test_pull_quote_not_repeating_takeaway_or_thesis(self):
        from tracer.full_compose import genre_layer
        for aid, genre in (("PILOT-A15-FRANK", "opinion"), ("PILOT-A17-FRIEDMAN", "opinion")):
            layer = genre_layer(self.data, aid, genre)
            if "pull_quote" not in layer:
                continue
            with self.subTest(unit=aid):
                pq = layer["pull_quote"]
                used = set()
                for tk in layer.get("takeaways", []):
                    used.add(tk["en"])
                if "thesis" in layer:
                    used.add(layer["thesis"]["en"])
                self.assertNotIn(pq["en"], used)

    def test_companion_data_src_matches_chart_topic(self):
        """Printed charts ground their companion in the on-topic paragraph."""
        for e in self.entries:
            for cid, expect_pid in (("p10-b59", "p12"), ("p20-b45", "p6"), ("p21-b43", "p4")):
                if f'data-chart="{cid}"' not in e.element_html:
                    continue
                frag = e.element_html.split(f'data-chart="{cid}"')[0]
                self.assertIn(f'data-src="{expect_pid}"', frag[-200:], f"{cid} topic anchor")


class CompositeGroupingCheck(FullIssueDataTestCase):
    """86 raw fragments -> ~70 units; every paragraph conserved verbatim."""

    def test_unit_counts_and_tiers(self):
        from collections import Counter
        tiers = Counter(e.tier for e in self.entries)
        self.assertEqual(tiers[1], 8)
        self.assertEqual(tiers[2], 54)
        self.assertEqual(tiers[3], 9)  # 5 composites + digest + brief + caption + tables
        self.assertEqual(len(self.entries), 71)

    def test_all_86_items_routed_exactly_once(self):
        routed = [aid for r in self.routes for aid in r.article_ids]
        self.assertEqual(len(routed), 86)
        self.assertEqual(set(routed), set(self.articles))

    def test_narrative_sha256_conservation_all_items(self):
        """Every paragraph of every one of the 86 items appears verbatim
        (Chinese and English) inside exactly its reading unit."""
        for aid, article in self.articles.items():
            with self.subTest(item=aid):
                entry = self.entries_by_id.get(aid)
                if entry is None:
                    member_of = [uid for uid, spec in COMPOSITES.items() if aid in spec["members"]]
                    self.assertEqual(len(member_of), 1, f"{aid} not routed")
                    entry = self.entries_by_id[member_of[0]]
                import lxml.html
                root = lxml.html.fromstring(entry.element_html)
                span_texts = {s.text_content() for s in root.xpath(".//span")}
                h_texts = {h.text_content() for h in root.xpath(".//h1|.//h2")}
                for pid in self.data.paragraph_ids(aid):
                    unit = self.data.bilingual(aid).get(pid)
                    if unit is None:
                        continue
                    for lang in ("cn", "en"):
                        text = unit[lang]
                        self.assertTrue(
                            text in span_texts or text in h_texts,
                            f"{aid}:{pid} {lang} paragraph missing verbatim",
                        )

    def test_composite_columns_merge_single_paragraph_fragments(self):
        expected_members = {uid: len(spec["members"]) for uid, spec in COMPOSITES.items()}
        for uid, n in expected_members.items():
            entry = self.entries_by_id[uid]
            blocks = entry.element_html.count('class="letter"')
            self.assertEqual(blocks, n, f"{uid} member count")
        # letters: 5 diesel letters share one sub-header
        letters = self.entries_by_id["COMPOSITE-A16-LETTERS"].element_html
        self.assertEqual(letters.count('letter-group-title'), 1)
        # zero one-paragraph orphan units for the recurring rubrics
        for uid in expected_members:
            self.assertEqual(self.entries_by_id[uid].tier, 3)

    def test_whitnews_paragraphs_intact_with_deep_links(self):
        entry = self.entries_by_id["PILOT-A1-WHATSNEWS"]
        import lxml.html
        root = lxml.html.fromstring(entry.element_html)
        for pid, target in EXPECTED_LINKS.items():
            p = root.xpath(f".//p[@data-ref='{pid}']")
            self.assertEqual(len(p), 1, f"{pid} narrative paragraph")
            src = self.data.units("PILOT-A1-WHATSNEWS")[pid]
            self.assertEqual(p[0].xpath("./span")[0].text_content(), src["cn"])
            link = p[0].getnext()
            self.assertIsNotNone(link and link.xpath(".//a/@href"))
            href = link.xpath(".//a/@href")[0]
            self.assertEqual(href, f"#u-{target}")
            self.assertIn(target, self.entries_by_id, f"deep-link target unit {target}")
        # narrative conservation: all 18 digest paragraphs verbatim
        span_texts = {s.text_content() for s in root.xpath(".//span")}
        for pid in [f"p{i}" for i in range(1, 19)]:
            unit = self.data.units("PILOT-A1-WHATSNEWS")[pid]
            self.assertIn(unit["cn"], span_texts)


class SectionRoutingCheck(FullIssueDataTestCase):
    def test_all_28_raw_sections_map_to_canonical_seven(self):
        raw_sections = {a["section"] for a in self.articles.values()}
        self.assertEqual(len(raw_sections), 28)
        canonical_keys = {key for key, _, _ in SECTIONS}
        mapped = {canonical_section(s) for s in raw_sections}
        self.assertEqual(mapped, canonical_keys)
        for s in raw_sections:
            self.assertIn(s, SECTION_MAP)

    def test_rubric_kickers_preserved(self):
        kickers = " ".join(e.kicker for e in self.entries).lower()
        for rubric in ("Heard on the Street", "Review & Outlook", "Bookshelf",
                       "Upward Mobility", "The Elder Influencer", "Business World",
                       "Politics & Ideas", "Jason Gay", "Stock Spotlight",
                       "U.S. Watch", "World Watch", "Analysis"):
            self.assertIn(rubric.lower(), kickers)

    def test_all_seven_sections_populated(self):
        used = {e.section for e in self.entries}
        self.assertEqual(used, {key for key, _, _ in SECTIONS})

    def test_sidebar_cross_linked_to_parent(self):
        entry = self.entries_by_id["PILOT-A8-SHIPBUILDER"]
        self.assertIn('data-ref="related:PILOT-A8-TAIWAN"', entry.element_html)
        self.assertIn("#u-PILOT-A8-TAIWAN", entry.element_html)


class ChartCompanionCheck(FullIssueDataTestCase):
    """All 21 printed charts: Retina* metadata + data-src companions."""

    def test_all_21_charts_extract_retina_metadata(self):
        charts = [(aid, m) for aid, a in self.articles.items()
                  for m in a.get("media", []) if m.get("type") == "chart"]
        self.assertEqual(len(charts), 21)
        for aid, m in charts:
            with self.subTest(chart=m["id"]):
                native = self.data.natives[int(m["page"])]
                cv = extract_chart_vectors(native, m["id"], int(m["page"]), m["bbox_normalized_top_left"])
                self.assertTrue(cv.title_en or cv.axis_ticks_en, f"{m['id']} no Retina text")
                self.assertTrue(cv.retina_lines or cv.axis_ticks_en)

    def test_companion_cards_grounded_in_units(self):
        companions = 0
        for e in self.entries:
            companions += e.element_html.count('class="companion"')
        self.assertEqual(companions, 21)
        for e in self.entries:
            for frag in e.element_html.split('class="companion"')[1:]:
                self.assertIn('data-src="p', frag.split("</aside>")[0])
        # series key bilingual pairing on the BANKS charts
        banks = self.entries_by_id["PILOT-A1-BANKS"].element_html
        self.assertIn('class="co-term">Wells Fargo</span>', banks)
        self.assertIn('class="co-cn"> · 富国银行</span>', banks)

    def test_wsj_chart_primitives_on_mechanism_stories(self):
        for uid in ("PILOT-A1-CONDO", "PILOT-A1-CARFREE", "CASE-B1B2-PRIVATE-EQUITY"):
            self.assertIn('class="wsj-chart"', self.entries_by_id[uid].element_html)


class ZeroSilentFallbackCheck(FullIssueDataTestCase):
    def test_tier1_and_tier2_not_downgraded(self):
        for e in self.entries:
            if e.tier in (1, 2):
                self.assertIn(f"unit-tier{e.tier}", e.element_html)
                self.assertIn('class="prose-p"', e.element_html)

    def test_genre_grammar_present(self):
        # article: takeaway bullets; editorial: thesis box; review: metadata card
        self.assertIn('class="takeaways"', self.entries_by_id["PILOT-A2-HOMES"].element_html)
        self.assertIn('class="thesis-box"', self.entries_by_id["PILOT-A16-IRAN"].element_html
                      or self.entries_by_id["PILOT-A16-WEALTH"].element_html)
        self.assertIn('class="book-details"', self.entries_by_id["PILOT-A15-EDGEWORTH"].element_html)
        # opinion pull quote from the auto genre layer
        self.assertIn('pull-quote', self.entries_by_id["PILOT-A15-FRANK"].element_html)

    def test_resolver_matches_expected_16(self):
        members = {m for spec in COMPOSITES.values() for m in spec["members"]}
        links = resolve_whatsnews(self.data, members)
        self.assertEqual(len(links), 16)
        for pid, target in EXPECTED_LINKS.items():
            self.assertEqual(links[pid].target_id, target)


@unittest.skipUnless(HAS_DATA, "2026-10-14 pilot dataset not present")
class FullIssueCliCheck(unittest.TestCase):
    def test_cli_full_mode_writes_artifact_and_gate_report(self):
        import tracer_pipeline
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "full.html"
            gate = Path(tmp) / "gate.json"
            rc = tracer_pipeline.main([
                "--mode", "full", "--fast",
                "--output", str(out), "--gate-report", str(gate),
            ])
            self.assertEqual(rc, 0)
            self.assertTrue(out.exists())
            report = json.loads(gate.read_text("utf-8"))
            self.assertEqual(report["units_scanned"], 1257)
            self.assertIn("findings_by_kind", report)
            self.assertNotIn("gate-report", out.read_text("utf-8"))

    def test_cli_units_subset(self):
        import tracer_pipeline
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "subset.html"
            rc = tracer_pipeline.main([
                "--mode", "full", "--fast", "--output", str(out),
                "--units", "PILOT-A1-BANKS,COMPOSITE-A16-LETTERS",
                "--gate-report", str(Path(tmp) / "g.json"),
            ])
            self.assertEqual(rc, 0)
            doc = out.read_text("utf-8")
            self.assertIn('id="u-PILOT-A1-BANKS"', doc)
            self.assertIn('id="u-COMPOSITE-A16-LETTERS"', doc)
            self.assertNotIn('id="u-PILOT-A7-POPE"', doc)

    def test_cli_tracer_mode_keeps_pilot_slice(self):
        import tracer_pipeline
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "tracer.html"
            rc = tracer_pipeline.main(["--mode", "tracer", "--output", str(out), "--fast"])
            self.assertEqual(rc, 0)
            doc = out.read_text("utf-8")
            for uid in ("PILOT-A1-BANKS", "PILOT-A1-CONDO", "PILOT-A1-NAVY",
                        "PILOT-A15-EDGEWORTH", "PILOT-A16-WEALTH", "COMPOSITE-A16-LETTERS"):
                self.assertIn(f'id="u-{uid}"', doc)


if __name__ == "__main__":
    unittest.main()
