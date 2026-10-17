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

    def test_every_section_is_canonical(self) -> None:
        for record in derive_article_map(self.natives, self.cache_path):
            self.assertIn(record["section"], SECTION_MAP)
            canonical_section(record["section"])

    def test_ids_stable_across_two_runs(self) -> None:
        first = derive_article_map(self.natives, self.cache_path)
        second = derive_article_map(self.natives, self.cache_path)
        self.assertEqual([r["id"] for r in first], [r["id"] for r in second])
        self.assertEqual(stable_run_fingerprint(first), stable_run_fingerprint(second))


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


if __name__ == "__main__":
    unittest.main()
