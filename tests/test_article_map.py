"""Ticket #7: derive the article map from a reader cache plus vector pages.

The reader cache is an independent input — it is produced by a strong-model pass
over each page's vector line table (``tracer.build_reader_cache``), never from a
golden article map. These tests therefore check two different things:

* the printed rules that let deterministic code reject what the reader cannot
  know from a single page (jump headlines, unlabelled captions, image-only pages);
* end-to-end parity with the reference issue, which only runs when a full reader
  cache is present.
"""
from __future__ import annotations

import json
import sys
import unittest
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "render"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from pilot_prereq import require_pilot  # noqa: E402

from tracer.article_map import (  # noqa: E402
    _is_ad_page,
    _is_jump_headline,
    _is_standalone_caption,
    _line_by_id,
    assemble,
    default_reader_cache_path,
    derive_article_map,
    load_natives_from_pilot,
    load_reader_cache,
    stable_run_fingerprint,
)
from tracer.compose import PILOT_ROOT  # noqa: E402
from tracer.routing import SECTION_MAP, canonical_section  # noqa: E402
from tracer.verify import TracerCompilationError  # noqa: E402

HAS_DATA = require_pilot()


def _golden_records() -> list[dict]:
    data = json.loads((PILOT_ROOT / "article-map.json").read_text(encoding="utf-8"))
    return list(data["articles"])


def _native(page: int) -> dict:
    return json.loads((PILOT_ROOT / "evidence" / f"p{page:02d}-native.json").read_text(encoding="utf-8"))


@unittest.skipUnless(HAS_DATA, "pinned pilot dataset required")
class PrintedRulesTests(unittest.TestCase):
    """Rules a single-page reader cannot apply, but the vector layer can."""

    def test_image_only_pages_are_derived_from_text_volume(self) -> None:
        inventory = json.loads((PILOT_ROOT / "inventory.json").read_text(encoding="utf-8"))
        declared = set(inventory["nonarticle_dispositions"]["full_page_advertisements"])
        derived = {p for p in range(1, 37) if _is_ad_page(_native(p))}
        self.assertEqual(derived, declared)

    def test_jump_page_headline_is_not_a_new_story(self) -> None:
        page = _native(4)
        # `Guilfoyle Resigns as Ambassador` is the reprinted headline of
        # PILOT-A1-GREECE, which continues from page one.
        jump = next(l for l in page["lines"] if l["text"].strip() == "Guilfoyle")
        self.assertTrue(_is_jump_headline(page, jump))
        # `Paxton, on Dubai Trip,` genuinely starts on page 4.
        start = next(l for l in page["lines"] if l["text"].strip().startswith("Paxton, on Dubai"))
        self.assertFalse(_is_jump_headline(page, start))

    def test_jump_headline_rule_needs_a_continuation_marker(self) -> None:
        page = _native(16)
        italic_head = next(l for l in page["lines"] if l["text"].strip() == "Readers Revolt Against Trump’s Diesel Plan")
        self.assertFalse(_is_jump_headline(page, italic_head))

    def test_standalone_caption_needs_a_printed_label(self) -> None:
        self.assertTrue(_is_standalone_caption("STANDING TALL"))
        self.assertFalse(_is_standalone_caption("Texas Senate candidate Ken Paxton at the GOP midterm convention"))


