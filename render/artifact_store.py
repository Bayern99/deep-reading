#!/usr/bin/env python3
"""WSJ 深读 · Phase 5 Editorial Artifact Persistence & Version Manager (`artifact_store.py`).

Stores and manages versioned, self-contained Bilingual Editorial Artifacts under:
`<issue_dir>/editorial-artifacts/`
  ├── _index.json                 # Registry of all generated articles, versions, active version, and status
  └── <article_id>/
        ├── canonical.json        # Frozen CanonicalSource snapshot (with content_digest)
        ├── v1/
        │     ├── artifact.json   # Complete metadata, model info, validation report, shadow bundle
        │     ├── raw.html        # Raw source-referenced HTML emitted by the model
        │     └── compiled.html   # Standalone deterministically-injected & sanitized HTML
        └── latest.json           # Pointer / snapshot of the active verified version

Key guarantees:
- Re-opening an article NEVER invokes an LLM or re-runs generation.
- Failed generations are recorded in `<article_id>/failed-<timestamp>/` for inspection without
  overwriting or corrupting the previously active verified artifact!
- Multiple versions (across different models, prompts, or revisions) coexist cleanly and can be
  compared or rolled back.
"""
from __future__ import annotations

import datetime
import json
import os
import re
from typing import Any


def _utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class ArtifactStore:
    def __init__(self, issue_dir: str):
        self.issue_dir = os.path.abspath(issue_dir)
        self.root_dir = os.path.join(self.issue_dir, "editorial-artifacts")
        os.makedirs(self.root_dir, exist_ok=True)
        self.index_path = os.path.join(self.root_dir, "_index.json")

    def _load_index(self) -> dict[str, Any]:
        if os.path.isfile(self.index_path):
            with open(self.index_path, encoding="utf-8") as f:
                return json.load(f)
        return {
            "schema_version": "editorial-artifact-index-v1",
            "issue_date": os.path.basename(self.issue_dir),
            "updated_at": _utc_now(),
            "articles": {},
        }

    def _save_index(self, idx: dict[str, Any]) -> None:
        idx["updated_at"] = _utc_now()
        with open(self.index_path, "w", encoding="utf-8") as f:
            json.dump(idx, f, ensure_ascii=False, indent=2)

    def article_dir(self, article_id: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", article_id):
            raise ValueError(f"Invalid article identifier: {article_id!r}")
        d = os.path.join(self.root_dir, article_id)
        os.makedirs(d, exist_ok=True)
        return d

    def save_canonical(self, canonical: dict[str, Any]) -> str:
        aid = canonical["article_id"]
        adir = self.article_dir(aid)
        cpath = os.path.join(adir, "canonical.json")
        with open(cpath, "w", encoding="utf-8") as f:
            json.dump(canonical, f, ensure_ascii=False, indent=2)
        return cpath

    def save_verified_artifact(
        self,
        *,
        canonical: dict[str, Any],
        raw_html: str,
        compiled_html: str,
        shadow_bundle: dict[str, str],
        audit_report: dict[str, Any],
        model_metadata: dict[str, Any],
        usage_metadata: dict[str, Any] | None = None,
        rendered_integrity: dict[str, Any] | None = None,
        notes: str = "",
    ) -> dict[str, Any]:
        """Persist a verified Editorial Artifact as a new version and promote it to active."""
        if not audit_report.get("passed"):
            raise ValueError("Cannot save an unverified artifact as active; use save_failed_attempt instead.")

        aid = canonical["article_id"]
        self.save_canonical(canonical)
        idx = self._load_index()
        art_entry = idx["articles"].get(aid) or {
            "article_id": aid,
            "title_cn": canonical["metadata"]["title_cn"],
            "title_en": canonical["metadata"]["title_en"],
            "section": canonical["metadata"]["section"],
            "page": canonical["metadata"]["page"],
            "active_version": None,
            "versions": [],
            "failed_attempts": [],
        }

        next_v_num = len(art_entry["versions"]) + 1
        version_id = f"v{next_v_num}"
        v_dir = os.path.join(self.article_dir(aid), version_id)
        os.makedirs(v_dir, exist_ok=True)

        created_at = _utc_now()
        raw_rel = f"{aid}/{version_id}/raw.html"
        comp_rel = f"{aid}/{version_id}/compiled.html"

        with open(os.path.join(v_dir, "raw.html"), "w", encoding="utf-8") as f:
            f.write(raw_html)
        with open(os.path.join(v_dir, "compiled.html"), "w", encoding="utf-8") as f:
            f.write(compiled_html)

        artifact_record = {
            "schema_version": "editorial-artifact-v1",
            "article_id": aid,
            "artifact_version": version_id,
            "created_at": created_at,
            "status": "verified",
            "notes": notes,
            "source_reference": {
                "issue_date": canonical.get("issue_date", "2026-10-12"),
                "content_digest": canonical["content_digest"],
                "paragraph_count": len(canonical["blocks"]),
                "locales": ["zh-CN", "en"],
            },
            "model_metadata": model_metadata,
            "usage_metadata": usage_metadata or {},
            "files": {
                "raw_html": raw_rel,
                "compiled_html": comp_rel,
            },
            "shadow_bundle": shadow_bundle,
            "validation": {
                "compiler_audit": audit_report,
                "rendered_integrity": rendered_integrity or {"status": "pending_browser_check"},
            },
        }

        with open(os.path.join(v_dir, "artifact.json"), "w", encoding="utf-8") as f:
            json.dump(artifact_record, f, ensure_ascii=False, indent=2)

        with open(os.path.join(self.article_dir(aid), "latest.json"), "w", encoding="utf-8") as f:
            json.dump(artifact_record, f, ensure_ascii=False, indent=2)

        version_summary = {
            "version": version_id,
            "created_at": created_at,
            "status": "verified",
            "content_digest": canonical["content_digest"],
            "provider": model_metadata.get("provider", "unknown"),
            "model_id": model_metadata.get("model_id", "unknown"),
            "exact_match_cn": audit_report["source_integrity"]["exact_match_cn"],
            "exact_match_en": audit_report["source_integrity"]["exact_match_en"],
            "compiled_html": comp_rel,
            "notes": notes,
        }
        art_entry["versions"].append(version_summary)
        art_entry["active_version"] = version_id
        art_entry["content_digest"] = canonical["content_digest"]
        art_entry["updated_at"] = created_at
        idx["articles"][aid] = art_entry
        self._save_index(idx)
        return artifact_record

    def save_failed_attempt(
        self,
        *,
        canonical: dict[str, Any],
        raw_html: str,
        audit_report: dict[str, Any],
        model_metadata: dict[str, Any],
        error_message: str,
    ) -> dict[str, Any]:
        """Record a failed generation/compilation without clobbering any previously verified artifact."""
        aid = canonical["article_id"]
        self.save_canonical(canonical)
        idx = self._load_index()
        art_entry = idx["articles"].get(aid) or {
            "article_id": aid,
            "title_cn": canonical["metadata"]["title_cn"],
            "title_en": canonical["metadata"]["title_en"],
            "section": canonical["metadata"]["section"],
            "page": canonical["metadata"]["page"],
            "active_version": None,
            "versions": [],
            "failed_attempts": [],
        }

        fail_num = len(art_entry.get("failed_attempts", [])) + 1
        fail_id = f"failed-{fail_num}"
        f_dir = os.path.join(self.article_dir(aid), fail_id)
        os.makedirs(f_dir, exist_ok=True)
        created_at = _utc_now()

        with open(os.path.join(f_dir, "raw.html"), "w", encoding="utf-8") as f:
            f.write(raw_html or "")

        fail_record = {
            "article_id": aid,
            "attempt_id": fail_id,
            "created_at": created_at,
            "status": "failed",
            "error_message": error_message,
            "content_digest": canonical["content_digest"],
            "model_metadata": model_metadata,
            "audit_report": audit_report,
        }
        with open(os.path.join(f_dir, "failure.json"), "w", encoding="utf-8") as f:
            json.dump(fail_record, f, ensure_ascii=False, indent=2)

        art_entry.setdefault("failed_attempts", []).append({
            "attempt_id": fail_id,
            "created_at": created_at,
            "error_message": error_message,
            "model_id": model_metadata.get("model_id", "unknown"),
        })
        idx["articles"][aid] = art_entry
        self._save_index(idx)
        return fail_record

    def update_rendered_integrity(self, article_id: str, version_id: str, rendered_metrics: dict[str, Any]) -> None:
        v_path = os.path.join(self.article_dir(article_id), version_id, "artifact.json")
        if not os.path.isfile(v_path):
            return
        with open(v_path, encoding="utf-8") as f:
            rec = json.load(f)
        rec["validation"]["rendered_integrity"] = rendered_metrics
        with open(v_path, "w", encoding="utf-8") as f:
            json.dump(rec, f, ensure_ascii=False, indent=2)

        latest_path = os.path.join(self.article_dir(article_id), "latest.json")
        if os.path.isfile(latest_path):
            with open(latest_path, encoding="utf-8") as f:
                lat = json.load(f)
            if lat.get("artifact_version") == version_id:
                lat["validation"]["rendered_integrity"] = rendered_metrics
                with open(latest_path, "w", encoding="utf-8") as f:
                    json.dump(lat, f, ensure_ascii=False, indent=2)

    def set_active_version(self, article_id: str, version_id: str) -> dict[str, Any]:
        """Switch the active version of an article and update latest.json."""
        if not re.fullmatch(r"v[1-9][0-9]*", version_id):
            raise KeyError(f"Invalid artifact version: {version_id!r}")
        idx = self._load_index()
        art_entry = idx["articles"].get(article_id)
        if not art_entry:
            raise KeyError(f"Article '{article_id}' has no stored artifacts")
        if version_id not in {v["version"] for v in art_entry["versions"]}:
            raise KeyError(f"Version '{version_id}' is not registered for article '{article_id}'")
        v_path = os.path.join(self.article_dir(article_id), version_id, "artifact.json")
        if not os.path.isfile(v_path):
            raise KeyError(f"Version '{version_id}' not found for article '{article_id}'")
        with open(v_path, encoding="utf-8") as f:
            rec = json.load(f)
        with open(os.path.join(self.article_dir(article_id), "latest.json"), "w", encoding="utf-8") as f:
            json.dump(rec, f, ensure_ascii=False, indent=2)
        art_entry["active_version"] = version_id
        art_entry["updated_at"] = _utc_now()
        idx["articles"][article_id] = art_entry
        self._save_index(idx)
        return rec
    def get_active_artifact(self, article_id: str) -> dict[str, Any] | None:
        latest_path = os.path.join(self.article_dir(article_id), "latest.json")
        if not os.path.isfile(latest_path):
            return None
        with open(latest_path, encoding="utf-8") as f:
            return json.load(f)

    def list_articles(self) -> dict[str, Any]:
        return self._load_index()["articles"]
