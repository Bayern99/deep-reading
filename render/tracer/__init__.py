"""WSJ 深读 · Vertical Tracer — primary-vector editorial composition for the 2026-10-14 pilot.

Implements the accepted ADR 0001 three-tier architecture end-to-end:
primary PDF vector signals (`native.json`), union chart re-crops, declarative
`<wsj-chart>` primitives, natural figure anchoring, genre-aware Tier 2
composition, composite columns and a single-file Issue Artifact.

Heavy dependencies (`fitz`, `PIL`) are imported lazily inside functions so the
pure-Python core (charts, verification, composition, shell) stays importable
in any interpreter that has `lxml`.
"""
from __future__ import annotations

from .verify import (
    TracerCompilationError,
    assert_no_forbidden_strings,
    check_highlight_density,
    extract_substantive_numbers,
    ground_numbers,
    norm_number,
    surgical_narrative_completion,
    verify_element_numbers,
)
from .charts import compile_wsj_chart
from .compose import (
    PilotData,
    anchor_figures,
    composite_letters_unit,
    compose_article_unit,
    load_pilot_data,
)
from .shell import build_issue_artifact

__all__ = [
    "TracerCompilationError",
    "assert_no_forbidden_strings",
    "check_highlight_density",
    "compile_wsj_chart",
    "composite_letters_unit",
    "compose_article_unit",
    "anchor_figures",
    "build_issue_artifact",
    "extract_substantive_numbers",
    "ground_numbers",
    "load_pilot_data",
    "norm_number",
    "PilotData",
    "surgical_narrative_completion",
    "verify_element_numbers",
]
