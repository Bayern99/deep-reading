"""Collect strong-model reader output into ``evidence/reader-items.json``.

The reading pass is the strong-model pass that enumerates a page's reading items. It is
run out of band — one reader per page — because the enumeration is a reading
judgement, not a printed fact (see ADR 0003 and FOUNDATION 12). This module only
normalises and validates the reader's answer; it never reads a golden article
map, so the cache it writes is an independent input to ``derive_article_map``.

Reader input contract, per page:

    [{"start_line": "p16-l0215", "kind": "article", "first_line": "...",
      "lines": ["p16-l0215", "p16-l0216", ...]}]

``kind`` must be one of ``READER_KINDS``. Ad pages carry no items.

An item on a continuation page may also carry ``continues``: the ``start_line`` of the
story it carries on, which the pass can answer because the candidate stories are
printed in the start page's jump markers, not because it matched the reprinted
headline. That is what lets a continued story's regions on the later page be exact
instead of inferred.

Either ``lines`` or ``blocks`` may name what the item owns. ``blocks`` are MinerU
middle-json block indices, which ask the pass for paragraphs rather than for every
line: the reference issue has about 100 blocks against 525 lines on a dense front
page. Give one or the other, never both.

``lines`` is optional but is the difference between exact and approximate
placement: it names every line the item owns, on every page it runs on. Without
it the map falls back to inferring rectangles from where the printed text stops,
which reproduces about 39% of the reference issue's rectangles above IoU 0.5.
With it the rectangle follows from the lines themselves.

Usage:
    python -m tracer.build_reader_cache <reader-output-dir>
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from .article_map import READER_KINDS, default_reader_cache_path


def _page_number(path: Path) -> int:
    m = re.search(r"(\d+)", path.stem)
    if not m:
        raise ValueError(f"no page number in {path.name!r}")
    return int(m.group(1))


def collect(reader_dir: str | Path) -> dict[str, list[dict[str, Any]]]:
    """Read one JSON file per page and validate the reader's answer."""
    root = Path(reader_dir)
    pages: dict[str, list[dict[str, Any]]] = {}
    for path in sorted(root.glob("*.json"), key=_page_number):
        page = _page_number(path)
        items = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(items, dict):
            items = [items]
        if not isinstance(items, list):
            raise ValueError(f"{path.name}: reader output must be a list")
        clean: list[dict[str, Any]] = []
        for item in items:
            kind = str(item.get("kind") or "").strip()
            if kind not in READER_KINDS:
                raise ValueError(f"{path.name}: invalid kind {kind!r}")
            line_id = str(item.get("start_line") or "").strip()
            if not line_id:
                raise ValueError(f"{path.name}: item missing start_line")
            entry = {
                "start_line": line_id,
                "kind": kind,
                "first_line": str(item.get("first_line") or "").strip(),
            }
            continues = str(item.get("continues") or "").strip()
            if continues:
                entry["continues"] = continues
            raw_blocks = item.get("blocks")
            if raw_blocks is not None:
                if not isinstance(raw_blocks, list):
                    raise ValueError(f"{path.name}: blocks must be a list")
                blocks = [int(value) for value in raw_blocks]
                if not blocks:
                    raise ValueError(f"{path.name}: blocks must not be empty")
                if item.get("lines"):
                    raise ValueError(
                        f"{path.name}: give lines or blocks for {line_id!r}, not both"
                    )
                entry["blocks"] = blocks
            raw_lines = item.get("lines")
            if raw_lines is not None:
                if not isinstance(raw_lines, list):
                    raise ValueError(f"{path.name}: lines must be a list")
                lines = [str(value).strip() for value in raw_lines if str(value).strip()]
                if line_id not in lines:
                    raise ValueError(
                        f"{path.name}: lines for {line_id!r} must include its start line"
                    )
                entry["lines"] = lines
            # The reader supplies `section` only where the page prints none
            # (the front page). It stays optional.
            section = str(item.get("section") or "").strip()
            if section:
                entry["section"] = section
            clean.append(entry)
        pages[str(page)] = clean
    return pages


def write_cache(reader_dir: str | Path, dest: str | Path) -> Path:
    pages = collect(reader_dir)
    out = Path(dest)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps({"issue": "", "pages": pages}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return out


def main() -> None:
    from .compose import PILOT_ROOT

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reader_dir", help="directory of per-page reader JSON files")
    parser.add_argument(
        "--dest",
        default=str(default_reader_cache_path(PILOT_ROOT)),
        help="where to write the normalised cache",
    )
    args = parser.parse_args()
    print(write_cache(args.reader_dir, args.dest))


if __name__ == "__main__":
    main()
