#!/usr/bin/env python3
"""WSJ 深读 · Phase 7 Daily Editorial Studio & Batch Production Server (`editorial_studio.py`).

Supports the complete Daily Issue Workflow:
  Existing WSJ Source Pipeline -> Integrity Gate (PASS/WARN/BLOCK) ->
  Editorial Curation & Recommendations -> Batch Article Selection ->
  Persistent Background Generation Queue (Pending/Running/Completed/Failed/Cancelled) ->
  Source-referenced Compilation & Audit -> Versioned Editorial Artifacts ->
  Daily Reading Library & Bilingual Open Shadow DOM Reader.

Multi-issue ready: discovers all `<YYYY-MM-DD>/final.json` issues in the repository and allows
switching issues dynamically without hardcoding `2026-10-12`.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

BASE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(BASE)
sys.path.insert(0, BASE)

from artifact_store import ArtifactStore
from canonical_builder import load_canonical_for_issue
from generation_queue import (
    PersistentGenerationQueue,
    discover_issues,
    evaluate_article_curation,
)
from integrity_gate import check_article
from model_provider import (
    DEFAULT_EDITORIAL_MODEL_ID,
    ModelProvider,
    list_configured_models,
)
from source_model import content_digest


_QUEUE_INSTANCES_LOCK = threading.Lock()
_QUEUE_INSTANCES: dict[str, PersistentGenerationQueue] = {}


def get_issue_queue(
    issue_dir: str,
    *,
    provider_override: ModelProvider | None = None,
    auto_start_worker: bool = True,
) -> PersistentGenerationQueue:
    abs_dir = os.path.abspath(issue_dir)
    with _QUEUE_INSTANCES_LOCK:
        q = _QUEUE_INSTANCES.get(abs_dir)
        if q is None:
            q = PersistentGenerationQueue(
                abs_dir,
                provider_override=provider_override,
                auto_start_worker=auto_start_worker,
            )
            _QUEUE_INSTANCES[abs_dir] = q
        elif provider_override is not None:
            q.provider_override = provider_override
        return q


def compute_workflow_status(
    *,
    gate_status: str,
    excluded_by_curation: bool,
    item_type: str,
    paras_cn: int,
    has_artifact: bool,
    failed_attempts_count: int,
    active_job: dict[str, Any] | None,
) -> tuple[str, str]:
    """Classify each source item into one of the 5 explicit Daily Editorial Workflow states:
    1. `generating`   — Pending or Running in the background queue
    2. `generated`    — Has a verified, saved Editorial Artifact
    3. `failed_retry` — Last generation attempt failed (or has failed attempts and no verified artifact yet)
    4. `eligible`     — Passed Content Integrity Gate (`pass` or reviewed `warn`) and ready for generation
    5. `not_ready`    — Blocked by gate, excluded by curation, non-narrative table/digest, or empty translation
    """
    if active_job and active_job.get("status") in ("pending", "running", "generating"):
        st_lbl = "排队等待中 (Pending)" if active_job.get("status") == "pending" else f"正在生成 ({active_job.get('stage', 'running')})"
        return "generating", st_lbl

    if active_job and active_job.get("status") == "failed" and not has_artifact:
        return "failed_retry", "生成失败 · 需重试 (Failed)"

    if failed_attempts_count > 0 and not has_artifact:
        return "failed_retry", "生成失败 · 需重试 (Failed)"

    if has_artifact:
        if active_job and active_job.get("status") == "failed":
            return "generated", "已生成 (上次重试失败，已保留历史有效版)"
        return "generated", "已生成制品 (Verified)"

    if gate_status == "block" or excluded_by_curation or paras_cn == 0:
        return "not_ready", "尚未就绪 / 已拦截 (Not Ready)"

    if item_type in ("index_digest", "photo_caption", "correction", "data_table"):
        return "not_ready", f"非叙事条目 ({item_type})"

    if gate_status == "warn":
        return "eligible", "可生成 · 需确认门禁警告 (WARN)"

    return "eligible", "可生成 (Ready)"


def collect_issue_payload(issue_dir: str, *, provider_override: ModelProvider | None = None) -> dict[str, Any]:
    """Collect Source Library status, Curation Recommendations, Persistent Queue state, and Artifacts."""
    issue_dir = os.path.abspath(issue_dir)
    issue_date = os.path.basename(issue_dir)
    final_path = os.path.join(issue_dir, "final.json")
    with open(final_path, encoding="utf-8") as f:
        final_items = json.load(f)

    front_path = os.path.join(issue_dir, "front.json")
    front = {}
    if os.path.isfile(front_path):
        with open(front_path, encoding="utf-8") as f:
            front = json.load(f)

    curation_path = os.path.join(BASE, "curation.json")
    curation = {}
    if os.path.isfile(curation_path):
        with open(curation_path, encoding="utf-8") as f:
            curation = json.load(f)
    excluded_ids = set(curation.get("exclude") or {})

    plans_dir = os.path.join(issue_dir, "editorial-plans")
    planned_ids = set()
    if os.path.isdir(plans_dir):
        for fn in os.listdir(plans_dir):
            if fn.endswith(".json") and not fn.startswith("_"):
                planned_ids.add(fn[:-5])

    store = ArtifactStore(issue_dir)
    index_articles = store.list_articles()

    artifacts_by_id: dict[str, Any] = {}
    for aid, meta in index_articles.items():
        versions_data: dict[str, Any] = {}
        for v_info in meta.get("versions", []):
            vid = v_info["version"]
            v_json_path = os.path.join(store.article_dir(aid), vid, "artifact.json")
            if os.path.isfile(v_json_path):
                with open(v_json_path, encoding="utf-8") as vf:
                    versions_data[vid] = json.load(vf)
        canonical_path = os.path.join(store.article_dir(aid), "canonical.json")
        canonical_obj = None
        if os.path.isfile(canonical_path):
            with open(canonical_path, encoding="utf-8") as cf:
                canonical_obj = json.load(cf)
        artifacts_by_id[aid] = {
            "summary": meta,
            "active_version": meta.get("active_version"),
            "versions": versions_data,
            "canonical": canonical_obj,
        }

    q = get_issue_queue(issue_dir, provider_override=provider_override)
    queue_summary = q.get_summary()
    latest_tasks_map = q.latest_task_by_article()

    source_library: list[dict[str, Any]] = []
    state_counts = {
        "generated": 0,
        "generating": 0,
        "failed_retry": 0,
        "eligible": 0,
        "not_ready": 0,
        "recommended": 0,
    }

    for entry in final_items:
        aid = entry["id"]
        passed, issues = check_article(entry)
        gate_st = "pass" if passed and not issues else ("warn" if passed else "block")
        paras_cn = [p.strip() for p in (entry.get("body_cn") or "").split("\n\n") if p.strip()]
        paras_en = [p.strip() for p in (entry.get("body_en") or "").split("\n\n") if p.strip()]
        art_rec = artifacts_by_id.get(aid)
        has_artifact = bool(art_rec and art_rec["versions"])
        failed_attempts = len((art_rec or {}).get("summary", {}).get("failed_attempts") or [])
        job_info = latest_tasks_map.get(aid)

        curation_eval = evaluate_article_curation(
            entry,
            front=front,
            curation=curation,
            has_editorial_plan=(aid in planned_ids),
        )
        if curation_eval["recommended"]:
            state_counts["recommended"] += 1

        wf_state, wf_label = compute_workflow_status(
            gate_status=gate_st,
            excluded_by_curation=(aid in excluded_ids),
            item_type=entry.get("type") or "article",
            paras_cn=len(paras_cn),
            has_artifact=has_artifact,
            failed_attempts_count=failed_attempts,
            active_job=job_info,
        )
        state_counts[wf_state] = state_counts.get(wf_state, 0) + 1

        source_library.append({
            "id": aid,
            "page": entry.get("page") or "",
            "section": entry.get("section") or "",
            "type": entry.get("type") or "article",
            "priority": entry.get("priority") or "P3",
            "title_cn": entry.get("title_cn") or "",
            "title_en": entry.get("title") or "",
            "dek_cn": entry.get("dek_cn") or "",
            "dek_en": entry.get("dek") or "",
            "byline": entry.get("byline") or "",
            "paras_cn": len(paras_cn),
            "paras_en": len(paras_en),
            "gate_status": gate_st,
            "gate_issues": issues,
            "excluded_by_curation": aid in excluded_ids,
            "content_digest": content_digest(entry)[:16],
            "has_editorial_artifact": has_artifact,
            "active_version": art_rec["active_version"] if has_artifact and art_rec else None,
            "version_count": len(art_rec["versions"]) if has_artifact and art_rec else 0,
            "failed_attempts_count": failed_attempts,
            "workflow_state": wf_state,
            "workflow_label": wf_label,
            "curation": curation_eval,
            "active_job": job_info,
        })

    return {
        "issue_date": issue_date,
        "available_issues": discover_issues(os.path.dirname(issue_dir)),
        "front_meta": front,
        "total_source_items": len(source_library),
        "published_artifact_count": sum(1 for v in artifacts_by_id.values() if v.get("versions")),
        "state_counts": state_counts,
        "configured_models": list_configured_models(),
        "queue": queue_summary,
        "artifacts": artifacts_by_id,
        "source_library": source_library,
    }


READER_TEMPLATE_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>WSJ 深读 · Daily Production Studio & Reader</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;700&family=Lora:ital,wght@0,400;0,500;0,600;1,400;1,600&family=Noto+Sans+SC:wght@400;500;700&family=Noto+Serif+SC:wght@400;500;600;700&family=Playfair+Display:ital,wght@0,700;0,800;1,700&display=swap" rel="stylesheet">
  <style>
    :root {
      --shell-bg: #f6f3ec;
      --shell-surface: #fdfbf8;
      --shell-ink: #111111;
      --shell-muted: #5f6462;
      --shell-line: #e2ddd2;
      --shell-accent: #b85d19;
      --shell-green: #156d3b;
      --shell-blue: #1d4ed8;
      --shell-red: #b91c1c;
      --font-sans: "Inter", "Noto Sans SC", -apple-system, sans-serif;
      --font-serif: "Playfair Display", "Noto Serif SC", Georgia, serif;
      --font-mono: "JetBrains Mono", monospace;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: var(--shell-bg);
      color: var(--shell-ink);
      font-family: var(--font-sans);
      -webkit-font-smoothing: antialiased;
    }
    /* Sticky Top Studio Bar */
    .studio-bar {
      position: sticky;
      top: 0;
      z-index: 500;
      background: rgba(253, 251, 248, 0.96);
      backdrop-filter: blur(8px);
      border-bottom: 1px solid var(--shell-ink);
      padding: 10px 20px;
    }
    .studio-bar-inner {
      max-width: 1440px;
      margin: 0 auto;
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
    }
    .brand-cluster {
      display: flex;
      align-items: center;
      gap: 10px;
      flex-wrap: wrap;
    }
    .brand-sq {
      width: 14px;
      height: 14px;
      background: #fa9000;
      display: inline-block;
      flex-shrink: 0;
    }
    .brand-name {
      font-weight: 700;
      font-size: 13.5px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }
    .issue-select {
      font-family: var(--font-mono);
      font-size: 11.5px;
      font-weight: 700;
      padding: 4px 8px;
      border: 1px solid var(--shell-ink);
      background: #fff;
      border-radius: 4px;
      cursor: pointer;
    }
    .nav-tabs {
      display: flex;
      align-items: center;
      gap: 6px;
    }
    .nav-tab {
      border: 1px solid var(--shell-line);
      background: transparent;
      color: var(--shell-muted);
      padding: 6px 13px;
      font-family: var(--font-sans);
      font-size: 12px;
      font-weight: 600;
      cursor: pointer;
      border-radius: 9999px;
      transition: all 0.15s;
    }
    .nav-tab.active {
      background: var(--shell-ink);
      color: #fff;
      border-color: var(--shell-ink);
    }
    .reader-controls {
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
    }
    .ctrl-select {
      font-family: var(--font-sans);
      font-size: 12px;
      font-weight: 600;
      padding: 5px 9px;
      border: 1px solid var(--shell-line);
      background: #fff;
      color: var(--shell-ink);
      border-radius: 4px;
      cursor: pointer;
      max-width: 240px;
    }
    .lang-pill {
      display: inline-flex;
      border: 1px solid var(--shell-ink);
      border-radius: 9999px;
      overflow: hidden;
    }
    .lang-pill button {
      border: 0;
      background: transparent;
      padding: 5px 11px;
      font-size: 11.5px;
      font-weight: 700;
      cursor: pointer;
      color: var(--shell-muted);
    }
    .lang-pill button.active {
      background: var(--shell-ink);
      color: #fff;
    }
    .audit-badge {
      font-family: var(--font-mono);
      font-size: 11px;
      font-weight: 600;
      padding: 5px 10px;
      border-radius: 4px;
      background: #e7f4ec;
      color: var(--shell-green);
      border: 1px solid #b7dfc5;
      cursor: pointer;
    }
    .btn-action {
      background: var(--shell-accent);
      color: #fff;
      border: 0;
      padding: 6px 12px;
      font-size: 12px;
      font-weight: 600;
      border-radius: 4px;
      cursor: pointer;
    }
    .btn-action.dark { background: var(--shell-ink); }
    .btn-action:disabled { opacity: 0.45; cursor: not-allowed; }
    /* Live Queue Progress Banner */
    .job-banner {
      max-width: 1440px;
      margin: 0 auto;
      background: #1e293b;
      color: #f8fafc;
      padding: 9px 24px;
      font-family: var(--font-mono);
      font-size: 12px;
      display: none;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      border-bottom: 2px solid #38bdf8;
    }
    .job-banner.active { display: flex; }
    .job-banner.failed { background: #450a0a; border-bottom-color: #ef4444; }
    .job-banner.completed { background: #064e3b; border-bottom-color: #10b981; }
    /* Inspector Drawer */
    .inspector-drawer {
      max-width: 1440px;
      margin: 0 auto;
      background: #181816;
      color: #e6e3dc;
      padding: 18px 24px;
      font-size: 12.5px;
      border-bottom: 2px solid var(--shell-accent);
      display: none;
    }
    .inspector-drawer.open { display: block; }
    .insp-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      gap: 16px;
    }
    .insp-card {
      background: #232320;
      padding: 12px 16px;
      border: 1px solid #343430;
    }
    .insp-label {
      font-family: var(--font-mono);
      font-size: 10.5px;
      text-transform: uppercase;
      letter-spacing: 0.1em;
      color: #9e9a90;
      margin-bottom: 6px;
    }
    .insp-val {
      font-family: var(--font-mono);
      font-size: 13px;
      font-weight: 700;
      color: #fff;
    }
    /* Views */
    .view-panel { display: none; }
    .view-panel.active { display: block; }
    #editorial-host-container {
      width: 100%;
      min-height: 80vh;
      background: #faf8f4;
    }
    /* Library & Batch Production Workspace */
    .library-wrap {
      max-width: 1380px;
      margin: 24px auto 80px auto;
      padding: 0 20px;
    }
    .lib-section-title {
      font-family: var(--font-serif);
      font-size: 25px;
      font-weight: 700;
      margin-bottom: 6px;
    }
    .lib-subtitle {
      font-size: 13px;
      color: var(--shell-muted);
      margin-bottom: 18px;
    }
    /* Batch Curation & Queue Control Console */
    .batch-console {
      background: var(--shell-surface);
      border: 1px solid var(--shell-ink);
      padding: 16px 20px;
      margin-bottom: 24px;
      display: flex;
      flex-direction: column;
      gap: 14px;
    }
    .batch-row {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
    }
    .gen-ctrl-group {
      display: flex;
      align-items: center;
      gap: 10px;
      flex-wrap: wrap;
    }
    .gen-input {
      font-family: var(--font-sans);
      font-size: 12px;
      padding: 6px 10px;
      border: 1px solid var(--shell-line);
      border-radius: 4px;
      min-width: 240px;
    }
    /* Persistent Queue Panel */
    .queue-panel {
      background: #181816;
      color: #f3efe6;
      border: 1px solid #333;
      padding: 16px 20px;
      margin-bottom: 28px;
    }
    .queue-head {
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 10px;
      padding-bottom: 12px;
      border-bottom: 1px solid #333;
      margin-bottom: 12px;
    }
    .queue-stats {
      font-family: var(--font-mono);
      font-size: 11.5px;
      color: #cbd5e1;
      display: flex;
      gap: 14px;
      flex-wrap: wrap;
    }
    .queue-list {
      display: flex;
      flex-direction: column;
      gap: 8px;
      max-height: 260px;
      overflow-y: auto;
    }
    .q-item {
      background: #22221f;
      border: 1px solid #363632;
      padding: 9px 14px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 10px;
      font-size: 12px;
    }
    .q-status {
      font-family: var(--font-mono);
      font-size: 10.5px;
      font-weight: 700;
      padding: 2px 7px;
      border-radius: 3px;
      text-transform: uppercase;
    }
    .qs-pending { background: #3b4252; color: #e5e9f0; }
    .qs-running { background: #1d4ed8; color: #fff; }
    .qs-completed { background: #156d3b; color: #fff; }
    .qs-failed { background: #991b1b; color: #fff; }
    .qs-cancelled { background: #4b5563; color: #d1d5db; }
    /* Filter Pills */
    .filter-bar {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-bottom: 14px;
      align-items: center;
      justify-content: space-between;
    }
    .filter-chips {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
    }
    .filter-chip {
      font-family: var(--font-mono);
      font-size: 11.5px;
      padding: 5px 12px;
      border: 1px solid var(--shell-line);
      background: var(--shell-surface);
      color: var(--shell-muted);
      border-radius: 9999px;
      cursor: pointer;
    }
    .filter-chip.active {
      background: var(--shell-ink);
      color: #fff;
      border-color: var(--shell-ink);
    }
    /* Artifact Cards */
    .artifact-cards {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
      gap: 16px;
      margin-bottom: 36px;
    }
    .art-card {
      background: var(--shell-surface);
      border: 1px solid var(--shell-line);
      border-top: 3px solid var(--shell-ink);
      padding: 16px;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      gap: 10px;
    }
    .art-card-kicker {
      font-family: var(--font-mono);
      font-size: 10.5px;
      font-weight: 700;
      color: var(--shell-accent);
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }
    .art-card h3 {
      font-family: var(--font-serif);
      font-size: 19px;
      line-height: 1.35;
      margin: 4px 0;
    }
    .art-card-en {
      font-size: 12.5px;
      color: var(--shell-muted);
      line-height: 1.45;
    }
    .art-card-meta {
      font-family: var(--font-mono);
      font-size: 11px;
      color: var(--shell-muted);
      border-top: 1px solid var(--shell-line);
      padding-top: 10px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 6px;
    }
    .btn-open {
      background: var(--shell-ink);
      color: #fff;
      border: 0;
      padding: 5px 11px;
      font-size: 11px;
      font-weight: 600;
      cursor: pointer;
      border-radius: 3px;
    }
    .btn-gen {
      background: var(--shell-accent);
      color: #fff;
      border: 0;
      padding: 5px 11px;
      font-size: 11px;
      font-weight: 600;
      cursor: pointer;
      border-radius: 3px;
    }
    .btn-canon {
      background: transparent;
      color: var(--shell-ink);
      border: 1px solid var(--shell-line);
      padding: 4px 9px;
      font-size: 11px;
      font-weight: 600;
      cursor: pointer;
      border-radius: 3px;
    }
    /* Workflow & Curation Badges */
    .wf-badge {
      display: inline-block;
      font-family: var(--font-mono);
      font-size: 10.5px;
      font-weight: 700;
      padding: 2px 7px;
      border-radius: 3px;
    }
    .wf-generated { background: #dcfce7; color: #166534; }
    .wf-generating { background: #dbeafe; color: #1e40af; }
    .wf-failed_retry { background: #fee2e2; color: #991b1b; }
    .wf-eligible { background: #fef3c7; color: #92400e; }
    .wf-not_ready { background: #f3f4f6; color: #6b7280; }
    .cur-tier {
      font-family: var(--font-mono);
      font-size: 10.5px;
      font-weight: 700;
      color: var(--shell-accent);
    }
    .cur-reason {
      font-size: 11.5px;
      color: var(--shell-muted);
      line-height: 1.4;
      margin-top: 2px;
    }
    /* Source Table */
    .source-table-wrap {
      overflow-x: auto;
      background: var(--shell-surface);
      border: 1px solid var(--shell-line);
    }
    table.source-tbl {
      width: 100%;
      border-collapse: collapse;
      font-size: 12.5px;
    }
    table.source-tbl th, table.source-tbl td {
      padding: 9px 10px;
      border-bottom: 1px solid var(--shell-line);
      text-align: left;
      vertical-align: middle;
    }
    table.source-tbl th {
      font-family: var(--font-mono);
      font-size: 10.5px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--shell-muted);
      background: #f1ede4;
    }
    .st-pass { color: #156d3b; font-weight: 700; font-family: var(--font-mono); font-size: 11px; }
    .st-warn { color: #b85d19; font-weight: 700; font-family: var(--font-mono); font-size: 11px; }
    .st-block { color: #b91c1c; font-weight: 700; font-family: var(--font-mono); font-size: 11px; }
    /* Modal */
    .modal-backdrop {
      position: fixed;
      inset: 0;
      background: rgba(0, 0, 0, 0.55);
      z-index: 900;
      display: none;
      align-items: center;
      justify-content: center;
      padding: 24px;
    }
    .modal-backdrop.open { display: flex; }
    .modal-box {
      background: var(--shell-surface);
      border: 1px solid var(--shell-ink);
      max-width: 960px;
      width: 100%;
      max-height: 86vh;
      display: flex;
      flex-direction: column;
      box-shadow: 0 20px 50px rgba(0,0,0,0.3);
    }
    .modal-head {
      padding: 14px 20px;
      background: #181816;
      color: #fff;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .modal-body {
      padding: 20px;
      overflow-y: auto;
      font-size: 13px;
      line-height: 1.65;
    }
    .canon-block-row {
      border-bottom: 1px solid var(--shell-line);
      padding: 10px 0;
      display: grid;
      grid-template-columns: 64px 1fr 1fr;
      gap: 14px;
    }
    .canon-pid {
      font-family: var(--font-mono);
      font-weight: 700;
      color: var(--shell-accent);
      font-size: 12px;
    }
    @media (max-width: 768px) {
      .studio-bar { padding: 8px 12px; }
      .brand-name { font-size: 12px; }
      .artifact-cards { grid-template-columns: 1fr; }
      .canon-block-row { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <header class="studio-bar">
    <div class="studio-bar-inner">
      <div class="brand-cluster">
        <span class="brand-sq"></span>
        <span class="brand-name">WSJ 深读 · Daily Production</span>
        <label style="font-size:11px;color:var(--shell-muted);font-weight:600;">期刊 (Issue):</label>
        <select class="issue-select" id="select-issue" onchange="onSwitchIssue(this.value)"></select>
        <div class="nav-tabs">
          <button class="nav-tab active" id="tab-reader" onclick="switchView('reader')">阅读器 (Reader)</button>
          <button class="nav-tab" id="tab-library" onclick="switchView('library')">每日选稿与批量出版 (Curation & Queue)</button>
        </div>
      </div>
      <div class="reader-controls" id="reader-toolbar">
        <label style="font-size:11.5px;color:var(--shell-muted);font-weight:600;">文章:</label>
        <select class="ctrl-select" id="select-article" onchange="onSelectArticle(this.value)"></select>
        <label style="font-size:11.5px;color:var(--shell-muted);font-weight:600;">版本:</label>
        <select class="ctrl-select" id="select-version" onchange="onSelectVersion(this.value)"></select>
        <div class="lang-pill" role="group" aria-label="Language switch">
          <button id="shell-btn-cn" class="active" onclick="setGlobalLang('zh-CN')">中文</button>
          <button id="shell-btn-en" onclick="setGlobalLang('en')">EN</button>
        </div>
        <button class="audit-badge" id="btn-audit-toggle" onclick="toggleInspector()">✓ 100% 原文核验 (Audit)</button>
        <button class="btn-canon" id="btn-reader-canon" onclick="inspectCanonical(currentArticleId)">源结构</button>
        <button class="btn-action" id="btn-regenerate-current" onclick="enqueueSingleFromUI(currentArticleId, true)">↻ 重新生成新版本</button>
      </div>
    </div>
  </header>

  <!-- Live Queue Progress Banner -->
  <div class="job-banner" id="job-banner">
    <div id="job-banner-text">后台生成队列运行中…</div>
    <div id="job-banner-actions"></div>
  </div>

  <!-- Audit & Provenance Inspector Drawer -->
  <section class="inspector-drawer" id="inspector-drawer" aria-label="Artifact Verification Inspector">
    <div class="insp-grid" id="inspector-content"></div>
  </section>

  <!-- View 1: Open Shadow DOM Article Reader -->
  <main class="view-panel active" id="view-reader">
    <div id="editorial-host-container" lang="zh-CN"></div>
  </main>

  <!-- View 2: Daily Editorial Curation, Batch Queue & 117-Article Source Library -->
  <section class="view-panel" id="view-library">
    <div class="library-wrap">
      <!-- Batch Curation & Model Control Console -->
      <div class="batch-console">
        <div class="batch-row">
          <div class="gen-ctrl-group">
            <strong style="font-size:13px;">1. 模型配置 (Model Provider):</strong>
            <select class="ctrl-select" id="select-model" style="max-width:340px;"></select>
            <input type="text" class="gen-input" id="input-custom-notes" placeholder="可选全局/单篇 Art Direction 备注…">
          </div>
          <div style="font-family:var(--font-mono);font-size:11.5px;color:var(--shell-muted);" id="studio-summary-stats"></div>
        </div>
        <div class="batch-row" style="border-top:1px solid var(--shell-line);padding-top:12px;">
          <div class="gen-ctrl-group">
            <strong style="font-size:13px;">2. 每日选稿与批量队列操作 (Batch Curation):</strong>
            <button class="btn-canon" id="btn-select-recommended" onclick="selectRecommendedUngenerated()">★ 一键勾选推荐未生成文章</button>
            <button class="btn-canon" onclick="clearBatchSelection()">清空勾选 (<span id="selected-count-badge">0</span>)</button>
          </div>
          <div class="gen-ctrl-group">
            <button class="btn-action" id="btn-enqueue-selected" onclick="enqueueSelectedBatch()" disabled>✦ 将勾选文章加入后台生成队列 (0)</button>
          </div>
        </div>
      </div>

      <!-- Persistent Background Generation Queue Panel -->
      <div class="queue-panel" id="queue-panel">
        <div class="queue-head">
          <div>
            <strong style="font-size:13.5px;letter-spacing:0.04em;">后台批量生成队列 (Persistent Background Queue · 串行执行 & 断点恢复)</strong>
          </div>
          <div class="queue-stats" id="queue-stats-bar"></div>
        </div>
        <div class="queue-list" id="queue-task-list"></div>
      </div>

      <h2 class="lib-section-title">Daily Reading Library (本期已生成深读制品库)</h2>
      <p class="lib-subtitle">所有已完成制品均持久化保存于磁盘，进程重启或离线均可直接秒开阅读，支持多版本切换。</p>
      <div class="artifact-cards" id="library-cards"></div>

      <h2 class="lib-section-title">Editorial Curation & Source Library (全期 117 篇选稿推荐与状态表)</h2>
      <p class="lib-subtitle">严格执行 Content Integrity Gate：PASS 可直接入队；WARN 提示双语段落/跨页风险并要求确认；BLOCK 与非叙事条目禁止入队。</p>

      <div class="filter-bar" id="filter-bar">
        <div class="filter-chips">
          <button class="filter-chip active" data-filter="all" onclick="setSourceFilter('all')">全部 (117)</button>
          <button class="filter-chip" data-filter="recommended" onclick="setSourceFilter('recommended')">★ 编辑推荐生成</button>
          <button class="filter-chip" data-filter="generated" onclick="setSourceFilter('generated')">已生成制品</button>
          <button class="filter-chip" data-filter="eligible" onclick="setSourceFilter('eligible')">全部可生成 (PASS/WARN)</button>
          <button class="filter-chip" data-filter="generating" onclick="setSourceFilter('generating')">队列执行中</button>
          <button class="filter-chip" data-filter="failed_retry" onclick="setSourceFilter('failed_retry')">失败需重试</button>
          <button class="filter-chip" data-filter="not_ready" onclick="setSourceFilter('not_ready')">非叙事/拦截</button>
        </div>
      </div>

      <div class="source-table-wrap">
        <table class="source-tbl">
          <thead>
            <tr>
              <th style="width:36px;"><input type="checkbox" id="chk-select-all-visible" onchange="toggleSelectAllVisible(this.checked)" title="全选当前可见可生成文章"></th>
              <th>ID / 版面</th>
              <th>类型 / 优先级</th>
              <th>中文标题 / English Headline</th>
              <th>选稿推荐与理由 (Editorial Curation)</th>
              <th>段落 (CN/EN)</th>
              <th>Gate 门禁</th>
              <th>工作流状态</th>
              <th>操作 (Inspect / Queue / Read)</th>
            </tr>
          </thead>
          <tbody id="source-table-body"></tbody>
        </table>
      </div>
    </div>
  </section>

  <!-- Canonical Source & WARN Confirmation Modal -->
  <div class="modal-backdrop" id="canonical-modal" onclick="if(event.target===this)closeCanonicalModal()">
    <div class="modal-box">
      <div class="modal-head">
        <div id="canon-modal-title" style="font-family:var(--font-mono);font-size:13px;font-weight:700;">Canonical Source Inspector</div>
        <button class="btn-open" style="background:#444;" onclick="closeCanonicalModal()">✕ 关闭</button>
      </div>
      <div class="modal-body" id="canon-modal-body"></div>
    </div>
  </div>

  <script id="wsj-issue-payload" type="application/json">__ISSUE_PAYLOAD_JSON__</script>
  <script>
    let PAYLOAD = JSON.parse(document.getElementById("wsj-issue-payload").textContent);
    const hostContainer = document.getElementById("editorial-host-container");
    const shadowRoot = hostContainer.attachShadow({ mode: "open" });

    let currentIssueDate = PAYLOAD.issue_date || "2026-10-12";
    let currentArticleId = null;
    let currentVersionId = null;
    let currentLang = "zh-CN";
    let currentSourceFilter = "all";
    let selectedBatchIds = new Set();
    let activePollTimer = null;

    function switchView(viewName) {
      document.getElementById("view-reader").classList.toggle("active", viewName === "reader");
      document.getElementById("view-library").classList.toggle("active", viewName === "library");
      document.getElementById("tab-reader").classList.toggle("active", viewName === "reader");
      document.getElementById("tab-library").classList.toggle("active", viewName === "library");
      document.getElementById("reader-toolbar").style.display = viewName === "reader" ? "flex" : "none";
    }

    function toggleInspector() {
      document.getElementById("inspector-drawer").classList.toggle("open");
    }

    function setGlobalLang(lang) {
      currentLang = lang;
      document.documentElement.lang = lang;
      hostContainer.setAttribute("lang", lang);
      document.getElementById("shell-btn-cn").classList.toggle("active", lang === "zh-CN");
      document.getElementById("shell-btn-en").classList.toggle("active", lang === "en");
      const innerCn = shadowRoot.getElementById("btn-cn") || shadowRoot.getElementById("btn-zh");
      const innerEn = shadowRoot.getElementById("btn-en");
      if (innerCn) innerCn.classList.toggle("active", lang === "zh-CN");
      if (innerEn) innerEn.classList.toggle("active", lang === "en");
      shadowRoot.querySelectorAll("[onclick*='setLang']").forEach(btn => {
        const txt = btn.textContent.trim();
        if (txt === "中文" || txt === "ZH") btn.classList.toggle("active", lang === "zh-CN");
        if (txt === "EN" || txt === "English") btn.classList.toggle("active", lang === "en");
      });
    }

    window.setLang = function(lang) {
      setGlobalLang(lang === "en" ? "en" : "zh-CN");
    };

    async function onSwitchIssue(issueDate) {
      if (!issueDate || issueDate === currentIssueDate) return;
      currentIssueDate = issueDate;
      selectedBatchIds.clear();
      await refreshStatusFromServer();
      const artIds = Object.keys(PAYLOAD.artifacts);
      if (artIds.length > 0) {
        onSelectArticle(artIds[0]);
      } else {
        switchView("library");
      }
    }

    function renderActiveArtifact() {
      const artEntry = PAYLOAD.artifacts[currentArticleId];
      if (!artEntry) return;
      const verRecord = artEntry.versions[currentVersionId];
      if (!verRecord) return;

      const bundle = verRecord.shadow_bundle;
      shadowRoot.innerHTML = "<style>" + bundle.shadow_css + "</style>" + bundle.shadow_html;
      setGlobalLang(currentLang);
      window.scrollTo({ top: 0, behavior: "instant" });

      const audit = verRecord.validation.compiler_audit;
      const si = audit.source_integrity;
      const st = audit.structural_integrity;
      const inv = audit.derived_and_editorial_inventory;
      const mod = verRecord.model_metadata || {};
      const usage = verRecord.usage_metadata || {};

      document.getElementById("btn-audit-toggle").textContent =
        "✓ 原文核验 " + si.exact_match_cn + " (CN) · " + si.exact_match_en + " (EN)";

      document.getElementById("inspector-content").innerHTML = `
        <div class="insp-card">
          <div class="insp-label">Source & Version Identity</div>
          <div class="insp-val">${verRecord.article_id} · ${verRecord.artifact_version}</div>
          <div style="margin-top:4px;color:#9e9a90;">Issue: ${currentIssueDate} · Digest: ${si.content_digest.slice(0, 14)}…</div>
        </div>
        <div class="insp-card">
          <div class="insp-label">Verbatim Source Integrity</div>
          <div class="insp-val" style="color:#4ade80;">CN: ${si.exact_match_cn} | EN: ${si.exact_match_en}</div>
          <div style="margin-top:4px;color:#9e9a90;">Monotonic Order: ${st.monotonic_order} · Diffs: ${si.verbatim_diffs.length}</div>
        </div>
        <div class="insp-card">
          <div class="insp-label">Editorial Composition Inventory</div>
          <div class="insp-val">${st.observed_narrative_elements} Refs · ${inv.source_derived_count} Derives · ${inv.highlights_applied.length} Highlights</div>
          <div style="margin-top:4px;color:#9e9a90;">SVGs & Headings: ${inv.ai_editorial_items_count} · SVG Auto-Repairs: ${(audit.svg_diagnostics || []).length}</div>
        </div>
        <div class="insp-card">
          <div class="insp-label">Model & Usage Metadata</div>
          <div class="insp-val">${mod.provider || "provider"} / ${mod.model_id || "model"}</div>
          <div style="margin-top:4px;color:#9e9a90;">Tokens: ${usage.total_tokens || "N/A"} · Latency: ${usage.latency_seconds ? usage.latency_seconds + "s" : "N/A"}</div>
        </div>
      `;
    }

    function populateVersionSelector(articleId, preferredVersion) {
      const artEntry = PAYLOAD.artifacts[articleId];
      const selVer = document.getElementById("select-version");
      selVer.innerHTML = "";
      if (!artEntry) return;
      const vList = artEntry.summary.versions || [];
      vList.forEach(v => {
        const opt = document.createElement("option");
        opt.value = v.version;
        opt.textContent = `${v.version} (${v.model_id} · ${v.exact_match_cn})`;
        selVer.appendChild(opt);
      });
      currentVersionId = preferredVersion || artEntry.active_version || (vList[vList.length - 1] && vList[vList.length - 1].version);
      selVer.value = currentVersionId;
    }

    function onSelectArticle(articleId, preferredVersion) {
      if (!PAYLOAD.artifacts[articleId]) return;
      currentArticleId = articleId;
      document.getElementById("select-article").value = articleId;
      populateVersionSelector(articleId, preferredVersion);
      renderActiveArtifact();
      switchView("reader");
    }

    async function onSelectVersion(versionId) {
      currentVersionId = versionId;
      renderActiveArtifact();
      try {
        await fetch("/api/activate-version", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ issue: currentIssueDate, article_id: currentArticleId, version_id: versionId })
        });
      } catch (e) {}
    }

    function updateBatchSelectionButtons() {
      const count = selectedBatchIds.size;
      const badge = document.getElementById("selected-count-badge");
      if (badge) badge.textContent = String(count);
      const btn = document.getElementById("btn-enqueue-selected");
      if (btn) {
        btn.disabled = count === 0;
        btn.textContent = `✦ 将勾选文章加入后台生成队列 (${count})`;
      }
    }

    function toggleArticleCheckbox(articleId, checked) {
      if (checked) {
        selectedBatchIds.add(articleId);
      } else {
        selectedBatchIds.delete(articleId);
      }
      updateBatchSelectionButtons();
    }

    function selectRecommendedUngenerated() {
      selectedBatchIds.clear();
      (PAYLOAD.source_library || []).forEach(item => {
        if (item.curation && item.curation.recommended && !item.has_editorial_artifact && item.gate_status === "pass") {
          selectedBatchIds.add(item.id);
        }
      });
      updateBatchSelectionButtons();
      renderSourceTable();
    }

    function clearBatchSelection() {
      selectedBatchIds.clear();
      const chkAll = document.getElementById("chk-select-all-visible");
      if (chkAll) chkAll.checked = false;
      updateBatchSelectionButtons();
      renderSourceTable();
    }

    function toggleSelectAllVisible(checked) {
      const visibleRows = getFilteredSourceRows();
      visibleRows.forEach(item => {
        if (item.curation && item.curation.can_enqueue) {
          if (checked) selectedBatchIds.add(item.id);
          else selectedBatchIds.delete(item.id);
        }
      });
      updateBatchSelectionButtons();
      renderSourceTable();
    }

    function setSourceFilter(filterKey) {
      currentSourceFilter = filterKey;
      document.querySelectorAll("#filter-bar .filter-chip").forEach(btn => {
        btn.classList.toggle("active", btn.getAttribute("data-filter") === filterKey);
      });
      renderSourceTable();
    }

    function getFilteredSourceRows() {
      return (PAYLOAD.source_library || []).filter(item => {
        if (currentSourceFilter === "all") return true;
        if (currentSourceFilter === "recommended") return Boolean(item.curation && item.curation.recommended);
        return item.workflow_state === currentSourceFilter;
      });
    }

    function renderQueuePanel() {
      const q = PAYLOAD.queue || { counts: {}, tasks: [] };
      const c = q.counts || {};
      const statsBar = document.getElementById("queue-stats-bar");
      if (statsBar) {
        statsBar.innerHTML = `
          <span>Running: <strong style="color:#38bdf8;">${c.running || 0}</strong></span>
          <span>Pending: <strong style="color:#fcd34d;">${c.pending || 0}</strong></span>
          <span>Completed: <strong style="color:#4ade80;">${c.completed || 0}</strong></span>
          <span>Failed: <strong style="color:#f87171;">${c.failed || 0}</strong></span>
          <span>Cancelled: <strong>${c.cancelled || 0}</strong></span>
        `;
      }

      const listEl = document.getElementById("queue-task-list");
      if (!listEl) return;
      const tasks = q.tasks || [];
      if (tasks.length === 0) {
        listEl.innerHTML = `<div style="color:#888;font-size:12px;">队列当前为空。在下方选稿表中勾选文章并点击“将勾选文章加入后台生成队列”即可启动批量生成。</div>`;
        return;
      }

      listEl.innerHTML = tasks.slice(0, 20).map(t => {
        const st = t.status || "pending";
        const actions = [];
        if (st === "completed" && t.artifact_version) {
          actions.push(`<button class="btn-open" style="background:#156d3b;" onclick="onSelectArticle('${t.article_id}', '${t.artifact_version}')">打开阅读 (${t.artifact_version})</button>`);
        }
        if (st === "pending") {
          actions.push(`<button class="btn-open" style="background:#4b5563;" onclick="cancelQueueTask('${t.task_id}')">取消</button>`);
        }
        if (st === "failed" || st === "cancelled") {
          actions.push(`<button class="btn-gen" onclick="retryQueueTask('${t.task_id}')">↻ 重试</button>`);
        }
        const recTag = t.recovered_from_restart ? `<span style="color:#fbbf24;font-family:var(--font-mono);font-size:10px;">[重启恢复]</span> ` : "";
        return `
          <div class="q-item" data-task-id="${t.task_id}">
            <div>
              <span class="q-status qs-${st}">${st}</span>
              <strong style="margin-left:8px;">${t.article_id} · ${t.title_cn}</strong>
              <span style="color:#9ca3af;font-family:var(--font-mono);font-size:11px;margin-left:6px;">(${t.model_id})</span>
              <div style="color:#cbd5e1;font-size:11.5px;margin-top:3px;">${recTag}${t.detail || ""}</div>
            </div>
            <div style="display:flex;gap:6px;">${actions.join("")}</div>
          </div>
        `;
      }).join("");
    }

    function renderSourceTable() {
      const tbody = document.getElementById("source-table-body");
      const rows = getFilteredSourceRows();

      tbody.innerHTML = rows.map(item => {
        const gateClass = item.gate_status === "pass" ? "st-pass" : (item.gate_status === "warn" ? "st-warn" : "st-block");
        const wfClass = "wf-" + item.workflow_state;
        const cur = item.curation || {};
        const canCheck = Boolean(cur.can_enqueue);
        const isChecked = selectedBatchIds.has(item.id);
        const buttons = [];

        buttons.push(`<button class="btn-canon" onclick="inspectCanonical('${item.id}')">源结构</button>`);

        if (item.has_editorial_artifact) {
          buttons.push(`<button class="btn-open" onclick="onSelectArticle('${item.id}')">打开 (${item.active_version})</button>`);
          buttons.push(`<button class="btn-gen" onclick="enqueueSingleFromUI('${item.id}', true)">↻ 新版本</button>`);
        } else if (item.workflow_state === "generating") {
          buttons.push(`<button class="btn-gen" disabled>队列中…</button>`);
        } else if (canCheck) {
          const lbl = item.workflow_state === "failed_retry" ? "↻ 重试生成" : "✦ 加入队列";
          buttons.push(`<button class="btn-gen" id="btn-gen-${item.id}" onclick="enqueueSingleFromUI('${item.id}', false)">${lbl}</button>`);
        }

        return `
          <tr data-article-row="${item.id}">
            <td>
              <input type="checkbox" class="batch-chk" data-chk-id="${item.id}"
                ${canCheck ? "" : "disabled"}
                ${isChecked ? "checked" : ""}
                onchange="toggleArticleCheckbox('${item.id}', this.checked)">
            </td>
            <td style="font-family:var(--font-mono);font-weight:700;">
              ${item.id}<div style="font-weight:400;font-size:11px;color:#666;">${item.page} · ${item.section}</div>
            </td>
            <td style="font-family:var(--font-mono);font-size:11px;">${item.type} · ${item.priority}</td>
            <td>
              <strong>${item.title_cn}</strong>
              <div style="color:#666;font-size:11.5px;">${item.title_en}</div>
            </td>
            <td style="max-width:300px;">
              <div class="cur-tier">${cur.tier_label || ""}</div>
              <div class="cur-reason">${cur.reason || ""}</div>
            </td>
            <td style="font-family:var(--font-mono);">${item.paras_cn} / ${item.paras_en}</td>
            <td><span class="${gateClass}">${item.gate_status.toUpperCase()}</span></td>
            <td><span class="wf-badge ${wfClass}">${item.workflow_label}</span></td>
            <td><div style="display:flex;gap:5px;flex-wrap:wrap;">${buttons.join("")}</div></td>
          </tr>
        `;
      }).join("");
    }

    function renderStudioUI() {
      // Populate Issue Selector
      const selIssue = document.getElementById("select-issue");
      if (selIssue) {
        selIssue.innerHTML = "";
        (PAYLOAD.available_issues || [{ issue: currentIssueDate, date_cn: currentIssueDate }]).forEach(iss => {
          const opt = document.createElement("option");
          opt.value = iss.issue;
          opt.textContent = `${iss.issue} (${iss.date_cn} · ${iss.generated_count || 0}篇制品)`;
          if (iss.issue === currentIssueDate) opt.selected = true;
          selIssue.appendChild(opt);
        });
      }

      // Populate Model Selector
      const selModel = document.getElementById("select-model");
      if (selModel && selModel.options.length === 0) {
        (PAYLOAD.configured_models || []).forEach(m => {
          const opt = document.createElement("option");
          opt.value = `${m.provider}:::${m.model_id}`;
          opt.textContent = m.label + (m.recommended ? " ★ 推荐" : "");
          if (m.recommended) opt.selected = true;
          selModel.appendChild(opt);
        });
      }

      const sc = PAYLOAD.state_counts || {};
      const statsEl = document.getElementById("studio-summary-stats");
      if (statsEl) {
        statsEl.textContent = `推荐深读: ${sc.recommended || 0} 篇 · 已生成: ${sc.generated || 0} 篇 · 可生成: ${sc.eligible || 0} 篇 · 队列中: ${sc.generating || 0} 篇`;
      }

      const countMap = {
        all: PAYLOAD.total_source_items,
        recommended: sc.recommended || 0,
        generated: sc.generated || 0,
        eligible: sc.eligible || 0,
        generating: sc.generating || 0,
        failed_retry: sc.failed_retry || 0,
        not_ready: sc.not_ready || 0
      };
      document.querySelectorAll("#filter-bar .filter-chip").forEach(btn => {
        const fk = btn.getAttribute("data-filter");
        const baseLabels = {
          all: "全部",
          recommended: "★ 编辑推荐生成",
          generated: "已生成制品",
          eligible: "全部可生成 (PASS/WARN)",
          generating: "队列执行中",
          failed_retry: "失败需重试",
          not_ready: "非叙事/拦截"
        };
        if (baseLabels[fk]) {
          btn.textContent = `${baseLabels[fk]} (${countMap[fk] ?? 0})`;
        }
      });

      const selArt = document.getElementById("select-article");
      const prevSelected = currentArticleId;
      selArt.innerHTML = "";
      const artIds = Object.keys(PAYLOAD.artifacts);
      artIds.forEach(aid => {
        const s = PAYLOAD.artifacts[aid].summary;
        const opt = document.createElement("option");
        opt.value = aid;
        opt.textContent = `${aid} · ${s.title_cn}`;
        selArt.appendChild(opt);
      });
      if (prevSelected && PAYLOAD.artifacts[prevSelected]) {
        selArt.value = prevSelected;
      }

      const cardsWrap = document.getElementById("library-cards");
      cardsWrap.innerHTML = artIds.map(aid => {
        const entry = PAYLOAD.artifacts[aid];
        const s = entry.summary;
        const activeVer = entry.versions[entry.active_version];
        const si = activeVer ? activeVer.validation.compiler_audit.source_integrity : {};
        const vButtons = (s.versions || []).map(v =>
          `<button class="btn-open" style="background:${v.version === entry.active_version ? '#111' : '#646059'};" onclick="onSelectArticle('${aid}', '${v.version}')">打开 ${v.version}</button>`
        ).join(" ");
        return `
          <article class="art-card" data-library-card="${aid}">
            <div>
              <div class="art-card-kicker">${s.section} · PAGE ${s.page} · ${aid}</div>
              <h3>${s.title_cn}</h3>
              <div class="art-card-en">${s.title_en}</div>
            </div>
            <div class="art-card-meta">
              <span>✓ 原文保真 ${si.exact_match_cn || ""} · 共 ${(s.versions || []).length} 个版本</span>
              <div style="display:flex;gap:6px;flex-wrap:wrap;">
                ${vButtons}
                <button class="btn-gen" onclick="enqueueSingleFromUI('${aid}', true)">↻ 新版本</button>
              </div>
            </div>
          </article>
        `;
      }).join("");

      updateBatchSelectionButtons();
      renderQueuePanel();
      renderSourceTable();
    }

    async function inspectCanonical(articleId, showWarnPrompt = false) {
      if (!articleId) return;
      const modal = document.getElementById("canonical-modal");
      const titleEl = document.getElementById("canon-modal-title");
      const bodyEl = document.getElementById("canon-modal-body");
      modal.classList.add("open");
      titleEl.textContent = `Canonical Source & Gate Inspector · ${articleId}`;
      bodyEl.innerHTML = "Loading Canonical Source…";

      let canon = PAYLOAD.artifacts[articleId] && PAYLOAD.artifacts[articleId].canonical;
      if (!canon) {
        try {
          const resp = await fetch(`/api/canonical?issue=${encodeURIComponent(currentIssueDate)}&article_id=${encodeURIComponent(articleId)}`);
          if (resp.ok) canon = await resp.json();
        } catch (e) {}
      }
      if (!canon) {
        const libItem = PAYLOAD.source_library.find(x => x.id === articleId);
        bodyEl.innerHTML = `<p>当前为静态离线模式，请通过 <code>python3 render/editorial_studio.py --serve</code> 启动服务以实时检视未生成文章的完整 Canonical Source。</p>
        ${libItem ? `<pre style="margin-top:12px;background:#f1ede4;padding:12px;">${JSON.stringify(libItem, null, 2)}</pre>` : ""}`;
        return;
      }

      const libItem = PAYLOAD.source_library.find(x => x.id === articleId) || {};
      const cur = libItem.curation || {};
      const gate = canon.integrity_gate || {};
      let warnBoxHtml = "";
      if (gate.status === "warn" || (cur.warn_risks && cur.warn_risks.length)) {
        const riskItems = (cur.warn_risks || gate.issues || []).map(r => `<li><strong>[${r.code}]</strong> ${r.risk_explanation || r.detail}</li>`).join("");
        warnBoxHtml = `
          <div style="background:#fffbeb;border:2px solid #d97706;padding:14px 16px;margin-bottom:14px;">
            <div style="color:#92400e;font-weight:700;margin-bottom:6px;">⚠️ Content Integrity Gate 风险确认 (WARN Gate Confirmation Required)</div>
            <ul style="padding-left:18px;color:#78350f;font-size:12.5px;margin-bottom:10px;">${riskItems}</ul>
            <button class="btn-gen" onclick="closeCanonicalModal();submitQueueRequest(['${canon.article_id}'], true, true)">✓ 我已核实双语段落与跨页内容，确认加入生成队列</button>
          </div>
        `;
      }

      const blocksHtml = (canon.blocks || []).map(b => `
        <div class="canon-block-row">
          <div class="canon-pid">[${b.id}]<br><span style="font-size:10px;color:#666;">${b.sentences ? b.sentences.length + " sents" : ""}</span></div>
          <div>${b.text_cn}</div>
          <div style="color:#444;font-family:Georgia,serif;">${b.text_en}</div>
        </div>
      `).join("");

      bodyEl.innerHTML = `
        ${warnBoxHtml}
        <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px;padding-bottom:14px;border-bottom:2px solid #111;margin-bottom:14px;">
          <div>
            <div style="font-family:var(--font-mono);font-size:11.5px;color:var(--shell-accent);font-weight:700;">
              ${canon.article_id} · ${canon.metadata.section} · Page ${canon.metadata.page} · Digest: ${canon.content_digest.slice(0, 16)}…
            </div>
            <h3 style="font-family:var(--font-serif);font-size:22px;margin:4px 0;">${canon.metadata.title_cn}</h3>
            <div style="color:#555;">${canon.metadata.title_en}</div>
          </div>
          ${gate.status !== "block" ? `<button class="btn-gen" onclick="closeCanonicalModal();submitQueueRequest(['${canon.article_id}'], true, true)">✦ 确认并加入生成队列</button>` : ""}
        </div>
        <div style="margin-bottom:14px;font-family:var(--font-mono);font-size:12px;background:#f3efe6;padding:10px 14px;">
          Integrity Gate: <strong>${(gate.status || "pass").toUpperCase()}</strong> |
          Curation: <strong>${cur.tier_label || "Standard"}</strong> |
          Canonical Paragraphs: <strong>${(canon.blocks || []).length}</strong> |
          Derived Quotes: <strong>${(canon.derived_quotes || []).length}</strong> |
          Derived Metrics: <strong>${(canon.derived_metrics || []).length}</strong>
        </div>
        <div>${blocksHtml}</div>
      `;
    }

    function closeCanonicalModal() {
      document.getElementById("canonical-modal").classList.remove("open");
    }

    async function enqueueSingleFromUI(articleId, forceNew = false) {
      if (!articleId) return;
      const libItem = (PAYLOAD.source_library || []).find(x => x.id === articleId);
      if (libItem && libItem.curation && libItem.curation.requires_warn_confirmation && !forceNew) {
        inspectCanonical(articleId, true);
        return;
      }
      await submitQueueRequest([articleId], forceNew, true);
    }

    async function enqueueSelectedBatch() {
      const ids = Array.from(selectedBatchIds);
      if (ids.length === 0) return;
      // Check if any selected article has unconfirmed WARN
      const warnItems = ids.filter(id => {
        const it = (PAYLOAD.source_library || []).find(x => x.id === id);
        return it && it.curation && it.curation.requires_warn_confirmation;
      });
      if (warnItems.length > 0) {
        inspectCanonical(warnItems[0], true);
        return;
      }
      await submitQueueRequest(ids, false, false);
      selectedBatchIds.clear();
      updateBatchSelectionButtons();
    }

    async function submitQueueRequest(articleIds, forceNew = false, confirmWarn = false) {
      const selModel = document.getElementById("select-model");
      const rawModelVal = selModel ? selModel.value : "magpie:::google-vertex/gemini-4-argon";
      const [providerName, modelId] = rawModelVal.split(":::");
      const customNotes = (document.getElementById("input-custom-notes") && document.getElementById("input-custom-notes").value) || "";

      const banner = document.getElementById("job-banner");
      const bannerText = document.getElementById("job-banner-text");
      const bannerActions = document.getElementById("job-banner-actions");
      banner.className = "job-banner active";
      bannerText.textContent = `⏳ 正在将 ${articleIds.join(", ")} 加入后台出版队列 (${modelId})…`;
      bannerActions.innerHTML = "";

      try {
        const resp = await fetch("/api/queue/enqueue", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            issue: currentIssueDate,
            article_ids: articleIds,
            provider: providerName,
            model_id: modelId,
            custom_instructions: customNotes,
            force_new: forceNew,
            confirm_warn: confirmWarn
          })
        });
        const data = await resp.json();
        if (!resp.ok) {
          throw new Error(data.error || "Failed to enqueue articles");
        }
        await refreshStatusFromServer();
        ensureQueuePolling();
      } catch (err) {
        banner.className = "job-banner active failed";
        bannerText.textContent = `❌ 入队失败: ${err.message}`;
      }
    }

    async function cancelQueueTask(taskId) {
      try {
        await fetch("/api/queue/cancel", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ issue: currentIssueDate, task_id: taskId })
        });
        await refreshStatusFromServer();
      } catch (e) {}
    }

    async function retryQueueTask(taskId) {
      try {
        await fetch("/api/queue/retry", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ issue: currentIssueDate, task_id: taskId })
        });
        await refreshStatusFromServer();
        ensureQueuePolling();
      } catch (e) {}
    }

    async function refreshStatusFromServer() {
      try {
        const resp = await fetch(`/api/status?issue=${encodeURIComponent(currentIssueDate)}`);
        if (resp.ok) {
          PAYLOAD = await resp.json();
          renderStudioUI();
        }
      } catch (e) {}
    }

    function ensureQueuePolling() {
      if (activePollTimer) return;
      const banner = document.getElementById("job-banner");
      const bannerText = document.getElementById("job-banner-text");
      const bannerActions = document.getElementById("job-banner-actions");

      activePollTimer = setInterval(async () => {
        await refreshStatusFromServer();
        const q = PAYLOAD.queue || { counts: {}, tasks: [] };
        const c = q.counts || {};
        const runningTask = (q.tasks || []).find(t => t.status === "running");

        if (runningTask || (c.pending || 0) > 0) {
          banner.className = "job-banner active";
          const curTxt = runningTask
            ? `正在生成 ${runningTask.article_id} (${runningTask.title_cn}) — ${runningTask.detail}`
            : `等待执行中 (${c.pending} 篇排队)`;
          bannerText.textContent = `⚙️ [队列进度: 已完成 ${c.completed || 0} / 排队 ${c.pending || 0} / 运行中 ${c.running || 0}] ${curTxt}`;
          bannerActions.innerHTML = `<button class="btn-open" onclick="switchView('library')">查看队列详情</button>`;
        } else {
          clearInterval(activePollTimer);
          activePollTimer = null;
          const latestTask = (q.tasks || [])[0];
          if (latestTask && latestTask.status === "completed") {
            banner.className = "job-banner active completed";
            bannerText.textContent = `✓ 队列已全部完成！最新完成：${latestTask.article_id} (${latestTask.artifact_version}) — ${latestTask.detail}`;
            bannerActions.innerHTML = `<button class="btn-open" onclick="onSelectArticle('${latestTask.article_id}', '${latestTask.artifact_version}')">立即打开阅读 ${latestTask.article_id} →</button>`;
          } else if (latestTask && latestTask.status === "failed") {
            banner.className = "job-banner active failed";
            bannerText.textContent = `⚠️ 队列执行结束（含失败任务 ${latestTask.article_id}）：${latestTask.detail}`;
            bannerActions.innerHTML = `<button class="btn-gen" onclick="retryQueueTask('${latestTask.task_id}')">↻ 重试失败任务</button>`;
          }
        }
      }, 1000);
    }

    function initStudio() {
      renderStudioUI();
      const artIds = Object.keys(PAYLOAD.artifacts);
      if (artIds.length > 0) {
        const hashParams = new URLSearchParams(location.hash.replace(/^#/, ""));
        const initialAid = hashParams.get("article") && PAYLOAD.artifacts[hashParams.get("article")]
          ? hashParams.get("article")
          : artIds[0];
        const initialVer = hashParams.get("version") || undefined;
        onSelectArticle(initialAid, initialVer);
      } else {
        switchView("library");
      }
      const q = PAYLOAD.queue || { counts: {} };
      if ((q.counts.running || 0) > 0 || (q.counts.pending || 0) > 0) {
        ensureQueuePolling();
      }
    }

    window.addEventListener("hashchange", () => {
      const hp = new URLSearchParams(location.hash.replace(/^#/, ""));
      const aid = hp.get("article");
      const ver = hp.get("version") || undefined;
      if (aid && PAYLOAD.artifacts[aid]) {
        onSelectArticle(aid, ver);
      }
    });

    window.switchView = switchView;
    window.toggleInspector = toggleInspector;
    window.setGlobalLang = setGlobalLang;
    window.onSwitchIssue = onSwitchIssue;
    window.onSelectArticle = onSelectArticle;
    window.onSelectVersion = onSelectVersion;
    window.setSourceFilter = setSourceFilter;
    window.inspectCanonical = inspectCanonical;
    window.closeCanonicalModal = closeCanonicalModal;
    window.toggleArticleCheckbox = toggleArticleCheckbox;
    window.selectRecommendedUngenerated = selectRecommendedUngenerated;
    window.clearBatchSelection = clearBatchSelection;
    window.toggleSelectAllVisible = toggleSelectAllVisible;
    window.enqueueSingleFromUI = enqueueSingleFromUI;
    window.enqueueSelectedBatch = enqueueSelectedBatch;
    window.submitQueueRequest = submitQueueRequest;
    window.cancelQueueTask = cancelQueueTask;
    window.retryQueueTask = retryQueueTask;
    window.refreshStatusFromServer = refreshStatusFromServer;
    initStudio();
  </script>
</body>
</html>
"""


