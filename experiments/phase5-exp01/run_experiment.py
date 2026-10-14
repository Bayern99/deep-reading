#!/usr/bin/env python3
"""Minimal standalone runner for Phase 5 Experiment 01.

Reproduces:
1. Canonical Source verification (`canonical-E2-001.json`)
2. Golden Baseline (`2026-10-12/editorial-explorations/gold-standard/index.html`) integrity audit
3. Group B (Free HTML) Runs 1..3 integrity audits
4. Group C (Source-Referenced HTML) Runs 1..3 deterministic compilation + integrity audits
"""
from __future__ import annotations

import json
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

import compiler


def main() -> None:
    canonical_path = os.path.join(BASE_DIR, "canonical-E2-001.json")
    with open(canonical_path, encoding="utf-8") as f:
        canonical = json.load(f)

    golden_path = os.path.abspath(
        os.path.join(BASE_DIR, "../../2026-10-12/editorial-explorations/gold-standard/index.html")
    )
    artifacts_dir = os.path.join(BASE_DIR, "artifacts")
    os.makedirs(artifacts_dir, exist_ok=True)

    summary = {"article_id": canonical["article_id"], "source_sha256": canonical["source_sha256"], "results": []}

    # 1. Audit Golden Baseline
    with open(golden_path, encoding="utf-8") as f:
        golden_html = f.read()
    golden_rep = compiler.audit_rendered_html(golden_html, canonical, mode="audit-only")
    summary["results"].append({
        "name": "Phase 4 Golden Baseline",
        "passed_strict_verbatim": len(golden_rep["verbatim_diffs"]) == 0,
        "exact_match_cn": golden_rep["exact_match_cn"],
        "exact_match_en": golden_rep["exact_match_en"],
        "monotonic_order": golden_rep["monotonic_order"],
        "diff_paragraphs": [d["paragraph_id"] for d in golden_rep["verbatim_diffs"]],
    })

    # 2. Audit Group B Runs 1..3
    for run_idx in (1, 2, 3):
        b_path = os.path.join(artifacts_dir, f"group-b-run{run_idx}.html")
        if not os.path.isfile(b_path):
            continue
        with open(b_path, encoding="utf-8") as f:
            b_html = f.read()
        b_rep = compiler.audit_rendered_html(b_html, canonical, mode="audit-only")
        summary["results"].append({
            "name": f"Group B (Free HTML) Run {run_idx}",
            "raw_bytes": len(b_html.encode("utf-8")),
            "passed_strict_verbatim": b_rep["passed"] and len(b_rep["verbatim_diffs"]) == 0,
            "exact_match_cn": b_rep["exact_match_cn"],
            "exact_match_en": b_rep["exact_match_en"],
            "monotonic_order": b_rep["monotonic_order"],
            "diff_paragraphs": [d["paragraph_id"] for d in b_rep["verbatim_diffs"]],
        })

    # 3. Compile & Audit Group C Runs 1..3
    for run_idx in (1, 2, 3):
        c_raw_path = os.path.join(artifacts_dir, f"group-c-run{run_idx}-raw.html")
        c_comp_path = os.path.join(artifacts_dir, f"group-c-run{run_idx}-compiled.html")
        if not os.path.isfile(c_raw_path):
            continue
        with open(c_raw_path, encoding="utf-8") as f:
            c_raw = f.read()
        c_comp, c_rep = compiler.compile_and_inject(c_raw, canonical, strict=True)
        with open(c_comp_path, "w", encoding="utf-8") as f:
            f.write(c_comp)
        summary["results"].append({
            "name": f"Group C (Source-Referenced HTML) Run {run_idx}",
            "raw_bytes": len(c_raw.encode("utf-8")),
            "compiled_bytes": len(c_comp.encode("utf-8")),
            "passed_strict_verbatim": c_rep["passed"] and len(c_rep["verbatim_diffs"]) == 0,
            "exact_match_cn": c_rep["exact_match_cn"],
            "exact_match_en": c_rep["exact_match_en"],
            "monotonic_order": c_rep["monotonic_order"],
            "highlights_applied": len(c_rep["content_breakdown"]["highlights_applied"]),
            "derived_callouts": c_rep["content_breakdown"]["source_derived_count"],
            "ai_editorial_items": c_rep["content_breakdown"]["ai_editorial_items_count"],
            "unverified_editorial_numbers": len(c_rep["content_breakdown"]["unverified_editorial_numbers"]),
        })

    summary_path = os.path.join(artifacts_dir, "experiment-summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
