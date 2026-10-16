"""7-Oracle certification, Ticket 2 polish notes, and fault-injection tests.

Ticket 3 (GitHub Issue #4) acceptance tests.  Run with the system interpreter
(has fitz/PIL):  /opt/homebrew/bin/python3 -m unittest tests/test_seven_oracles.py -v

The pinned pilot dataset is required: when it is absent these tests fail
rather than skip, so `make test` cannot report OK without checking the
product (set WSJ_ALLOW_MISSING_PILOT=1 to skip the data-backed classes
instead).
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "render"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from pilot_prereq import require_pilot  # noqa: E402

from tracer.compose import PILOT_ROOT, load_full_data  # noqa: E402
from tracer.gate import scan_pair  # noqa: E402
from tracer.numbers import extract_substantive_numbers, ground_numbers  # noqa: E402
from tracer.verify import TracerCompilationError  # noqa: E402
from tracer.vector import (  # noqa: E402
    extract_chart_vectors,
    media_sibling_bboxes,
    union_chart_bbox,
)

HAS_DATA = require_pilot()
try:
    import fitz  # noqa: F401
    import PIL  # noqa: F401

    HAS_RASTER = True
except ImportError:
    HAS_RASTER = False


def _norm(toks):
    return sorted((t.value, t.kind) for t in toks)


class SpelledOutNumbersCheck(unittest.TestCase):
    """PILOT-A16-CORRECTION p1: 'Four hundred thousand dollars' == 40万美元."""

    def test_four_hundred_thousand_dollars(self):
        toks = extract_substantive_numbers("Four hundred thousand dollars")
        self.assertEqual(_norm(toks), [(Decimal(400000), "money")])

    def test_cross_language_grounding(self):
        self.assertEqual(
            ground_numbers("40万美元", ["Four hundred thousand dollars is roughly 200%."]), []
        )
        bad = ground_numbers("50万美元", ["Four hundred thousand dollars."])
        self.assertEqual(len(bad), 1)
        self.assertEqual(bad[0].value, Decimal(500000))

    def test_basic_cardinal_scale_expressions(self):
        cases = {
            "seven hundred million": Decimal(700000000),
            "two billion dollars": Decimal(2000000000),
            "ten thousand": Decimal(10000),
            "ninety hundred thousand dollars": Decimal(9000000),
        }
        for text, value in cases.items():
            with self.subTest(text=text):
                toks = extract_substantive_numbers(text)
                self.assertIn((value, "money"), _norm(toks))

    def test_spelled_numbers_do_not_create_spurious_tokens(self):
        # structural small integers and years stay non-substantive
        self.assertEqual(extract_substantive_numbers("a family of four in 2025"), [])
        # verbal fractions unchanged
        self.assertIn(
            (Decimal(500000), "money"),
            _norm(extract_substantive_numbers("roughly half a million followers")),
        )

    @unittest.skipUnless(HAS_DATA, "2026-10-14 pilot dataset not present")
    def test_correction_paragraph_no_longer_flags_magnitude(self):
        data = load_full_data()
        u = data.bilingual("PILOT-A16-CORRECTION")["p1"]
        kinds = {f.kind for f in scan_pair("PILOT-A16-CORRECTION", "p1", u["en"], u["cn"])}
        self.assertNotIn("magnitude", kinds)


@unittest.skipUnless(HAS_DATA, "2026-10-14 pilot dataset not present")
class MultiColumnSourceLineCheck(unittest.TestCase):
    """Reviewer-G follow-up: shared 3-column RetinaMPNarrowLt source lines on
    page 10 keep their full text in ChartVectorMeta.source but never expand
    the WebP crop (no sliced half-words at the bottom edge)."""

    @classmethod
    def setUpClass(cls):
        cls.data = load_full_data()
        cls.targets = {}
        for a in cls.data.articles.values():
            for m in a.get("media") or []:
                if m.get("id") in ("p10-b59", "p10-b63", "p10-b68", "p02-b78"):
                    cls.targets[m["id"]] = (a, m)

    def _extract(self, cid):
        a, m = self.targets[cid]
        native = self.data.natives[int(m["page"])]
        W, H = float(native["width"]), float(native["height"])
        sibs = media_sibling_bboxes(a.get("media") or [], int(m["page"]), cid, W, H)
        union, members, text_only = union_chart_bbox(native, m["bbox_normalized_top_left"], sibs)
        cv = extract_chart_vectors(native, cid, int(m["page"]), m["bbox_normalized_top_left"], sibs)
        return native, m, union, text_only, cv

    def test_shared_source_line_text_only_not_cropped(self):
        for cid in ("p10-b59", "p10-b63", "p10-b68"):
            with self.subTest(chart=cid):
                native, m, union, text_only, cv = self._extract(cid)
                self.assertTrue(text_only, f"{cid}: shared source line not detected")
                self.assertIn("Sources:", cv.source_en)
                self.assertIn("National Bureau", cv.source_en)  # full multi-column text
                ux0, uy0, ux1, uy1 = union
                for l in text_only:
                    lx0, ly0, lx1, ly1 = l["bbox"]
                    intersects = lx0 < ux1 and ux0 < lx1 and ly0 < uy1 and uy0 < ly1
                    self.assertFalse(intersects, f"{cid} crop slices shared source line")

    def test_single_column_source_stays_inside_crop(self):
        native, m, union, text_only, cv = self._extract("p02-b78")
        self.assertFalse(text_only)
        self.assertEqual(cv.source_en, "Source: the companies")
        ux0, uy0, ux1, uy1 = union
        for l in native["lines"]:
            if "Source: the companies" in (l.get("text") or ""):
                self.assertTrue(
                    ux0 <= l["bbox"][0] and l["bbox"][2] <= ux1
                    and uy0 <= l["bbox"][1] and l["bbox"][3] <= uy1,
                    "p02-b78 single-column source must stay inside the union crop",
                )


class FaultInjectionDetectorCheck(unittest.TestCase):
    """Oracle 5 detectors reject each historical failure class deterministically."""

    def test_magnitude_detectors(self):
        from tracer.oracles import detect_cross_language_magnitude

        self.assertTrue(detect_cross_language_magnitude(
            "The company raised $700 million in new funding.",
            "该公司募集了7000万美元新资金。",
        ))
        self.assertTrue(detect_cross_language_magnitude(
            "The deal is worth $2.3 billion.", "这笔交易价值2.3亿美元。"
        ))
        self.assertEqual(detect_cross_language_magnitude(
            "The deal is worth $2.3 billion.", "这笔交易价值23亿美元。"
        ), [])

    def test_ungrounded_number_detector(self):
        from tracer.oracles import detect_ungrounded_numbers

        bad = detect_ungrounded_numbers("费率为4.12%，高于去年。", ["费率为5%，高于去年。"])
        self.assertEqual(len(bad), 1)
        self.assertEqual(bad[0].value, Decimal("4.12"))
        self.assertEqual(detect_ungrounded_numbers("费率为5%。", ["费率为5%。"]), [])

    def test_pseudo_quote_detector(self):
        from tracer.oracles import detect_pseudo_quote

        self.assertIsNone(detect_pseudo_quote("“Hello world,” he said.", 1, "“Hello world,” he said."))
        self.assertIsNotNone(detect_pseudo_quote("“Hello world,” he said.", 1, "“Goodbye world,” he said."))

    def test_svg_overflow_detector(self):
        from tracer.oracles import svg_text_overflow_findings

        svg = '<svg viewBox="0 0 640 150"><text x="0.0" y="20.0" font-size="14">标题</text></svg>'
        self.assertEqual(svg_text_overflow_findings(svg, "ok", 640.0), [])
        bad = svg.replace('x="0.0"', f'x="{700.0}"', 1)
        self.assertTrue(svg_text_overflow_findings(bad, "bad", 640.0))

    def test_language_toggle_gap_detector(self):
        import lxml.html
        from tracer.oracles import detect_language_toggle_gap

        doc = (
            '<article><p class="prose-p" data-ref="p1">'
            '<span class="lang-cn">中文</span><span class="lang-en">English</span></p>'
            '<h2 class="sec-h" data-ref="p2"><span class="lang-cn">小标题</span>'
            '<span class="sec-h-en">Subhead</span></h2></article>'
        )
        root = lxml.html.fromstring(doc)
        self.assertEqual(detect_language_toggle_gap(root), [])
        en = root.xpath(".//span[contains(@class,'lang-en')]")[0]
        en.getparent().remove(en)
        gaps = detect_language_toggle_gap(root)
        self.assertEqual(len(gaps), 1)
        self.assertIn("p1", gaps[0])


@unittest.skipUnless(HAS_DATA, "2026-10-14 pilot dataset not present")
class SevenOraclesFastArtifactCheck(unittest.TestCase):
    """All 7 oracles pass over a fast-mode full-issue artifact (budget and
    Headless Chrome geometry probe excluded; covered by the real E2E run)."""

    @classmethod
    def setUpClass(cls):
        import tracer_pipeline

        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name) / "full.html"
        rc = tracer_pipeline.main([
            "--mode", "full", "--fast", "--output", str(cls.out),
            "--gate-report", str(Path(cls.tmp.name) / "gate.json"),
        ])
        assert rc == 0
        cls.data = load_full_data()
        from tracer.oracles import certify

        cls.report = certify(
            cls.out, cls.data, check_budget=False, run_geometry_probe=False
        )

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_all_seven_oracles_pass(self):
        self.assertTrue(self.report.passed)
        for o in self.report.oracles:
            self.assertTrue(o.passed, f"{o.name}: {o.detail}")

    def test_oracle1_sha256_round_trip_86_of_86(self):
        o = self.report.oracle("narrative_conservation")
        self.assertEqual(o.detail["items"], 86)
        self.assertEqual(o.detail["matched"], 86)
        self.assertEqual(o.detail["diff"], 0)
        self.assertEqual(o.detail["sha256_round_trip"], "100%")

    def test_oracle2_all_elements_grounded(self):
        o = self.report.oracle("paragraph_scoped_numeric_grounding")
        self.assertEqual(o.detail["grounding"], "100%")
        self.assertEqual(o.detail["failures"], [])

    def test_oracle3_chart_coverage_21_of_21(self):
        o = self.report.oracle("retina_chart_vector_coverage")
        self.assertEqual(o.detail["coverage"], "21/21")

    def test_oracle5_recall_6_of_6(self):
        o = self.report.oracle("historical_fault_injection_recall")
        self.assertEqual(o.detail["recall"], "6/6")
        for name, c in o.detail["classes"].items():
            self.assertTrue(c["detected"], f"{name} not detected")

    def test_oracle6_hierarchy_counts(self):
        o = self.report.oracle("print_hierarchy_composite_grouping_zero_lede_restatement")
        self.assertEqual(o.detail["tiers"], {1: 8, 2: 54, 3: 9})
        self.assertEqual(o.detail["units"], 71)
        self.assertEqual(o.detail["raw_items"], 86)
        self.assertEqual(o.detail["deep_links"], 16)

    def test_oracle_6_rejects_multi_token_p1_in_tier2(self):
        import lxml.html

        from tracer.oracles import oracle_print_hierarchy

        for mutated in ("p1 p2", "p1,p2"):
            with self.subTest(data_src=mutated):
                root = lxml.html.fromstring(self.out.read_text("utf-8"))
                victims = root.xpath(
                    './/div[@data-tier="2"]//li[contains(@class,"takeaway")][@data-src]'
                )
                self.assertTrue(victims, "no Tier 2 takeaway to mutate")
                victims[0].set("data-src", mutated)
                result = oracle_print_hierarchy(root, self.data)
                self.assertFalse(result.passed)
                self.assertTrue(
                    any("cites p1" in f for f in result.detail["failures"]),
                    f"multi-token {mutated!r} not rejected: {result.detail['failures']}",
                )

    def test_oracle7_clean_surface(self):
        o = self.report.oracle("viewport_geometry_clean_surface_payload")
        self.assertEqual(o.detail["failures"], [])
        self.assertEqual(o.detail["chrome_probe"]["status"], "skipped")

    def test_certification_rejects_a_corrupted_artifact(self):
        import lxml.html
        from tracer.oracles import certify

        root = lxml.html.fromstring(self.out.read_text("utf-8"))
        victim = root.xpath(".//article[@data-unit='PILOT-A2-HOMES']//p[contains(@class,'prose-p')]")[0]
        victim.getparent().remove(victim)
        corrupted = Path(self.tmp.name) / "corrupted.html"
        corrupted.write_text(lxml.html.tostring(root, encoding="unicode"), "utf-8")
        report = certify(corrupted, self.data, check_budget=False, run_geometry_probe=False)
        self.assertFalse(report.passed)
        self.assertFalse(report.oracle("narrative_conservation").passed)

    # --- Issue #5: Group C Forensic Dossier (Variant A) production fold-in ---

    def _unit_root(self, uid: str):
        import lxml.html

        root = lxml.html.fromstring(self.out.read_text("utf-8"))
        return root, root.xpath(f".//div[@data-unit='{uid}']")[0]

    def test_variant_a_hero_meta_grid_and_dossier_card(self):
        """Hero: byline block + key-ledger strip + executive dossier card
        housing the story's takeaways."""
        _, banks = self._unit_root("PILOT-A1-BANKS")
        grid = banks.xpath(".//div[contains(@class,'hero-meta-grid')]")
        self.assertEqual(len(grid), 1, "exactly one hero meta grid per unit")
        card = banks.xpath(".//aside[contains(@class,'dossier-card')]")
        self.assertEqual(len(card), 1)
        self.assertTrue(
            card[0].xpath(".//ul[contains(@class,'takeaways')]/li[@data-src]"),
            "dossier card must house the verified takeaways",
        )
        self.assertIn("核心提要", card[0].text_content())
        ledger = banks.xpath(
            ".//div[contains(@class,'key-ledger-strip')]/div[@data-src]"
        )
        self.assertTrue(ledger, "key-ledger strip carries extracted stats")
        self.assertLessEqual(len(ledger), 3)
        for item in ledger:
            self.assertRegex(item.get("data-src") or "", r"^p\d+$")
        # editorial thesis units house the thesis box in the dossier card
        _, wealth = self._unit_root("PILOT-A16-WEALTH")
        self.assertTrue(
            wealth.xpath(
                ".//aside[contains(@class,'dossier-card')]"
                "//div[contains(@class,'thesis-box')][@data-src]"
            )
        )

    def test_variant_a_chapter_sections_and_sticky_rail(self):
        """Tier 1/2 bodies partition into chapter sections over the
        asymmetric two-column grid with a sticky rail column."""
        _, banks = self._unit_root("PILOT-A1-BANKS")
        sections = banks.xpath(".//section[contains(@class,'editorial-section')]")
        self.assertGreaterEqual(len(sections), 1)
        for i, sec in enumerate(sections, 1):
            nums = sec.xpath(".//div[contains(@class,'section-banner')]"
                             "/span[contains(@class,'section-num')]")
            self.assertEqual(len(nums), 1, f"chapter {i} banner number")
            self.assertIn(f"CHAPTER {i:02d}", nums[0].text_content())
            self.assertTrue(sec.xpath(".//div[contains(@class,'grid-asymmetric')]"))
            self.assertTrue(sec.xpath(".//div[contains(@class,'prose-column')]"))
        self.assertTrue(
            banks.xpath(".//aside[contains(@class,'rail-column')]"
                        "/div[contains(@class,'metric-card')][@data-src]"),
            "rail column carries extracted metric cards",
        )
        # multi-chapter unit: authored subheadings become chapter banners
        _, wealth = self._unit_root("PILOT-A16-WEALTH")
        heads = wealth.xpath(
            ".//div[contains(@class,'section-banner')]"
            "/h2[contains(@class,'sec-h')][@data-ref][@data-src]"
        )
        self.assertEqual(len(heads), 4, "WEALTH has four authored subheadings")
        self.assertEqual(
            [h.get("data-ref") for h in heads], ["p5", "p7", "p11", "p14"]
        )

    def test_variant_a_dramatic_containers_and_sticky_fix(self):
        """Lead paragraph, verdict box, exhibit boxes, text-wrap balance and
        the overflow-x:clip sticky fix ship in the artifact surface."""
        doc = self.out.read_text("utf-8")
        self.assertIn("overflow-x:clip", doc)
        self.assertNotIn("overflow-x:hidden", doc)
        self.assertIn("text-wrap:balance", doc)
        self.assertIn("fonts.googleapis.com", doc)
        self.assertIn("Playfair+Display", doc)
        self.assertIn("JetBrains+Mono", doc)
        _, banks = self._unit_root("PILOT-A1-BANKS")
        self.assertTrue(
            banks.xpath(".//p[contains(@class,'prose-p')]"
                        "[contains(@class,'lead-paragraph')][@data-ref='p1']")
        )
        verdict = banks.xpath(
            ".//div[contains(@class,'verdict-box')]"
            "//p[contains(@class,'prose-p')][@data-ref='p24']"
        )
        self.assertEqual(len(verdict), 1, "closing paragraph closes in the verdict box")
        # every compiled wsj-chart primitive sits inside an exhibit box
        _, condo = self._unit_root("PILOT-A1-CONDO")
        charts = condo.xpath(".//div[contains(@class,'wsj-chart')]")
        self.assertTrue(charts, "CONDO compiles wsj-chart primitives")
        for chart in charts:
            self.assertTrue(
                chart.xpath("ancestor::div[contains(@class,'exhibit-box')]")
            )

    def test_key_stat_cn_scale_keeps_currency_unit(self):
        """Reviewer-G (Issue #5 review): 「1.5万亿美元」 must render as a
        full stat value — never the bare, wrong-magnitude 「1.5万亿」."""
        _, defense = self._unit_root("PILOT-A17-DEFENSE")
        vals = [
            v.text_content().strip()
            for v in defense.xpath(
                ".//div[contains(@class,'metric-val')]"
                "| .//div[contains(@class,'mini-stat-val')]"
            )
        ]
        self.assertIn("1.5万亿美元", vals)
        self.assertNotIn("1.5万亿", vals)

    def test_oracle2_rejects_mutated_metric_card(self):
        """Oracle 2 grounds the extracted rail metric cards: an invented
        value fails certification deterministically (mutation test)."""
        import lxml.html

        from tracer.oracles import oracle_numeric_grounding

        root = lxml.html.fromstring(self.out.read_text("utf-8"))
        victims = root.xpath(".//div[contains(@class,'metric-card')][@data-src]")
        self.assertTrue(victims, "no metric card to mutate")
        for victim in victims:
            val = victim.xpath(".//div[contains(@class,'metric-val')]")
            if val:
                val[0].text = "999%"
                break
        result = oracle_numeric_grounding(root, self.data)
        self.assertFalse(result.passed)
        self.assertTrue(
            any("metric-card" in f for f in result.detail["failures"]),
            f"mutated metric card not rejected: {result.detail['failures']}",
        )

    def test_cert_json_written(self):
        from tracer.oracles import certify

        cert_path = Path(self.tmp.name) / "cert.json"
        certify(self.out, self.data, out_path=cert_path,
                check_budget=False, run_geometry_probe=False)
        loaded = json.loads(cert_path.read_text("utf-8"))
        self.assertTrue(loaded["passed"])
        self.assertEqual(len(loaded["oracles"]), 7)
        doc = self.out.read_text("utf-8")
        self.assertNotIn("findings_by_kind", doc)
        self.assertNotIn("gate-report", doc)


