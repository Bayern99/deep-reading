#!/usr/bin/env python3
"""Exercise the Issue Artifact CLI without writing the production /tmp outputs."""
from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIPELINE = ROOT / "render" / "tracer_pipeline.py"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fast",
        action="store_true",
        default=True,
        help="Skip PDF raster (default). Pass --no-fast for a full compile in the sandbox.",
    )
    parser.add_argument("--no-fast", dest="fast", action="store_false")
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="wsj-tracer-smoke-") as temp:
        out = Path(temp) / "issue.html"
        gate = Path(temp) / "gate-report.json"
        cmd = [
            sys.executable,
            str(PIPELINE),
            "--mode",
            "full",
            "--output",
            str(out),
            "--gate-report",
            str(gate),
        ]
        if args.fast:
            cmd.append("--fast")
        subprocess.run(cmd, cwd=ROOT, check=True)
        html = out.read_text(encoding="utf-8")
        if "<!DOCTYPE html>" not in html and "<html" not in html.lower():
            raise SystemExit("Smoke failed: output is not HTML")
        if not gate.is_file():
            raise SystemExit("Smoke failed: missing gate-report.json")
        mode = "fast" if args.fast else "full"
        print(f"Smoke passed: tracer --mode full ({mode}), {out.stat().st_size} bytes, gate report written.")


if __name__ == "__main__":
    main()
