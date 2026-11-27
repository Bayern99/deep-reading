#!/usr/bin/env python3
"""Build an allowlisted source release with a SHA256 content manifest."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROOT_FILES = (
    "README.md", "README.zh-CN.md",
    "AGENTS.md", "SKILL.md", "UPSTREAM.md",
    "LICENSE", "VERSION", "Makefile",
    "go.mod", "go.sum",
    ".gitignore", ".gitattributes",
)
SOURCE_DIRS = (".github", "cmd", "internal", "docs", "scripts")
SOURCE_SUFFIXES = {
    ".go", ".py", ".md", ".json", ".yaml", ".yml",
    ".txt", ".tsv", ".oui",
}
HOOKS = {"scripts/hooks/commit-msg", "scripts/hooks/pre-push"}
NAMED_SOURCE_FILES = {
    "internal/openuilang/testdata/openui-1.0/LICENSE",
}
EXCLUDED_PARTS = {"__pycache__", ".git", ".venv", ".scratch", ".pytest_cache", ".DS_Store", "research"}


def release_files(root: Path = ROOT) -> list[Path]:
    """Only tool sources and maintained docs may enter a release."""
    result = []
    for name in ROOT_FILES:
        path = root / name
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"Required source file missing or linked: {name}")
        result.append(path)
    for directory in SOURCE_DIRS:
        base = root / directory
        if not base.is_dir() or base.is_symlink():
            raise ValueError(f"Required source directory missing or linked: {directory}")
        for path in sorted(base.rglob("*")):
            rel = path.relative_to(root)
            if any(part in EXCLUDED_PARTS for part in rel.parts):
                continue
            if path.is_symlink():
                raise ValueError(f"Linked release input is not allowed: {rel}")
            if not path.is_file():
                continue
            if path.suffix not in SOURCE_SUFFIXES and rel.as_posix() not in HOOKS and rel.as_posix() not in NAMED_SOURCE_FILES:
                raise ValueError(f"Unclassified file in release source: {rel}")
            result.append(path)
    return sorted(result, key=lambda path: path.relative_to(root).as_posix())


def package(output: Path) -> dict:
    from check_distribution import check

    errors = check()
    if errors:
        raise ValueError("Distribution source check failed:\n" + "\n".join(errors))
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.-]+)?", version):
        raise ValueError("VERSION must contain a semantic version")
    files = release_files()
    output = output.expanduser().resolve()
    if output.exists():
        raise FileExistsError(f"Refusing to replace existing release: {output}")
    if output.with_suffix(output.suffix + ".sha256").exists():
        raise FileExistsError("Refusing to replace an existing release checksum")
    if any(output == path.resolve() for path in files):
        raise ValueError("Release output would replace an input")
    prefix = f"deepread-{version}"
    payloads = {path.relative_to(ROOT).as_posix(): path.read_bytes() for path in files}
    manifest = {
        "name": "deepread", "version": version,
        "scope": "Headless Go deep-reading engine, SKILL.md, and bilingual docs; no private book/issue data",
        "files": {name: hashlib.sha256(body).hexdigest() for name, body in payloads.items()},
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, body in payloads.items():
                entry = zipfile.ZipInfo(f"{prefix}/{name}", date_time=(2026, 1, 1, 0, 0, 0))
                entry.compress_type = zipfile.ZIP_DEFLATED
                mode = 0o755 if name in HOOKS else 0o644
                entry.external_attr = mode << 16
                archive.writestr(entry, body)
            archive.writestr(f"{prefix}/DISTRIBUTION-MANIFEST.json",
                             json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
        with zipfile.ZipFile(output) as archive:
            if len(archive.namelist()) != len(payloads) + 1:
                raise ValueError("Release member count mismatch")
            for name, digest in manifest["files"].items():
                if hashlib.sha256(archive.read(f"{prefix}/{name}")).hexdigest() != digest:
                    raise ValueError(f"Release member checksum mismatch: {name}")
    except Exception:
        output.unlink(missing_ok=True)
        raise
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    checksum = output.with_suffix(output.suffix + ".sha256")
    checksum.write_text(f"{digest}  {output.name}\n", encoding="utf-8")
    return {"output": str(output), "sha256": digest, "files": len(payloads),
            "bytes": output.stat().st_size}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(package(args.output), ensure_ascii=False))


if __name__ == "__main__":
    main()
