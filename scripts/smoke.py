#!/usr/bin/env python3
"""Exercise both production entry points on an isolated copy; never call a model."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--issue", default="2026-10-12")
    parser.add_argument("--keep", action="store_true", help="Keep the isolated copy for browser inspection")
    args = parser.parse_args()
    if Path(args.issue).name != args.issue:
        parser.error("--issue must be an issue directory name")
    original = ROOT / args.issue
    source = original / "final.json"
    digest_before = hashlib.sha256(source.read_bytes()).hexdigest()
    sandbox = Path(tempfile.mkdtemp(prefix="wsj-governance-smoke-"))
    try:
        shutil.copytree(ROOT / "render", sandbox / "render", ignore=shutil.ignore_patterns("__pycache__"))
        issue = sandbox / args.issue
        issue.mkdir()
        shutil.copy2(source, issue / "final.json")
        if (original / "front.json").is_file():
            shutil.copy2(original / "front.json", issue / "front.json")
        for name in ("assets", "cases/assets", "ovis-test", "editorial-plans", "editorial-artifacts"):
            if (original / name).is_dir():
                # The historical queue stays on disk; a smoke run must not resume paid work.
                shutil.copytree(original / name, issue / name, ignore=shutil.ignore_patterns("__pycache__", "shots", "_queue.json", "_queue.json.tmp.*"))
        subprocess.run([sys.executable, str(sandbox / "render/build.py"), "--issue", args.issue], cwd=sandbox, check=True)
        subprocess.run([sys.executable, str(sandbox / "render/editorial_studio.py"), "--issue", args.issue], cwd=sandbox, check=True)

        sys.path.insert(0, str(sandbox / "render"))
        from editorial_studio import create_studio_http_server
        from artifact_store import ArtifactStore

        server = create_studio_http_server(str(issue), port=0)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        base = f"http://127.0.0.1:{server.server_port}"

        def fetch(path: str):
            with urllib.request.urlopen(base + path, timeout=30) as response:
                return response.read()

        try:
            entries = json.loads(source.read_text(encoding="utf-8"))
            status = json.loads(fetch("/api/status"))
            assert {item["id"] for item in status["source_library"]} == {item["id"] for item in entries}
            assert status["queue"]["counts"]["pending"] == 0
            assert status["queue"]["counts"]["running"] == 0
            registered = ArtifactStore(str(issue)).list_articles()
            assert set(status["artifacts"]) == set(registered)
            for article_id, artifact in status["artifacts"].items():
                active = artifact["versions"][artifact["active_version"]]
                assert active["validation"]["compiler_audit"]["passed"], article_id
            article_id = entries[0]["id"]
            canonical = json.loads(fetch("/api/canonical?article_id=" + article_id))
            assert canonical["article_id"] == article_id
            assert canonical["issue_date"] == args.issue
            assert 'id="wsj-issue-payload"' in fetch("/reader").decode("utf-8")
            assert fetch("/studio").startswith(b"<!DOCTYPE html>")
            assert json.loads(fetch("/api/queue"))["total_tasks"] == 0
            print(f"Smoke passed: both builds, Studio/Reader HTTP, {len(entries)} source items, {len(registered)} stored articles, no model calls.")
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=5)
        assert hashlib.sha256(source.read_bytes()).hexdigest() == digest_before
    finally:
        if args.keep:
            print(f"Isolated copy: {sandbox}")
        else:
            shutil.rmtree(sandbox)


if __name__ == "__main__":
    main()
