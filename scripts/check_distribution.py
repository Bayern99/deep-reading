#!/usr/bin/env python3
"""Check source boundaries, JSON syntax, machine-path leaks, and active local document links."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote

from package_release import (
    HOOKS,
    NAMED_SOURCE_FILES,
    ROOT,
    ROOT_FILES,
    SOURCE_DIRS,
    SOURCE_SUFFIXES,
    release_files,
)

SKIP_LINK_CHECK_PREFIXES = (
    "docs/adr/0001-",
    "docs/adr/0002-",
    "docs/adr/0003-",
    "docs/adr/0004-",
    "docs/adr/0005-",
    "internal/openuilang/testdata/",
    "internal/testdata/",
)


def allowed(relative: str) -> bool:
    path = Path(relative)
    return relative in ROOT_FILES or (
        path.parts[0] in SOURCE_DIRS and (
            path.suffix in SOURCE_SUFFIXES or relative in HOOKS or relative in NAMED_SOURCE_FILES
        ) and "__pycache__" not in path.parts
    )


def check(staged: bool = False) -> list[str]:
    errors = []
    if staged:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z"],
            cwd=ROOT, capture_output=True, check=True,
        )
        paths = result.stdout.decode().split("\0")
        return [f"Unclassified staged file: {path}" for path in paths if path and not allowed(path)]
    files = release_files()
    if (ROOT / ".git").exists():
        tracked = subprocess.run(
            ["git", "ls-files", "-z", "--cached"],
            cwd=ROOT, capture_output=True, check=True,
        )
        for name in tracked.stdout.decode().split("\0"):
            if name and (ROOT / name).exists() and not allowed(name):
                errors.append(f"Unclassified tracked file: {name}")
    for path in files:
        text = path.read_text(encoding="utf-8")
        relative = path.relative_to(ROOT).as_posix()
        for marker in ("/Users/", "/home/hatch/", "/opt/homebrew/", "PILOT-", "CASE-B1B2-"):
            if marker in text and path.name != Path(__file__).name:
                errors.append(f"Machine/sample binding in {relative}: {marker}")
        if path.suffix == ".json":
            try:
                json.loads(text)
            except json.JSONDecodeError as exc:
                errors.append(f"JSON syntax: {relative}:{exc.lineno}: {exc.msg}")
        elif path.suffix == ".md" and not relative.startswith(SKIP_LINK_CHECK_PREFIXES):
            for target in re.findall(r"\[[^\]]*\]\(([^\s)]+)(?:\s+\"[^\"]*\")?\)", text):
                target = target.strip("<>").split("#", 1)[0]
                if not target or "://" in target or target.startswith(("mailto:", "{{")):
                    continue
                if not (path.parent / unquote(target)).exists():
                    errors.append(f"Broken document link: {relative} -> {target}")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staged", action="store_true")
    args = parser.parse_args()
    try:
        errors = check(args.staged)
    except (ValueError, OSError) as exc:
        errors = [str(exc)]
    if errors:
        print("\n".join(errors), file=sys.stderr)
        raise SystemExit(1)
    print("Distribution source check passed (static only; no publication or runtime certification).")


if __name__ == "__main__":
    main()