def build_editorial_reader_html(issue_dir: str, output_filename: str = "editorial-reader.html") -> str:
    payload = collect_issue_payload(issue_dir)
    payload_json = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    html_out = READER_TEMPLATE_HTML.replace("__ISSUE_PAYLOAD_JSON__", payload_json)

    dist_dir = os.path.join(os.path.abspath(issue_dir), "dist")
    os.makedirs(dist_dir, exist_ok=True)
    out_path = os.path.join(dist_dir, output_filename)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html_out)
    return out_path


def _resolve_issue_dir(default_issue_dir: str, requested_issue: str | None) -> str:
    if not requested_issue:
        return default_issue_dir
    clean_name = os.path.basename(requested_issue.strip())
    candidate = os.path.join(os.path.dirname(os.path.abspath(default_issue_dir)), clean_name)
    if os.path.isdir(candidate) and os.path.isfile(os.path.join(candidate, "final.json")):
        return candidate
    return default_issue_dir


def create_studio_http_server(
    issue_dir: str,
    port: int = 8788,
    provider_override: ModelProvider | None = None,
) -> ThreadingHTTPServer:
    """Create a ThreadingHTTPServer with full REST API support for Daily Curation & Persistent Batch Queue."""
    default_issue_dir = os.path.abspath(issue_dir)
    # Initialize & recover queue on startup
    get_issue_queue(default_issue_dir, provider_override=provider_override, auto_start_worker=True)
    build_editorial_reader_html(default_issue_dir)

    class StudioHandler(SimpleHTTPRequestHandler):
        def __init__(self, *args: Any, **kwargs: Any):
            super().__init__(*args, directory=default_issue_dir, **kwargs)

        def log_message(self, format: str, *args: Any) -> None:
            pass

        def _send_json(self, status_code: int, payload: Any) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            qs = parse_qs(parsed.query)
            req_issue = (qs.get("issue") or [None])[0]
            active_idir = _resolve_issue_dir(default_issue_dir, req_issue)

            if parsed.path == "/api/issues":
                return self._send_json(200, {"issues": discover_issues(os.path.dirname(default_issue_dir))})

            if parsed.path == "/api/status":
                return self._send_json(200, collect_issue_payload(active_idir, provider_override=provider_override))

            if parsed.path == "/api/models":
                return self._send_json(200, {"models": list_configured_models()})

            if parsed.path == "/api/canonical":
                aid = (qs.get("article_id") or [""])[0].strip()
                if not aid:
                    return self._send_json(400, {"error": "Missing article_id query parameter"})
                try:
                    canon = load_canonical_for_issue(active_idir, article_id=aid)
                    return self._send_json(200, canon)
                except KeyError as ke:
                    return self._send_json(404, {"error": str(ke)})

            if parsed.path in ("/api/queue", "/api/jobs"):
                q = get_issue_queue(active_idir, provider_override=provider_override)
                summary = q.get_summary()
                jid = (qs.get("job_id") or qs.get("task_id") or [""])[0].strip()
                if jid:
                    t_match = next((t for t in summary["tasks"] if t["task_id"] == jid), None)
                    if not t_match:
                        return self._send_json(404, {"error": f"Unknown task_id: {jid}"})
                    return self._send_json(200, t_match)
                return self._send_json(200, summary)

            if parsed.path in ("/", "/reader", "/studio"):
                payload = collect_issue_payload(active_idir, provider_override=provider_override)
                payload_json = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
                html_bytes = READER_TEMPLATE_HTML.replace("__ISSUE_PAYLOAD_JSON__", payload_json).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(html_bytes)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(html_bytes)
                return

            return super().do_GET()

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            content_len = int(self.headers.get("Content-Length") or 0)
            raw_body = self.rfile.read(content_len).decode("utf-8") if content_len > 0 else "{}"
            try:
                body = json.loads(raw_body)
            except Exception:
                return self._send_json(400, {"error": "Invalid JSON request body"})

            active_idir = _resolve_issue_dir(default_issue_dir, body.get("issue"))
            q = get_issue_queue(active_idir, provider_override=provider_override)

            if parsed.path in ("/api/queue/enqueue", "/api/generate"):
                # Support both batch `article_ids: [...]` and single `article_id: "..."`
                aids = body.get("article_ids")
                if not aids and body.get("article_id"):
                    aids = [body["article_id"]]
                if not aids or not isinstance(aids, list):
                    return self._send_json(400, {"error": "article_ids list or article_id is required"})

                provider_name = (body.get("provider") or "magpie").strip()
                model_id = (body.get("model_id") or DEFAULT_EDITORIAL_MODEL_ID).strip()
                custom_instructions = (body.get("custom_instructions") or "").strip()
                confirm_warn = bool(body.get("confirm_warn", True if parsed.path == "/api/generate" else False))
                force_new = bool(body.get("force_new", False))
                blocking = bool(body.get("blocking", False))

                res = q.enqueue_articles(
                    article_ids=aids,
                    provider_name=provider_name,
                    model_id=model_id,
                    custom_instructions=custom_instructions,
                    confirm_warn=confirm_warn,
                    force_new=force_new,
                    start_worker=not blocking,
                )
                if res["rejected"] and not res["enqueued"] and not res["deduplicated"]:
                    first_rej = res["rejected"][0]
                    return self._send_json(400, {"error": first_rej["reason"], "rejected": res["rejected"]})

                if blocking:
                    processed = q.run_all_pending_sync()
                    build_editorial_reader_html(active_idir)
                    if len(aids) == 1 and processed:
                        last_t = processed[-1]
                        return self._send_json(200, {**last_t, "job_id": last_t["task_id"], "queue_result": res})
                    return self._send_json(200, {"processed": processed, "queue_result": res})

                first_task = (res["enqueued"] or res["deduplicated"] or [{}])[0]
                return self._send_json(202, {**res, "job_id": first_task.get("task_id"), "task": first_task})

            if parsed.path == "/api/queue/cancel":
                tid = (body.get("task_id") or "").strip()
                if not tid:
                    return self._send_json(400, {"error": "task_id is required"})
                try:
                    t_rec = q.cancel_task(tid)
                    return self._send_json(200, t_rec)
                except KeyError as ke:
                    return self._send_json(404, {"error": str(ke)})

            if parsed.path == "/api/queue/retry":
                tid = (body.get("task_id") or "").strip()
                if not tid:
                    return self._send_json(400, {"error": "task_id is required"})
                try:
                    res = q.retry_task(tid, start_worker=not bool(body.get("blocking", False)))
                    if body.get("blocking"):
                        q.run_all_pending_sync()
                    return self._send_json(200, res)
                except KeyError as ke:
                    return self._send_json(404, {"error": str(ke)})

            if parsed.path == "/api/activate-version":
                aid = (body.get("article_id") or "").strip()
                vid = (body.get("version_id") or "").strip()
                if not aid or not vid:
                    return self._send_json(400, {"error": "article_id and version_id are required"})
                try:
                    store = ArtifactStore(active_idir)
                    rec = store.set_active_version(aid, vid)
                    build_editorial_reader_html(active_idir)
                    return self._send_json(200, {"status": "ok", "active_version": rec["artifact_version"]})
                except KeyError as ke:
                    return self._send_json(404, {"error": str(ke)})

            return self._send_json(404, {"error": f"Unknown endpoint {parsed.path}"})

    return ThreadingHTTPServer(("127.0.0.1", port), StudioHandler)


