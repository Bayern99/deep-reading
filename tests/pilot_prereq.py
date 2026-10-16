"""Shared prerequisite for the Issue Artifact suites.

The tracer suites use the pinned 2026-10-14 pilot dataset and the original
print PDF, which live outside this repository (see
[docs/data-policy.md](../docs/data-policy.md)). Each suite guards its
data-backed classes with `@unittest.skipUnless(HAS_DATA, ...)` and sets
`HAS_DATA` from this module.

`unittest` cannot tell "skipped because this machine has no pinned data" apart
from "skipped because the raster libraries are missing": both exit 0, and a
run in which every data-backed test skipped still reports OK. On a checkout
without the pins that is 84 of the 102 tests, so a green `make test` could be
verifying almost nothing.

`require_pilot()` refuses that outcome. It fails the run when the pins are
absent, unless `WSJ_ALLOW_MISSING_PILOT=1` downgrades the refusal to a skip,
which restores the previous behaviour of running the ~18 fixture-free tests
and skipping the rest.

The check lives in the suites rather than the Makefile so that every
documented invocation fails the same way: `make test`, `python -m unittest
discover -s tests`, and `python -m unittest tests/test_vertical_tracer.py`.
"""
from __future__ import annotations

import os
import unittest
from pathlib import Path

from tracer.compose import PDF_PATH, PILOT_ROOT

ALLOW_MISSING = os.environ.get("WSJ_ALLOW_MISSING_PILOT") == "1"

# The paths are absolute and outside this repository; docs/data-policy.md
# records the external backup that holds both.
_HOW_TO_RESTORE = (
    "Set PILOT_ROOT / PDF_PATH in render/tracer/compose.py to the pinned inputs,\n"
    "or point them at the external backup. See docs/data-policy.md (Backup and restore).\n"
    "To run only the fixture-free tests instead, set WSJ_ALLOW_MISSING_PILOT=1."
)


def _missing() -> list[str]:
    return [
        f"{name}: {path}"
        for name, path in (("pilot dataset", PILOT_ROOT), ("print PDF", PDF_PATH))
        if not path.exists()
    ]


def require_pilot() -> bool:
    """Return whether the pinned pilot inputs are present.

    Returns `False` (and the caller's `skipUnless` gates then skip) when the
    inputs are absent and `WSJ_ALLOW_MISSING_PILOT=1` is set. Without that
    variable an absent input fails the run: a suite that cannot check the
    product must not report success.
    """
    missing = _missing()
    if not missing:
        return True
    detail = "\n".join(f"  - {item}" for item in missing)
    message = f"pinned pilot inputs are missing:\n{detail}\n{_HOW_TO_RESTORE}"
    if ALLOW_MISSING:
        return False
    raise RuntimeError(message)