@unittest.skipUnless(HAS_DATA, "2026-10-14 pilot dataset not present")
class Oracle7GeometryProbeCheck(unittest.TestCase):
    """Reviewer-G round 2: the probe must measure the read view too.

    On load the artifact sits in ``overview`` mode where every ``.unit`` is
    ``display:none``; an overflow planted inside ``.unit-body`` is only
    observable after ``setView('read')``.
    """

    @classmethod
    def setUpClass(cls):
        import tracer_pipeline

        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name) / "full.html"
        rc = tracer_pipeline.main([
            "--mode", "full", "--fast", "--output", str(cls.out),
            "--gate-report", str(Path(cls.tmp.name) / "gate.json"),
        ])
        assert rc == 0
        cls.data = load_full_data()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def _planted(self) -> Path:
        import lxml.html

        root = lxml.html.fromstring(self.out.read_text("utf-8"))
        body = root.xpath(".//div[@data-unit='PILOT-A2-HOMES']//div[contains(@class,'unit-body')]")[0]
        body.append(lxml.html.fragment_fromstring(
            '<div style="white-space:nowrap;width:2000px">planted overflow</div>'
        ))
        planted = Path(self.tmp.name) / "planted.html"
        planted.write_text(lxml.html.tostring(root, encoding="unicode"), "utf-8")
        return planted

    @unittest.skipUnless(
        __import__("tracer.oracles", fromlist=["find_chrome"]).find_chrome(),
        "Headless Chrome not available",
    )
    def test_read_view_overflow_is_detected(self):
        from tracer.oracles import certify

        report = certify(
            self._planted(), self.data, check_budget=False, run_geometry_probe=True
        )
        o7 = report.oracle("viewport_geometry_clean_surface_payload")
        self.assertFalse(o7.passed)
        self.assertTrue(
            any("overflow" in f for f in o7.detail["failures"]),
            f"planted read-view overflow not reported: {o7.detail['failures']}",
        )
        # control: the clean artifact passes the same probe
        clean = certify(self.out, self.data, check_budget=False, run_geometry_probe=True)
        self.assertTrue(clean.oracle("viewport_geometry_clean_surface_payload").passed)

    def test_probe_measures_overview_and_read_views(self):
        import json
        import re

        from tracer.oracles import _PROBE_JS

        self.assertIn("setView('read')", _PROBE_JS)
        self.assertIn("setView('overview')", _PROBE_JS)
        self.assertIn("getComputedStyle(el)", _PROBE_JS)
        self.assertIn("display !== 'none'", _PROBE_JS)
        # the probe payload reports one result object per view
        self.assertEqual(len(re.findall(r"out\.\w+ = measure\(\);", _PROBE_JS)), 2)