def run_studio_server(issue_dir: str, port: int = 8788) -> None:
    server = create_studio_http_server(issue_dir, port=port)
    print(f"WSJ Daily Production Studio serving at http://127.0.0.1:{port}/studio")
    server.serve_forever()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="WSJ 深读 · Daily Production Studio & Batch Queue")
    ap.add_argument("--issue", default="2026-10-12", help="Issue date directory name")
    ap.add_argument("--output", default="editorial-reader.html", help="Output filename in dist/")
    ap.add_argument("--serve", action="store_true", help="Launch local interactive HTTP server")
    ap.add_argument("--port", type=int, default=8788, help="HTTP server port")
    ap.add_argument("--enqueue", nargs="+", metavar="ARTICLE_ID", help="Enqueue and run one or more articles synchronously")
    ap.add_argument("--model", default=DEFAULT_EDITORIAL_MODEL_ID, help="Model ID for --enqueue")
    args = ap.parse_args()

    issue_path = os.path.join(REPO_ROOT, args.issue)
    if args.enqueue:
        q = get_issue_queue(issue_path, auto_start_worker=False)
        enq = q.enqueue_articles(article_ids=args.enqueue, model_id=args.model, confirm_warn=True, start_worker=False)
        processed = q.run_all_pending_sync()
        print(json.dumps({"enqueued": enq, "processed": processed}, ensure_ascii=False, indent=2))

    out_file = build_editorial_reader_html(issue_path, output_filename=args.output)
    print(f"Built Editorial Reader: {out_file}")
    if args.serve:
        run_studio_server(issue_path, port=args.port)
