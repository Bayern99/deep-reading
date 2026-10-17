"""Reading Pass orchestration: page bundles, answer validation, cache merge.

The per-page answers are a reading judgement and stay out of band; this module
only moves data. It builds the bundle the pass reads, checks the answer against
it, merges validated answers into the issue's reader cache, and reports the
derived map.

Usage:
    python -m tracer.reading_pass bundle --pilot-root P --out DIR
    python -m tracer.reading_pass validate --bundles DIR --answers DIR
    python -m tracer.reading_pass merge --pilot-root P --bundles DIR --answers DIR
    python -m tracer.reading_pass report --pilot-root P --cache PATH
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .article_map import (
    READER_KINDS,
    _continuation_markers,
    _is_ad_page,
    _section_head_text,
    default_mineru_dir,
    default_reader_cache_path,
    derive_article_map,
    lines_from_blocks,
    load_mineru_blocks,
    load_natives_from_pilot,
    load_reader_cache,
)
from .routing import SECTION_MAP

BUNDLE_VERSION = 1
SECTION_ALIASES = {key.lower(): key for key in SECTION_MAP}
DROP_TYPES = {"table", "chart"}


def _json_markers(native: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    markers = _continuation_markers(native)
    return {
        side: [
            {
                "folio": entry["folio"],
                "text": (entry["line"].get("text") or "").strip(),
                "bbox": [round(float(v), 1) for v in entry["line"]["bbox"]],
            }
            for entry in entries
        ]
        for side, entries in markers.items()
    }


def _bundle_blocks(
    native: dict[str, Any], blocks: list[tuple[int, str, list[float]]]
) -> list[dict[str, Any]]:
    """MinerU blocks with the native lines they contain, in reading order."""
    out: list[dict[str, Any]] = []
    line_by_id = {line["id"]: line for line in native.get("lines") or []}
    for index, block_type, bbox in blocks:
        line_ids = lines_from_blocks(native, blocks, [index])
        lines = []
        for line_id in line_ids:
            line = line_by_id.get(line_id)
            if line is None or not (line.get("text") or "").strip():
                continue
            lines.append(
                {
                    "id": line_id,
                    "text": line["text"].strip(),
                    "bbox": [round(float(v), 1) for v in line["bbox"]],
                }
            )
        out.append(
            {
                "index": index,
                "type": block_type,
                "bbox": [round(float(v), 1) for v in bbox],
                "text": " ".join(line["text"] for line in lines),
                "lines": lines,
            }
        )
    return out


def build_bundle(
    native: dict[str, Any],
    blocks: list[tuple[int, str, list[float]]],
    items: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """One page's pass input: block text/lines, markers, section, item list."""
    return {
        "version": BUNDLE_VERSION,
        "page": int(native.get("page") or 0),
        "width": native.get("width"),
        "height": native.get("height"),
        "section_head": _section_head_text(native),
        "markers": _json_markers(native),
        "kinds": sorted(READER_KINDS),
        "items": list(items or []),
        "blocks": _bundle_blocks(native, blocks),
    }