@unittest.skipUnless(HAS_DATA and HAS_RASTER, "pilot dataset and fitz/PIL required")
class SevenOraclesEndToEndCheck(unittest.TestCase):
    """Real full-issue pipeline + 7-Oracle certification through the CLI."""

    def test_cli_full_mode_certifies(self):
        import tracer_pipeline

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "wsj.html"
            cert = Path(tmp) / "cert.json"
            rc = tracer_pipeline.main([
                "--mode", "full", "--output", str(out),
                "--gate-report", str(Path(tmp) / "gate.json"),
                "--certify", str(cert),
            ])
            self.assertEqual(rc, 0)
            self.assertTrue(out.exists())
            loaded = json.loads(cert.read_text("utf-8"))
            self.assertTrue(loaded["passed"])
            self.assertEqual(loaded["size_bytes"], out.stat().st_size)
            geo = loaded["oracles"]["viewport_geometry_clean_surface_payload"]
            self.assertEqual(geo["size_bytes"], out.stat().st_size)
            if geo["chrome_probe"].get("status") != "skipped":
                cells = geo["chrome_probe"]
                self.assertEqual(len(cells), 6, "2 viewports x 3 language modes")
                for cell, data in cells.items():
                    self.assertTrue(data["passed"], f"geometry probe {cell}")
            # zero Tier 2 takeaway/thesis cites p1 in the shipped artifact
            # (data-src token-split on whitespace/commas)
            import re

            import lxml.html

            root = lxml.html.fromstring(out.read_text("utf-8"))
            lede_cites = [
                el
                for el in root.xpath(
                    './/div[@data-tier="2"]//li[contains(@class,"takeaway")][@data-src]'
                    '| .//div[@data-tier="2"]//div[contains(@class,"thesis-box")][@data-src]'
                )
                if "p1" in re.split(r"[\s,]+", (el.get("data-src") or "").strip())
            ]
            self.assertEqual(lede_cites, [])


if __name__ == "__main__":
    unittest.main()
