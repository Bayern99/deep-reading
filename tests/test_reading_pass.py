"""Ticket #18: bundle, validate and merge a Reading Pass answer without a model."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "render"))

from tracer.reading_pass import (  # noqa: E402
    build_bundle,
    coverage,
    merge,
    validate,
    write_cache,
)


def _line(
    line_id: str,
    x0: float,
    y0: float,
    text: str = "ordinary body text",
    size: float = 8.4,
    font: str = "ExchangeBook",
) -> dict:
    return {
        "id": line_id,
        "bbox": [x0, y0, x0 + 120.0, y0 + 10.0],
        "text": text,
        "chars": [
            {
                "bbox": [x0, y0, x0 + 120.0, y0 + 10.0],
                "c": "o",
                "font": font,
                "size": size,
            }
        ],
    }


def _fixture() -> tuple[dict, list[tuple[int, str, list[float]]]]:
    native = {
        "page": 7,
        "width": 800,
        "height": 1000,
        "lines": [
            _line("title", 40, 101, "A Headline", 24.0, "ExchangeBanner"),
            _line("b1", 40, 131),
            _line("b2", 40, 143),
            _line("b3", 40, 155),
            _line("d1", 40, 241),
            _line("marker", 40, 401, "Continuedfromthepriorpage"),
        ],
    }
    blocks = [
        (0, "doc_title", [40, 100, 200, 120]),
        (1, "text", [40, 130, 200, 220]),
        (2, "table", [40, 240, 200, 300]),
    ]
    return native, blocks


class BundleTests(unittest.TestCase):
    def test_bundle_carries_block_lines_markers_and_kinds(self) -> None:
        native, blocks = _fixture()
        bundle = build_bundle(native, blocks)
        self.assertEqual(bundle["page"], 7)
        self.assertEqual([block["index"] for block in bundle["blocks"]], [0, 1, 2])
        self.assertEqual(
            [line["id"] for line in bundle["blocks"][1]["lines"]], ["b1", "b2", "b3"]
        )
        self.assertEqual(bundle["markers"]["backward"][0]["folio"], "prior")
        self.assertIn("article", bundle["kinds"])

    def test_coverage_reports_block_and_assigned_lines(self) -> None:
        native, blocks = _fixture()
        bundle = build_bundle(native, blocks)
        answers = {7: {"page": 7, "items": [{"start_line": "title", "blocks": [0, 1]}]}}
        row = coverage({7: bundle}, answers, {7: native})[0]
        self.assertEqual(row["text_lines"], 6)
        self.assertAlmostEqual(row["block_coverage"], 5 / 6, places=3)
        self.assertAlmostEqual(row["assigned_coverage"], 4 / 6, places=3)


class ValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        native, blocks = _fixture()
        self.bundle = build_bundle(native, blocks)
        self.bundles = {7: self.bundle}

    def findings(self, items: list[dict]) -> list[dict]:
        return validate(self.bundles, {7: {"page": 7, "items": items}})

    def test_clean_answer_has_no_findings(self) -> None:
        self.assertEqual(
            self.findings(
                [
                    {
                        "start_line": "title",
                        "kind": "article",
                        "first_line": "A Headline",
                        "section": "U.S. News",
                        "blocks": [0, 1],
                    }
                ]
            ),
            [],
        )

    def test_unknown_blocks_warn_and_cross_item_duplicates_error(self) -> None:
        findings = self.findings(
            [
                {"start_line": "title", "blocks": [0, 99]},
                {"start_line": "b2", "blocks": [0]},
            ]
        )
        levels = [(f["level"], f["detail"]) for f in findings]
        self.assertTrue(any(level == "warn" and "unknown blocks" in detail for level, detail in levels))
        self.assertTrue(any(level == "error" and "block 0" in detail for level, detail in levels))

    def test_empty_blocks_are_dropped(self) -> None:
        findings = self.findings([{"start_line": "title", "blocks": []}])
        self.assertEqual([f["level"] for f in findings], ["drop"])

    def test_table_only_and_continuation_body_are_dropped(self) -> None:
        findings = self.findings(
            [
                {"start_line": "d1", "blocks": [2]},
                {"start_line": "b1", "blocks": [1]},
            ]
        )
        self.assertEqual(
            [(f["level"], f["detail"]) for f in findings],
            [("drop", "d1: table-only"), ("drop", "b1: continuation body")],
        )

    def test_section_variants_are_normalized(self) -> None:
        findings = self.findings(
            [{"start_line": "title", "section": "REVIEW", "blocks": [0, 1]}]
        )
        self.assertEqual(findings, [])


class MergeTests(unittest.TestCase):
    def setUp(self) -> None:
        native, blocks = _fixture()
        native["lines"] = [line for line in native["lines"] if line["id"] != "marker"]
        self.bundles = {7: build_bundle(native, blocks)}

    def test_merge_drops_bad_items_and_keeps_continues(self) -> None:
        answers = {
            7: {
                "page": 7,
                "items": [
                    {
                        "start_line": "title",
                        "kind": "article",
                        "first_line": "A Headline",
                        "section": "REVIEW",
                        "blocks": [0, 1],
                    },
                    {"start_line": "d1", "blocks": [2]},
                    {"start_line": "b2", "blocks": [1], "continues": "p1-l1"},
                ],
            }
        }
        merged = merge({"issue": "", "pages": {}}, self.bundles, answers)
        items = merged["pages"]["7"]
        self.assertEqual([item["start_line"] for item in items], ["title", "b2"])
        self.assertEqual(items[0]["section"], "Review")
        self.assertEqual(items[0]["blocks"], [0, 1])
        self.assertEqual(items[1]["continues"], "p1-l1")

    def test_write_cache_refuses_overwrite_and_backs_up(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "reader-items.json"
            write_cache({"issue": "", "pages": {"1": []}}, target)
            with self.assertRaises(SystemExit):
                write_cache({"issue": "", "pages": {"1": []}}, target)
            write_cache({"issue": "", "pages": {"1": []}}, target, force=True)
            backups = list(Path(tmp).glob("reader-items.pre-merge-*.json"))
            self.assertEqual(len(backups), 1)
            self.assertEqual(json.loads(target.read_text())["pages"], {"1": []})


if __name__ == "__main__":
    unittest.main()