def build_bundles(
    pilot_root: str | Path,
    *,
    cache_path: str | Path | None = None,
    dest: str | Path,
) -> dict[int, dict[str, Any]]:
    """Write one bundle per content page of an issue."""
    root = Path(pilot_root)
    natives = load_natives_from_pilot(root)
    blocks = load_mineru_blocks(default_mineru_dir(root))
    items = (
        load_reader_cache(cache_path)
        if cache_path is not None and Path(cache_path).exists()
        else {}
    )
    out = Path(dest)
    out.mkdir(parents=True, exist_ok=True)
    bundles: dict[int, dict[str, Any]] = {}
    for page, native in sorted(natives.items()):
        if _is_ad_page(native):
            continue
        bundle = build_bundle(native, blocks.get(page) or [], items.get(page) or [])
        bundles[page] = bundle
        (out / f"p{page:02d}.json").write_text(
            json.dumps(bundle, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
        )
    return bundles


def load_json_dir(path: str | Path) -> dict[int, Any]:
    out: dict[int, Any] = {}
    for file in sorted(Path(path).glob("p*.json")):
        out[int(file.stem[1:])] = json.loads(file.read_text(encoding="utf-8"))
    return out


def _section(raw: Any) -> str:
    key = str(raw or "").replace("'", "’").strip()
    return SECTION_ALIASES.get(key.lower(), key)


def validate(
    bundles: dict[int, dict[str, Any]], answers: dict[int, dict[str, Any]]
) -> list[dict[str, Any]]:
    """Return hard errors and drop reasons; an empty list means the answer is clean."""
    findings: list[dict[str, Any]] = []
    for page, bundle in sorted(bundles.items()):
        answer = answers.get(page)
        if answer is None:
            findings.append({"page": page, "level": "error", "detail": "no answer"})
            continue
        if int(answer.get("page", page)) != page:
            findings.append({"page": page, "level": "error", "detail": "page mismatch"})
        block_by_index = {block["index"]: block for block in bundle["blocks"]}
        block_lines = {
            line["id"] for block in bundle["blocks"] for line in block["lines"]
        }
        line_type = {
            line["id"]: block["type"]
            for block in bundle["blocks"]
            for line in block["lines"]
        }
        has_backward = bool((bundle.get("markers") or {}).get("backward"))
        seen: dict[int, str] = {}
        for item in answer.get("items") or []:
            start = str(item.get("start_line") or "")
            if not start:
                findings.append(
                    {"page": page, "level": "error", "detail": "item without start_line"}
                )
                continue
            if start not in block_lines:
                findings.append(
                    {
                        "page": page,
                        "level": "warn",
                        "detail": f"{start}: start line outside the assigned blocks",
                    }
                )
            raw_blocks = [int(x) for x in item.get("blocks") or []]
            unknown = [index for index in raw_blocks if index not in block_by_index]
            if unknown:
                findings.append(
                    {
                        "page": page,
                        "level": "warn",
                        "detail": f"{start}: unknown blocks {unknown} dropped",
                    }
                )
            blocks = sorted({index for index in raw_blocks if index in block_by_index})
            if len(raw_blocks) != len(set(raw_blocks)):
                findings.append(
                    {
                        "page": page,
                        "level": "warn",
                        "detail": f"{start}: repeated block deduplicated",
                    }
                )
            if not blocks:
                findings.append(
                    {"page": page, "level": "drop", "detail": f"{start}: empty blocks"}
                )
                continue
            for index in blocks:
                if index in seen:
                    findings.append(
                        {
                            "page": page,
                            "level": "error",
                            "detail": f"block {index}: {seen[index]} and {start}",
                        }
                    )
                seen[index] = start
            if {block_by_index[index]["type"] for index in blocks} <= DROP_TYPES:
                findings.append(
                    {"page": page, "level": "drop", "detail": f"{start}: table-only"}
                )
            if has_backward and line_type.get(start) == "text":
                findings.append(
                    {
                        "page": page,
                        "level": "drop",
                        "detail": f"{start}: continuation body",
                    }
                )
            section = _section(item.get("section"))
            if section and section not in SECTION_MAP:
                findings.append(
                    {
                        "page": page,
                        "level": "error",
                        "detail": f"{start}: unmapped section {section!r}",
                    }
                )
    return findings


def merge(
    original: dict[str, Any],
    bundles: dict[int, dict[str, Any]],
    answers: dict[int, dict[str, Any]],
) -> dict[str, Any]:
    """Validated answers -> a reader cache. Drops are applied, not raised."""
    merged = {"issue": original.get("issue", ""), "pages": dict(original.get("pages") or {})}
    for page, bundle in sorted(bundles.items()):
        if page not in answers:
            continue
        block_by_index = {block["index"]: block for block in bundle["blocks"]}
        line_type = {
            line["id"]: block["type"]
            for block in bundle["blocks"]
            for line in block["lines"]
        }
        has_backward = bool((bundle.get("markers") or {}).get("backward"))
        original_by_start = {
            str(item.get("start_line")): item
            for item in original.get("pages", {}).get(str(page), [])
        }
        items: list[dict[str, Any]] = []
        for item in answers[page].get("items") or []:
            start = str(item.get("start_line") or "")
            if not start:
                continue
            blocks = sorted(
                {int(x) for x in item.get("blocks") or [] if int(x) in block_by_index}
            )
            if not blocks:
                continue
            if {block_by_index[index]["type"] for index in blocks} <= DROP_TYPES:
                continue
            if has_backward and line_type.get(start) == "text":
                continue
            entry: dict[str, Any] = {
                "start_line": start,
                "kind": str(item.get("kind") or "article"),
                "first_line": str(
                    item.get("first_line")
                    or original_by_start.get(start, {}).get("first_line")
                    or ""
                ),
                "blocks": blocks,
            }
            section = _section(
                item.get("section") or original_by_start.get(start, {}).get("section")
            )
            if section:
                entry["section"] = section
            continues = item.get("continues") or original_by_start.get(start, {}).get(
                "continues"
            )
            if continues:
                entry["continues"] = str(continues)
            items.append(entry)
        merged["pages"][str(page)] = items
    return merged


def coverage(
    bundles: dict[int, dict[str, Any]],
    answers: dict[int, dict[str, Any]],
    natives: dict[int, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    rows = []
    for page, bundle in sorted(bundles.items()):
        if natives is not None and page in natives:
            text = {
                line["id"]
                for line in natives[page].get("lines") or []
                if (line.get("text") or "").strip()
            }
        else:
            text = {
                line["id"] for block in bundle["blocks"] for line in block["lines"]
            }
        block_lines = {
            line["id"] for block in bundle["blocks"] for line in block["lines"]
        }
        assigned: set[str] = set()
        if page in answers:
            by_index = {block["index"]: block for block in bundle["blocks"]}
            for item in answers[page].get("items") or []:
                for index in item.get("blocks") or []:
                    block = by_index.get(int(index))
                    if block:
                        assigned.update(line["id"] for line in block["lines"])
        total = len(text)
        rows.append(
            {
                "page": page,
                "text_lines": total,
                "block_coverage": round(len(block_lines & text) / total, 3)
                if total
                else 1.0,
                "assigned_coverage": round(len(assigned & text) / total, 3)
                if total
                else 1.0,
            }
        )
    return rows


def write_cache(
    merged: dict[str, Any], dest: str | Path, *, force: bool = False
) -> Path:
    target = Path(dest)
    if target.exists():
        if not force:
            raise SystemExit(f"{target} exists; pass --force to replace it")
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = target.with_name(f"{target.stem}.pre-merge-{stamp}{target.suffix}")
        shutil.copy2(target, backup)
        print(f"backup: {backup}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(merged, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    return target


def report(
    pilot_root: str | Path, cache_path: str | Path, golden: str | Path | None = None
) -> dict[str, Any]:
    root = Path(pilot_root)
    natives = load_natives_from_pilot(root)
    records = derive_article_map(natives, cache_path, pilot_root=root)
    summary: dict[str, Any] = {
        "records": len(records),
        "sources": dict(Counter(r["regions_source"] for r in records)),
        "zero_region": [r["id"] for r in records if not r["regions"]],
        "with_paragraphs": sum(1 for r in records if r.get("paragraphs")),
        "paragraphs": sum(len(r.get("paragraphs") or []) for r in records),
        "flagged": sum(1 for r in records if r["needs_review"]),
        "multi_page": sum(1 for r in records if len(r["all_pages"]) > 1),
    }
    if golden is not None:
        expected = json.loads(Path(golden).read_text(encoding="utf-8"))
        summary["golden_items"] = len(expected.get("articles") or expected)
    return summary


def _cmd_bundle(args: argparse.Namespace) -> None:
    cache = args.cache or default_reader_cache_path(args.pilot_root)
    bundles = build_bundles(
        args.pilot_root,
        cache_path=Path(cache) if Path(cache).exists() else None,
        dest=args.out,
    )
    print(f"bundles: {len(bundles)} pages -> {args.out}")


def _cmd_validate(args: argparse.Namespace) -> None:
    findings = validate(load_json_dir(args.bundles), load_json_dir(args.answers))
    errors = [f for f in findings if f["level"] == "error"]
    warnings = [f for f in findings if f["level"] == "warn"]
    drops = [f for f in findings if f["level"] == "drop"]
    print(f"errors: {len(errors)}; warnings: {len(warnings)}; drops: {len(drops)}")
    for finding in findings:
        print(f"  {finding['level']} p{finding['page']:02d} {finding['detail']}")
    if errors:
        raise SystemExit(1)


def _cmd_merge(args: argparse.Namespace) -> None:
    cache_path = args.cache or default_reader_cache_path(args.pilot_root)
    original = (
        json.loads(Path(cache_path).read_text(encoding="utf-8"))
        if Path(cache_path).exists()
        else {"issue": "", "pages": {}}
    )
    bundles = load_json_dir(args.bundles)
    answers = load_json_dir(args.answers)
    findings = validate(bundles, answers)
    errors = [f for f in findings if f["level"] == "error"]
    if errors:
        for finding in errors:
            print(f"  error p{finding['page']:02d} {finding['detail']}")
        raise SystemExit(f"{len(errors)} validation errors; cache not written")
    merged = merge(original, bundles, answers)
    target = write_cache(merged, args.out, force=args.force)
    rows = coverage(bundles, answers, load_natives_from_pilot(args.pilot_root))
    print(f"cache: {target} ({sum(len(v) for v in merged['pages'].values())} items)")
    print(
        "coverage: block "
        f"{min(r['block_coverage'] for r in rows):.3f}-{max(r['block_coverage'] for r in rows):.3f}, "
        f"assigned {min(r['assigned_coverage'] for r in rows):.3f}-"
        f"{max(r['assigned_coverage'] for r in rows):.3f}"
    )


def _cmd_report(args: argparse.Namespace) -> None:
    summary = report(args.pilot_root, args.cache, args.golden)
    print(json.dumps(summary, ensure_ascii=False, indent=1))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    bundle = sub.add_parser("bundle", help="build per-page pass bundles")
    bundle.add_argument("--pilot-root", required=True)
    bundle.add_argument("--cache", default=None)
    bundle.add_argument("--out", required=True)
    bundle.set_defaults(func=_cmd_bundle)

    validate_cmd = sub.add_parser("validate", help="check answers against bundles")
    validate_cmd.add_argument("--bundles", required=True)
    validate_cmd.add_argument("--answers", required=True)
    validate_cmd.set_defaults(func=_cmd_validate)

    merge_cmd = sub.add_parser("merge", help="merge validated answers into a cache")
    merge_cmd.add_argument("--pilot-root", required=True)
    merge_cmd.add_argument("--bundles", required=True)
    merge_cmd.add_argument("--answers", required=True)
    merge_cmd.add_argument("--cache", default=None)
    merge_cmd.add_argument("--out", required=True)
    merge_cmd.add_argument("--force", action="store_true")
    merge_cmd.set_defaults(func=_cmd_merge)

    report_cmd = sub.add_parser("report", help="derive and summarize the map")
    report_cmd.add_argument("--pilot-root", required=True)
    report_cmd.add_argument("--cache", default=None)
    report_cmd.add_argument("--golden", default=None)
    report_cmd.set_defaults(func=_cmd_report)

    args = parser.parse_args()
    if getattr(args, "cache", None) is None and hasattr(args, "pilot_root"):
        args.cache = str(default_reader_cache_path(args.pilot_root))
    args.func(args)


if __name__ == "__main__":
    main()