@unittest.skipUnless(HAS_DATA, "pinned pilot dataset required")
class ReferenceParityTests(unittest.TestCase):
    """End-to-end parity — requires a full reader cache for the reference issue."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.cache_path = default_reader_cache_path(PILOT_ROOT)
        if not Path(cls.cache_path).exists():
            raise unittest.SkipTest(
                f"no reader cache at {cls.cache_path}; run tracer.build_reader_cache first"
            )
        cls.natives = load_natives_from_pilot(PILOT_ROOT)
        cls.golden = _golden_records()
        cls.items = load_reader_cache(cls.cache_path)
        cls.covered_pages = len(cls.items)
        cls.content_pages = len({a["start_page"] for a in cls.golden})

    def setUp(self) -> None:
        if self.covered_pages < self.content_pages:
            self.skipTest(
                f"reader cache covers {self.covered_pages} pages, reference issue has {self.content_pages}"
            )
        # A real reader supplies `section` where the page prints no banner; the
        # front page prints none, so its items must carry a judged section.
        bannerless = {1}
        lacking = [
            (page, item["start_line"])
            for page, items in self.items.items()
            for item in items
            if page in bannerless and not item.get("section")
        ]
        if lacking:
            self.skipTest(f"reader cache has no judged section for bannerless pages: {lacking[:3]}")

    def test_derive_count(self) -> None:
        derived = derive_article_map(self.natives, self.cache_path)
        self.assertEqual(
            len(derived),
            len(self.golden),
            f"expected {len(self.golden)} records, got {len(derived)}; per-page {Counter(r['start_page'] for r in derived)}",
        )

    def test_start_page_and_section_parity(self) -> None:
        """Every page carries the same multiset of sections as the golden map.

        Titles are not compared: a golden brief title carries its rubric prefix
        (`POLITICS Ossoff Rules Out White House Run`) while the printed headline
        line does not, so title equality would test a formatting convention
        rather than the map. Count and section together pin the mapping.
        """
        derived = derive_article_map(self.natives, self.cache_path)

        def per_page(records):
            out = {}
            for r in records:
                out.setdefault(r["start_page"], []).append(r["section"])
            return {p: sorted(v) for p, v in out.items()}

        g, d = per_page(self.golden), per_page(derived)
        mismatches = [
            (page, g.get(page), d.get(page))
            for page in sorted(set(g) | set(d))
            if g.get(page) != d.get(page)
        ]
        self.assertEqual(mismatches, [], f"per-page section sets differ: {mismatches[:6]}")

    def test_all_pages_match_golden(self) -> None:
        """Every multi-page story resolves the pages its printed markers name.

        The derived title is the headline's first printed line; the golden title
        is the whole headline, so matching is by substring after normalisation.
        """
        from tracer.article_map import _norm_title

        derived = derive_article_map(self.natives, self.cache_path)
        golden_multi = [g for g in self.golden if len(g.get("all_pages") or []) > 1]
        self.assertEqual(len(golden_multi), 12)
        mismatches = []
        used: set[str] = set()
        for g in golden_multi:
            want = _norm_title(g.get("original_title") or "")
            candidates = [
                r for r in derived
                if r["start_page"] == g["start_page"]
                and r["id"] not in used
                and _norm_title(r["original_title"])
                and (
                    _norm_title(r["original_title"]) in want
                    or want.startswith(_norm_title(r["original_title"]))
                )
            ]
            candidates.sort(key=lambda r: -len(_norm_title(r["original_title"])))
            if not candidates:
                mismatches.append((g["id"], g["all_pages"], "no candidate"))
                continue
            record = candidates[0]
            used.add(record["id"])
            if record["all_pages"] != g["all_pages"]:
                mismatches.append((g["id"], g["all_pages"], record["all_pages"]))
        self.assertEqual(mismatches, [], f"all_pages mismatches: {mismatches}")

    def _start_y(self, record) -> float:
        from tracer.article_map import _line_by_id

        native = self.natives[record["start_page"]]
        line = _line_by_id(native, record["start_line_id"])
        return float(line["bbox"][1])

    def test_continuation_evidence_cites_the_printed_markers(self) -> None:
        """Each multi-page story cites both marker directions with a line id."""
        derived = derive_article_map(self.natives, self.cache_path)
        for record in derived:
            if len(record["all_pages"]) < 2:
                continue
            evidence = record["continuation_evidence"]
            self.assertGreaterEqual(len(evidence), 2, record["original_title"])
            self.assertEqual(
                {entry["page"] for entry in evidence}, set(record["all_pages"])
            )
            for entry in evidence:
                self.assertTrue(entry["line_id"])
                self.assertEqual(len(entry["bbox_points"]), 4)
                self.assertTrue(entry["raw"])

    def test_composites_derive_by_printed_rubric(self) -> None:
        """The five Composite Columns group by rubric, not by a table of ids."""
        from tracer.article_map import derive_composites

        derived = derive_article_map(self.natives, self.cache_path)
        units = {u["unit_id"].split("-", 1)[1]: u for u in derive_composites(derived)}
        self.assertEqual(
            sorted(units),
            ["CORRECTIONS", "LETTERS", "STOCKSPOTLIGHT", "USWATCH", "WORLDWATCH"],
        )
        sizes = {key: len(unit["members"]) for key, unit in units.items()}
        # Four match the golden table exactly. Spotlight derives four, not five:
        # the reference issue's hand-made table also groups `In Market History`,
        # whose printed rubric is `Money & Investing`. That one grouping is an
        # editorial call the paper does not print, so it is left out rather than
        # special-cased. It routes on its own and still lands in Tier 3.
        self.assertEqual(
            sizes,
            {"LETTERS": 9, "STOCKSPOTLIGHT": 4, "USWATCH": 3, "WORLDWATCH": 2, "CORRECTIONS": 2},
        )
        # A lone item under a composite rubric is not a column.
        all_members = [m for unit in units.values() for m in unit["members"]]
        self.assertEqual(len(all_members), len(set(all_members)))

    def test_routing_tier_parity_from_derived_map(self) -> None:
        """Curation over a derived map reproduces the golden tier per item."""
        from tracer.article_map import _norm_title, derive_composites
        from tracer.routing import route_issue

        derived = derive_article_map(self.natives, self.cache_path)
        composites = {u["unit_id"]: u for u in derive_composites(derived)}
        routes = route_issue({r["id"]: r for r in derived}, self.natives, composites=composites)
        tier_by_id = {aid: r.tier for r in routes for aid in r.article_ids}

        from tracer.compose import load_full_data

        data = load_full_data()
        golden_tier = {aid: r.tier for r in route_issue(data.articles, data.natives) for aid in r.article_ids}

        matched = mismatched = 0
        used: set[str] = set()
        for g in self.golden:
            want = _norm_title(g.get("original_title") or "")
            candidates = [
                r for r in derived
                if r["start_page"] == g["start_page"]
                and r["id"] not in used
                and _norm_title(r["original_title"])
                and _norm_title(r["original_title"]) in want
            ]
            if not candidates:
                continue
            candidates.sort(key=lambda r: -len(_norm_title(r["original_title"])))
            record = candidates[0]
            used.add(record["id"])
            if tier_by_id.get(record["id"]) == golden_tier.get(g["id"]):
                matched += 1
            else:
                mismatched += 1
        self.assertGreaterEqual(matched, 78, f"matched {matched}, mismatched {mismatched}")
        self.assertEqual(mismatched, 0)
        self.assertEqual(sum(1 for r in routes if r.tier == 1), 8)

    def test_perturbed_marker_changes_all_pages(self) -> None:
        """Editing one printed jump marker must change the derived link.

        The reader cache is untouched, so the only thing that can move a story's
        continuation page is the rule reading the marker. A rule that had
        memorised the reference issue would keep answering page 4.
        """
        import copy

        baseline = derive_article_map(self.natives, self.cache_path)
        before = sorted(tuple(r["all_pages"]) for r in baseline if len(r["all_pages"]) > 1)
        self.assertEqual(before.count((1, 4)), 2, "expected two stories jumping to page 4")

        perturbed = copy.deepcopy(self.natives)
        page = perturbed[1]
        target = next(
            line for line in page["lines"] if line["text"].strip() == "PleaseturntopageA4"
        )
        target["text"] = "PleaseturntopageA12"

        after = sorted(
            tuple(r["all_pages"]) for r in derive_article_map(perturbed, self.cache_path)
            if len(r["all_pages"]) > 1
        )
        self.assertEqual(after.count((1, 4)), 1)
        self.assertEqual(after.count((1, 12)), 1)
        self.assertNotEqual(before, after)

    def test_a_marker_naming_an_unreachable_folio_raises(self) -> None:
        """A jump marker pointing outside the issue is a broken page, not a page to drop."""
        import copy

        perturbed = copy.deepcopy(self.natives)
        page = perturbed[1]
        target = next(
            line for line in page["lines"] if line["text"].strip() == "PleaseturntopageA4"
        )
        target["text"] = "PleaseturntopageA99"
        with self.assertRaisesRegex(TracerCompilationError, "unreachable folio"):
            derive_article_map(perturbed, self.cache_path)

    def test_type_accuracy_beats_the_model_baseline(self) -> None:
        """Derived types beat the measured Jev baseline on the reference issue.

        Jev scored 86.0% exact and 93.0% tier. The reader supplies each item's
        kind and a printed rubric closes the `brief` boundary. Measured here so a
        regression in either half shows up.
        """
        from tracer.article_map import _norm_title

        tier2 = {"article", "analysis", "opinion", "editorial", "review", "sidebar"}

        def tier_of(kind: str) -> int:
            return 2 if kind in tier2 else 3

        derived = derive_article_map(self.natives, self.cache_path)
        used: set[str] = set()
        exact = tier = total = 0
        for g in self.golden:
            want = _norm_title(g.get("original_title") or "")
            candidates = [
                r for r in derived
                if r["start_page"] == g["start_page"]
                and r["id"] not in used
                and _norm_title(r["original_title"])
                and _norm_title(r["original_title"]) in want
            ]
            if not candidates:
                continue
            candidates.sort(key=lambda r: -len(_norm_title(r["original_title"])))
            record = candidates[0]
            used.add(record["id"])
            total += 1
            exact += record["type"] == g["type"]
            tier += tier_of(record["type"]) == tier_of(g["type"])
        self.assertGreaterEqual(total, 78, f"matched only {total} golden items")
        self.assertGreaterEqual(exact / total, 0.86, f"exact {exact}/{total}")
        self.assertGreaterEqual(tier / total, 0.93, f"tier {tier}/{total}")

    def test_flagship_set_from_derived_records(self) -> None:
        """Tier 1 is reproducible from a derived map, with no paragraphs.

        The non-front-page branch is decided by printed lead position (leftmost
        column, top half) rather than body length, because a derived map has no
        reconstructed paragraphs to count.
        """
        from tracer.routing import is_flagship

        derived = derive_article_map(self.natives, self.cache_path)
        flagships = [r for r in derived if is_flagship(r, self.natives)]
        self.assertEqual(len(flagships), 8)
        front = [r for r in flagships if r["start_page"] == 1]
        business = [r for r in flagships if r["start_page"] == 19]
        self.assertEqual(len(front), 6)
        self.assertEqual(len(business), 2)

    def test_every_section_is_canonical(self) -> None:
        for record in derive_article_map(self.natives, self.cache_path):
            self.assertIn(record["section"], SECTION_MAP)
            canonical_section(record["section"])

    def test_ids_stable_across_two_runs(self) -> None:
        first = derive_article_map(self.natives, self.cache_path)
        second = derive_article_map(self.natives, self.cache_path)
        self.assertEqual([r["id"] for r in first], [r["id"] for r in second])
        self.assertEqual(stable_run_fingerprint(first), stable_run_fingerprint(second))


    def test_exact_regions_are_required_when_asked(self) -> None:
        """The compile seam refuses an inferred column set rather than shipping it."""
        with self.assertRaisesRegex(TracerCompilationError, "inferred regions"):
            derive_article_map(self.natives, self.cache_path, require_exact_regions=True)

    def test_a_missing_reading_pass_cache_raises(self) -> None:
        """An issue with no pass is a missing input, not a zero-item issue."""
        natives = load_natives_from_pilot(SECOND_ISSUE)
        with self.assertRaisesRegex(TracerCompilationError, "no Reading Pass cache"):
            derive_article_map(natives, pilot_root=SECOND_ISSUE)


@unittest.skipUnless(HAS_DATA, "pinned pilot dataset required")
class FailLoudTests(unittest.TestCase):
    def test_unknown_section_raises(self) -> None:
        natives = load_natives_from_pilot(PILOT_ROOT)
        page = _native(1)  # front page prints no section banner
        line = next(l for l in page["lines"] if l["text"].strip().startswith("Trump’s Ambassador"))
        items = {1: [{"start_line": line["id"], "kind": "article", "first_line": line["text"], "section": "Not A Real Section"}]}
        with self.assertRaises(TracerCompilationError):
            assemble(items, natives)

    def test_unbindable_start_line_raises(self) -> None:
        natives = load_natives_from_pilot(PILOT_ROOT)
        items = {1: [{"start_line": "p1-l9999", "kind": "article", "first_line": "x"}]}
        with self.assertRaises(TracerCompilationError):
            assemble(items, natives)

    def test_invalid_kind_raises(self) -> None:
        natives = load_natives_from_pilot(PILOT_ROOT)
        page = _native(1)
        line = page["lines"][0]
        items = {1: [{"start_line": line["id"], "kind": "telegram", "first_line": line["text"]}]}
        with self.assertRaises(TracerCompilationError):
            assemble(items, natives)


SECOND_ISSUE = Path("/Users/dmus/Documents/deep-reading/second-issue-pilot-2026-10-10")


@unittest.skipUnless(
    (SECOND_ISSUE / "evidence").is_dir(), "second issue pages not present"
)
class SecondIssueScaleTests(unittest.TestCase):
    """Scale check on a larger, different issue — a smoke check, not parity.

    There is no golden article map for this issue, so nothing here asserts item
    counts. What it does assert is that the parts that must generalise do: the
    folio index covers every page across five stacks, the jump markers pair up,
    and the column grid recovers on editorial pages.
    """

    @classmethod
    def setUpClass(cls) -> None:
        from tracer.article_map import load_natives_from_pilot

        cls.natives = load_natives_from_pilot(SECOND_ISSUE)

    def test_issue_is_larger_than_the_reference(self) -> None:
        self.assertGreaterEqual(len(self.natives), 55)

    def test_folio_index_covers_every_page_and_every_stack(self) -> None:
        from tracer.article_map import _folio_index

        index = _folio_index(self.natives)
        self.assertEqual(len(index), len(self.natives))
        stacks = {stack for stack, _folio_no in index}
        self.assertEqual(stacks, {"A", "B", "C", "D", "R"})

    def test_jump_markers_pair_up(self) -> None:
        from tracer.article_map import _continuation_markers

        forward = sum(len(_continuation_markers(p)["forward"]) for p in self.natives.values())
        backward = sum(len(_continuation_markers(p)["backward"]) for p in self.natives.values())
        self.assertEqual(forward, 11)
        self.assertEqual(backward, 11)

    def test_column_grid_recovers_on_editorial_pages(self) -> None:
        from tracer.article_map import _column_grid, _is_ad_page

        missing = [
            page
            for page, native in self.natives.items()
            if not _column_grid(native) and not _is_ad_page(native)
        ]
        # One dense data page (commodities/ag tables) has no body-text columns.
        self.assertLessEqual(len(missing), 1, f"pages without a grid: {missing}")


class ReaderLineRegionTests(unittest.TestCase):
    """Regions follow the reader's line set, not an inference from text flow.

    A reader answers which lines an item owns. The rectangle then follows from the
    column grid and those lines, which is the only exact route: which columns a
    story occupies is not printed, and inferring it from where text stops
    reproduced 39% of the reference issue's rectangles.
    """

    @staticmethod
    def _line(line_id: str, x0: float, y0: float, x1: float, y1: float) -> dict:
        return {
            "id": line_id,
            "bbox": [x0, y0, x1, y1],
            "text": "ordinary body text",
            "chars": [{"bbox": [x0, y0, x1, y1], "c": "o", "font": "ExchangeBook", "size": 8.4}],
        }

    def _page(self, lines: list[dict]) -> dict:
        return {"page": 7, "height": 1600, "lines": lines}

    def test_one_rectangle_per_column_sharing_the_band(self) -> None:
        from tracer.article_map import regions_from_lines

        lines = [
            self._line(f"c0-{i}", 40.0, 100.0 + 12 * i, 178.0, 112.0 + 12 * i)
            for i in range(6)
        ] + [
            self._line(f"c1-{i}", 188.0, 100.0 + 12 * i, 326.0, 112.0 + 12 * i)
            for i in range(6)
        ]
        regions = regions_from_lines({7: self._page(lines)}, [l["id"] for l in lines])

        self.assertEqual(
            [r["bbox"] for r in regions],
            [[40.0, 100.0, 178.0, 172.0], [188.0, 100.0, 326.0, 172.0]],
        )
        self.assertEqual([r["column_origin"] for r in regions], [40.0, 188.0])

    def test_line_starting_mid_measure_does_not_define_a_column(self) -> None:
        from tracer.article_map import regions_from_lines

        lines = [
            self._line(f"c0-{i}", 40.0, 100.0 + 12 * i, 178.0, 112.0 + 12 * i)
            for i in range(6)
        ] + [
            self._line(f"c1-{i}", 188.0, 100.0 + 12 * i, 326.0, 112.0 + 12 * i)
            for i in range(6)
        ] + [self._line("pull-quote", 136.0, 400.0, 300.0, 412.0)]
        regions = regions_from_lines({7: self._page(lines)}, [l["id"] for l in lines])

        self.assertEqual([r["bbox"][0] for r in regions], [40.0, 188.0])
        # The pull quote still counts towards the band, which is what stretches it.
        self.assertEqual(regions[0]["bbox"][3], 412.0)

    def test_spanning_rule_does_not_widen_its_column(self) -> None:
        from tracer.article_map import regions_from_lines

        lines = [
            self._line(f"c0-{i}", 40.0, 100.0 + 12 * i, 178.0, 112.0 + 12 * i)
            for i in range(6)
        ] + [
            self._line(f"c1-{i}", 188.0, 100.0 + 12 * i, 326.0, 112.0 + 12 * i)
            for i in range(6)
        ] + [self._line("rule", 40.0, 500.0, 900.0, 501.0)]
        regions = regions_from_lines({7: self._page(lines)}, [l["id"] for l in lines])

        self.assertEqual(regions[0]["bbox"][2], 200.0)

    def test_a_split_line_fragment_does_not_create_a_column(self) -> None:
        """A justified line split into style runs leaves fragments starting mid-measure.

        Snapping one of those to the next column produced an inverted, empty
        rectangle on page 20 ("woman / added. / Shares / fell").
        """
        from tracer.article_map import regions_from_lines

        lines = [
            self._line(f"c0-{i}", 40.0, 100.0 + 12 * i, 178.0, 112.0 + 12 * i)
            for i in range(6)
        ] + [
            self._line(f"c1-{i}", 188.0, 100.0 + 12 * i, 326.0, 112.0 + 12 * i)
            for i in range(6)
        ] + [self._line("fragment", 164.0, 160.0, 326.0, 172.0)]
        regions = regions_from_lines({7: self._page(lines)}, [l["id"] for l in lines])

        self.assertEqual([r["column_origin"] for r in regions], [40.0, 188.0])
        for region in regions:
            self.assertLess(region["bbox"][0], region["bbox"][2])

    def test_lines_spanning_two_pages_yield_rectangles_on_both(self) -> None:
        from tracer.article_map import regions_from_lines

        first = self._page([self._line(f"p7-{i}", 40.0, 100.0 + 12 * i, 178.0, 112.0 + 12 * i) for i in range(6)])
        second = dict(self._page([self._line(f"p9-{i}", 188.0, 300.0 + 12 * i, 326.0, 312.0 + 12 * i) for i in range(6)]), page=9)
        ids = [l["id"] for l in first["lines"]] + [l["id"] for l in second["lines"]]
        regions = regions_from_lines({7: first, 9: second}, ids)

        self.assertEqual([r["page"] for r in regions], [7, 9])
        self.assertEqual(regions[1]["bbox"], [188.0, 300.0, 326.0, 372.0])


class ReaderCacheContractTests(unittest.TestCase):
    """The reader may publish a line set; the cache validates it, never guesses."""

    def _collect(self, item: dict) -> dict:
        import tempfile
        from tracer.build_reader_cache import collect

        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "p7.json").write_text(json.dumps([item]), encoding="utf-8")
            return collect(tmp)

    def test_lines_are_kept_when_the_start_line_is_included(self) -> None:
        pages = self._collect(
            {"start_line": "p7-l0001", "kind": "article", "lines": ["p7-l0001", "p7-l0002", ""]}
        )
        self.assertEqual(pages["7"][0]["lines"], ["p7-l0001", "p7-l0002"])

    def test_lines_missing_the_start_line_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "must include its start line"):
            self._collect({"start_line": "p7-l0001", "kind": "article", "lines": ["p7-l0002"]})

    def test_lines_must_be_a_list(self) -> None:
        with self.assertRaisesRegex(ValueError, "lines must be a list"):
            self._collect({"start_line": "p7-l0001", "kind": "article", "lines": "p7-l0001"})

    def test_continues_is_kept_for_a_continuation_page_item(self) -> None:
        pages = self._collect(
            {"start_line": "p20-l0821", "kind": "article", "continues": "p19-l0401",
             "blocks": [14, 15, 16]}
        )
        self.assertEqual(pages["7"][0]["continues"], "p19-l0401")
        self.assertEqual(pages["7"][0]["blocks"], [14, 15, 16])

    def test_absent_lines_leave_the_item_unchanged(self) -> None:
        pages = self._collect({"start_line": "p7-l0001", "kind": "article"})
        self.assertNotIn("lines", pages["7"][0])


class TypeEvidenceTests(unittest.TestCase):
    """A type is confident when the page agrees with it, not because a model said so."""

    def test_printed_rubric_makes_the_type_certain(self) -> None:
        from tracer.article_map import _type_evidence

        confidence, reasons = _type_evidence("Markets / Stock Spotlight", "brief", [], [7])
        self.assertEqual(confidence, 1.0)
        self.assertEqual(reasons, [])

    def test_rubric_contradicting_the_judged_kind_is_flagged(self) -> None:
        from tracer.article_map import _type_evidence

        confidence, reasons = _type_evidence("Markets / Stock Spotlight", "article", [{"page": 7, "bbox": [40.0, 100.0, 160.0, 900.0], "column_origin": 40.0}], [7])
        self.assertEqual(confidence, 0.5)
        self.assertEqual(reasons, ["rubric-disagrees"])

    def test_article_with_a_tiny_printed_extent_is_flagged(self) -> None:
        from tracer.article_map import _type_evidence

        tiny = [{"page": 7, "bbox": [40.0, 100.0, 160.0, 108.0], "column_origin": 40.0}]
        confidence, reasons = _type_evidence("U.S. News", "article", tiny, [7])
        self.assertEqual(confidence, 0.5)
        self.assertEqual(reasons, ["article-but-tiny"])

    def test_brief_spanning_two_pages_is_flagged(self) -> None:
        from tracer.article_map import _type_evidence

        big = [{"page": 7, "bbox": [40.0, 100.0, 160.0, 900.0], "column_origin": 40.0}]
        confidence, reasons = _type_evidence("U.S. News", "brief", big, [7, 9])
        self.assertEqual(confidence, 0.5)
        self.assertEqual(reasons, ["brief-but-multi-page"])

    def test_a_judged_type_the_page_does_not_contradict_stands(self) -> None:
        from tracer.article_map import _type_evidence

        big = [{"page": 7, "bbox": [40.0, 100.0, 160.0, 900.0], "column_origin": 40.0}]
        confidence, reasons = _type_evidence("U.S. News", "article", big, [7])
        self.assertEqual(confidence, 0.9)
        self.assertEqual(reasons, [])


class BlockAnswerTests(unittest.TestCase):
    """A Reading Pass may answer in blocks; the lines follow by containment."""

    @staticmethod
    def _page() -> dict:
        def line(line_id: str, y: float) -> dict:
            return {
                "id": line_id,
                "bbox": [100.0, y, 300.0, y + 12.0],
                "text": "ordinary body text",
                "chars": [{"bbox": [100.0, y, 300.0, y + 12.0], "c": "o", "font": "ExchangeBook", "size": 8.4}],
            }

        return {"page": 7, "width": 800.0, "height": 1000.0, "lines": [line("l1", 100.0), line("l2", 120.0)]}

    def test_the_named_block_contributes_its_lines(self) -> None:
        from tracer.article_map import lines_from_blocks

        blocks = [(0, "doc_title", [90.0, 95.0, 310.0, 140.0])]
        self.assertEqual(lines_from_blocks(self._page(), blocks, [0]), ["l1", "l2"])

    def test_an_unnamed_block_contributes_nothing(self) -> None:
        from tracer.article_map import lines_from_blocks

        blocks = [(0, "doc_title", [90.0, 95.0, 310.0, 140.0])]
        self.assertEqual(lines_from_blocks(self._page(), blocks, [9]), [])


if __name__ == "__main__":
    unittest.main()
