#!/usr/bin/env python3
"""WSJ 深读 · Phase 7 Editorial Curation & Persistent Background Generation Queue (`generation_queue.py`).

Responsibilities:
1. Multi-Issue Discovery (`discover_issues`):
   Scans the repository for all issue directories (`YYYY-MM-DD/final.json`) so the system is never
   hardcoded to `2026-10-12`.
2. Editorial Curation & Recommendation Engine (`evaluate_article_curation`):
   Integrates `front.json` (lead & also-reads), `render/curation.json` (exclusions & data treatments),
   `editorial-plans/*.json`, article metadata (`page`, `section`, `type`, `priority`, paragraph count),
   and `integrity_gate.py` (`PASS` / `WARN` / `BLOCK`):
   - Strictly enforces Content Gate:
     * `BLOCK` articles are rejected from entering the normal publishing queue.
     * `WARN` articles return explicit `warn_risks` (`para_misaligned`, `turn_to_unconfirmed`, `too_few_paras`)
       and require explicit confirmation (`confirm_warn=True`) or repair before queueing.
     * `PASS` articles are eligible for normal queueing.
   - Computes Curation Tier & Recommendation Reason:
     * `recommended_lead`: Front-page lead / also-read / A1 flagship deep investigation
     * `recommended_feature`: P1/P2 in-depth analysis, feature, or opinion (`>= 6` paragraphs)
     * `optional_brief`: Short news / brief (`1..5` paragraphs, recommends restrained compact layout)
     * `not_recommended`: Non-narrative tables, index digests, photo captions, or excluded items
3. Persistent Background Generation Queue (`PersistentGenerationQueue`):
   - Persists queue state to `<issue_dir>/editorial-artifacts/_queue.json` via atomic file replacement.
   - Supports task states: `pending`, `running`, `completed`, `failed`, `cancelled`.
   - Prevents accidental duplicate submissions: if an article already has a `pending` or `running` task
     with the same `(article_id, model_id, content_digest)` and `force_new=False`, returns the existing task!
   - Executes tasks serially in a single background daemon thread (`max_concurrency = 1`) so failure in
     one task never blocks the rest of the queue, and historical verified artifacts remain untouched.
   - Process-Restart Recovery (`recover_on_startup`): when Studio restarts after an exit/crash, any task
     left in `running` state is inspected:
     * If its target artifact version was already saved and verified on disk before exit, marks it `completed`.
     * Otherwise transitions `running` -> `pending` (with `recovered_from_restart=True`) and resumes serial execution.
"""
from __future__ import annotations

import datetime
import json
import os
import re
import threading
import time
import uuid
from typing import Any, Callable

BASE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(BASE)

from artifact_store import ArtifactStore
from canonical_builder import load_canonical_for_issue
from editorial_publisher import publish_article
from integrity_gate import check_article
from model_provider import (
    DEFAULT_EDITORIAL_MODEL_ID,
    ModelProvider,
    create_provider_for_model,
)
from source_model import content_digest


def _utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def discover_issues(repo_root: str = REPO_ROOT) -> list[dict[str, Any]]:
    """Discover all available WSJ issue directories containing `final.json`."""
    issues: list[dict[str, Any]] = []
    if not os.path.isdir(repo_root):
        return issues
    for name in sorted(os.listdir(repo_root), reverse=True):
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", name):
            continue
        idir = os.path.join(repo_root, name)
        final_p = os.path.join(idir, "final.json")
        if not os.path.isfile(final_p):
            continue
        front_p = os.path.join(idir, "front.json")
        front = {}
        if os.path.isfile(front_p):
            try:
                with open(front_p, encoding="utf-8") as f:
                    front = json.load(f)
            except Exception:
                pass
        store = ArtifactStore(idir)
        art_count = len(store.list_articles())
        issues.append({
            "issue": name,
            "date_cn": front.get("date_cn") or name,
            "date_en": front.get("date_en") or name,
            "dek_cn": front.get("dek_cn") or "",
            "lead_id": front.get("lead_id") or "",
            "generated_count": art_count,
        })
    return issues


def evaluate_article_curation(
    entry: dict[str, Any],
    *,
    front: dict[str, Any] | None = None,
    curation: dict[str, Any] | None = None,
    has_editorial_plan: bool = False,
) -> dict[str, Any]:
    """Evaluate an article's Content Gate, Curation Tier, Recommendation Flag, and Reason."""
    front = front or {}
    curation = curation or {}
    excluded_map = curation.get("exclude") or {}
    data_treat_map = curation.get("data_treatment") or {}

    aid = entry["id"]
    atype = (entry.get("type") or "article").lower()
    page = entry.get("page") or ""
    section = entry.get("section") or ""
    priority = entry.get("priority") or "P3"
    paras_cn = [p.strip() for p in (entry.get("body_cn") or "").split("\n\n") if p.strip()]
    paras_en = [p.strip() for p in (entry.get("body_en") or "").split("\n\n") if p.strip()]
    n_cn = len(paras_cn)
    n_en = len(paras_en)

    passed, gate_issues = check_article(entry)
    gate_status = "pass" if passed and not gate_issues else ("warn" if passed else "block")

    # Classify WARN risks for user confirmation
    warn_risks: list[dict[str, str]] = []
    requires_warn_confirmation = False
    if gate_status == "warn":
        requires_warn_confirmation = True
        for iss in gate_issues:
            code = iss.get("code", "warn")
            detail = iss.get("detail", "")
            risk_desc = detail
            if code == "para_misaligned":
                risk_desc = f"中英段落数量存在差异 ({detail})：生成时将回退为整段原子锚点以防尾部截断，需确认双语对齐。"
            elif code == "turn_to_unconfirmed":
                risk_desc = f"跨页跳转标记待确认 ({detail})：需确认续文是否已完整合并。"
            elif code == "too_few_paras":
                risk_desc = f"段落较少 ({detail})：请确认原文是否为短稿且未截断。"
            warn_risks.append({"code": code, "detail": detail, "risk_explanation": risk_desc})

    # 1. Blocked or Excluded or Non-narrative items
    if gate_status == "block":
        return {
            "recommended": False,
            "tier": "blocked",
            "tier_label": "门禁拦截 (BLOCK)",
            "reason": "未通过 Content Integrity Gate：" + "; ".join(i.get("detail", "") for i in gate_issues),
            "suggested_treatment": "blocked",
            "can_enqueue": False,
            "requires_warn_confirmation": False,
            "warn_risks": [],
        }

    if aid in excluded_map:
        return {
            "recommended": False,
            "tier": "excluded",
            "tier_label": "策展排除 (Excluded)",
            "reason": f"已由 curation.json 排除：{excluded_map[aid]}",
            "suggested_treatment": "none",
            "can_enqueue": False,
            "requires_warn_confirmation": False,
            "warn_risks": [],
        }

    if n_cn == 0 or atype in ("index_digest", "photo_caption", "correction", "data_table"):
        reason_txt = (
            f"已配置数据摘要处理 ({data_treat_map[aid].get('suppress_body', '数据表')})"
            if aid in data_treat_map
            else f"印刷版非叙事条目 ({atype})，无需整篇 Generative Editorial 构图"
        )
        return {
            "recommended": False,
            "tier": "non_narrative",
            "tier_label": f"非叙事条目 ({atype})",
            "reason": reason_txt,
            "suggested_treatment": "none",
            "can_enqueue": False,
            "requires_warn_confirmation": False,
            "warn_risks": [],
        }

    # 2. Front-Page Lead / Also-Reads / Flagship A1 Stories
    lead_id = front.get("lead_id")
    also_ids = set(front.get("also_ids") or [])
    if aid == lead_id or aid in also_ids or page == "A1":
        role_tag = "本期头版主稿 (Lead)" if aid == lead_id else ("头版重点推荐 (Also Read)" if aid in also_ids else "A1 头版深度报道")
        return {
            "recommended": True,
            "tier": "recommended_lead",
            "tier_label": "★ 强烈推荐 · 头版重磅",
            "reason": f"{role_tag}（{n_cn} 段双语正文）——叙事层次丰富，适合完整章节构图、证据边栏与定制 SVG 图解。",
            "suggested_treatment": "full_editorial_composition",
            "can_enqueue": True,
            "requires_warn_confirmation": requires_warn_confirmation,
            "warn_risks": warn_risks,
        }

    # 3. Curated Editorial Plans or P1 / Long-Form Feature / Analysis / Opinion (>= 7 paragraphs)
    if has_editorial_plan or priority == "P1" or (atype in ("article", "opinion") and n_cn >= 7 and priority in ("P1", "P2")):
        genre_label = "深度评论/随笔" if atype == "opinion" else f"{section} 深度分析/特稿"
        return {
            "recommended": True,
            "tier": "recommended_feature",
            "tier_label": "✦ 推荐生成 · 深度长文",
            "reason": f"{priority} 级 {genre_label}（{n_cn} 段）——论证或叙事结构完整，适合针对性视觉层级与关键关系图解。",
            "suggested_treatment": "genre_conditioned_composition",
            "can_enqueue": True,
            "requires_warn_confirmation": requires_warn_confirmation,
            "warn_risks": warn_risks,
        }

    # 4. Shorter Articles, Briefs, Letters (1..6 paragraphs or P3)
    return {
        "recommended": False,
        "tier": "optional_brief",
        "tier_label": "可选生成 · 简讯/短稿",
        "reason": f"{atype} 短篇报道（{n_cn} 段）——建议保持克制紧凑版式，无需复杂多栏或冗余图表（可按需手动勾选）。",
        "suggested_treatment": "restrained_compact",
        "can_enqueue": True,
        "requires_warn_confirmation": requires_warn_confirmation,
        "warn_risks": warn_risks,
    }


class PersistentGenerationQueue:
    """Disk-backed, thread-safe serial batch generation queue with crash/restart recovery."""

    def __init__(
        self,
        issue_dir: str,
        *,
        provider_override: ModelProvider | None = None,
        auto_start_worker: bool = True,
    ):
        self.issue_dir = os.path.abspath(issue_dir)
        self.issue_date = os.path.basename(self.issue_dir)
        self.artifacts_root = os.path.join(self.issue_dir, "editorial-artifacts")
        os.makedirs(self.artifacts_root, exist_ok=True)
        self.queue_path = os.path.join(self.artifacts_root, "_queue.json")
        self.provider_override = provider_override
        self._lock = threading.RLock()
        self._worker_thread: threading.Thread | None = None
        self._stop_event = threading.Event()

        self._state = self._load_from_disk()
        self.recover_on_startup()
        if auto_start_worker and self.has_pending_tasks():
            self.ensure_worker_running()

    def _load_from_disk(self) -> dict[str, Any]:
        if os.path.isfile(self.queue_path):
            try:
                with open(self.queue_path, encoding="utf-8") as f:
                    data = json.load(f)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid persistent queue: {self.queue_path}") from exc
            if not isinstance(data, dict) or not isinstance(data.get("tasks"), list):
                raise ValueError(f"Invalid persistent queue: {self.queue_path}; expected a tasks list")
            return data
        return {
            "schema_version": "editorial-queue-v1",
            "issue_date": self.issue_date,
            "updated_at": _utc_now(),
            "tasks": [],
        }

    def _save_to_disk(self) -> None:
        with self._lock:
            self._state["updated_at"] = _utc_now()
            tmp_path = f"{self.queue_path}.tmp.{os.getpid()}.{threading.get_ident()}"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(self._state, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, self.queue_path)

    def recover_on_startup(self) -> list[dict[str, Any]]:
        """Inspect tasks left in `running` state when the Studio process previously exited."""
        recovered: list[dict[str, Any]] = []
        store = ArtifactStore(self.issue_dir)
        with self._lock:
            dirty = False
            for task in self._state["tasks"]:
                if task.get("status") != "running":
                    continue
                aid = task["article_id"]
                active = store.get_active_artifact(aid)
                # Check if an artifact was created after the task started
                if active and active.get("created_at", "") >= (task.get("started_at") or ""):
                    task["status"] = "completed"
                    task["stage"] = "completed"
                    task["artifact_version"] = active["artifact_version"]
                    task["finished_at"] = _utc_now()
                    task["detail"] = f"进程重启后恢复确认：制品 {active['artifact_version']} 已完整保存。"
                    task["recovered_from_restart"] = True
                    recovered.append(dict(task))
                    dirty = True
                else:
                    # Re-queue interrupted running task as pending so it resumes cleanly
                    task["status"] = "pending"
                    task["stage"] = "recovered_pending"
                    task["detail"] = "上次进程退出时任务未完成，已自动恢复至待执行队列 (Recovered -> Pending)。"
                    task["recovered_from_restart"] = True
                    recovered.append(dict(task))
                    dirty = True
            if dirty:
                self._save_to_disk()
        return recovered

    def has_pending_tasks(self) -> bool:
        with self._lock:
            return any(t.get("status") == "pending" for t in self._state["tasks"])

    def enqueue_articles(
        self,
        *,
        article_ids: list[str],
        provider_name: str = "magpie",
        model_id: str = DEFAULT_EDITORIAL_MODEL_ID,
        temperature: float = 0.2,
        custom_instructions: str = "",
        confirm_warn: bool = False,
        force_new: bool = False,
        start_worker: bool = True,
    ) -> dict[str, Any]:
        """Enqueue one or more articles with deduplication and Content Gate enforcement."""
        enqueued: list[dict[str, Any]] = []
        deduplicated: list[dict[str, Any]] = []
        rejected: list[dict[str, Any]] = []

        final_path = os.path.join(self.issue_dir, "final.json")
        with open(final_path, encoding="utf-8") as f:
            final_by_id = {e["id"]: e for e in json.load(f)}

        curation_path = os.path.join(BASE, "curation.json")
        curation = {}
        if os.path.isfile(curation_path):
            with open(curation_path, encoding="utf-8") as f:
                curation = json.load(f)
        with self._lock:
            for raw_aid in article_ids:
                aid = (raw_aid or "").strip()
                if not aid or aid not in final_by_id:
                    rejected.append({"article_id": aid, "reason": f"未找到文章 {aid}"})
                    continue

                entry = final_by_id[aid]
                cur_eval = evaluate_article_curation(entry, curation=curation)
                if not cur_eval["can_enqueue"]:
                    rejected.append({"article_id": aid, "reason": cur_eval["reason"]})
                    continue

                if cur_eval["requires_warn_confirmation"] and not confirm_warn:
                    rejected.append({
                        "article_id": aid,
                        "code": "warn_confirmation_required",
                        "reason": "该文章处于 WARN 状态，需确认双语段落/跨页风险后方可入队。",
                        "warn_risks": cur_eval["warn_risks"],
                    })
                    continue

                digest = content_digest(entry)

                # Deduplication check: if an identical (article_id, model_id, content_digest) is already pending or running
                existing_active = next(
                    (
                        t
                        for t in reversed(self._state["tasks"])
                        if t["article_id"] == aid
                        and t["status"] in ("pending", "running")
                        and t.get("model_id") == model_id
                        and t.get("content_digest") == digest
                    ),
                    None,
                )
                if existing_active and not force_new:
                    deduplicated.append(dict(existing_active))
                    continue

                # Add tailored brief instruction if article is a short brief and user didn't override
                effective_instructions = custom_instructions
                if not effective_instructions and cur_eval["suggested_treatment"] == "restrained_compact":
                    effective_instructions = (
                        "This is a short WSJ news dispatch/brief. Use a restrained, high-craft compact editorial layout "
                        "without inventing unnecessary multi-act headers or artificial charts."
                    )

                now_ts = _utc_now()
                task_id = f"task-{uuid.uuid4().hex[:8]}"
                task_rec = {
                    "task_id": task_id,
                    "issue": self.issue_date,
                    "article_id": aid,
                    "title_cn": entry.get("title_cn") or "",
                    "title_en": entry.get("title") or "",
                    "provider": provider_name,
                    "model_id": model_id,
                    "temperature": temperature,
                    "content_digest": digest,
                    "custom_instructions": effective_instructions,
                    "confirm_warn": confirm_warn,
                    "status": "pending",
                    "stage": "pending",
                    "detail": f"排队等待执行 ({model_id})…",
                    "created_at": now_ts,
                    "started_at": None,
                    "finished_at": None,
                    "updated_at": now_ts,
                    "artifact_version": None,
                    "error": None,
                    "audit_summary": None,
                    "recovered_from_restart": False,
                }
                self._state["tasks"].append(task_rec)
                enqueued.append(dict(task_rec))

            if enqueued:
                self._save_to_disk()

        if start_worker and (enqueued or self.has_pending_tasks()):
            self.ensure_worker_running()

        return {
            "enqueued": enqueued,
            "deduplicated": deduplicated,
            "rejected": rejected,
            "queue_summary": self.get_summary(),
        }

    def cancel_task(self, task_id: str) -> dict[str, Any]:
        """Cancel a pending task (or mark a running task for cancellation)."""
        with self._lock:
            task = next((t for t in self._state["tasks"] if t["task_id"] == task_id), None)
            if not task:
                raise KeyError(f"Task '{task_id}' not found")
            if task["status"] == "pending":
                task["status"] = "cancelled"
                task["stage"] = "cancelled"
                task["finished_at"] = _utc_now()
                task["detail"] = "已由用户取消 (Cancelled)"
                self._save_to_disk()
            elif task["status"] == "running":
                task["cancel_requested"] = True
                task["detail"] = "正在取消当前任务…"
                self._save_to_disk()
            return dict(task)

    def retry_task(self, task_id: str, *, start_worker: bool = True) -> dict[str, Any]:
        """Create a fresh pending retry task from a failed or cancelled task."""
        with self._lock:
            old_task = next((t for t in self._state["tasks"] if t["task_id"] == task_id), None)
            if not old_task:
                raise KeyError(f"Task '{task_id}' not found")
            aid = old_task["article_id"]
            prov = old_task.get("provider") or "magpie"
            mid = old_task.get("model_id") or DEFAULT_EDITORIAL_MODEL_ID
            instr = old_task.get("custom_instructions") or ""
            c_warn = bool(old_task.get("confirm_warn", True))

        return self.enqueue_articles(
            article_ids=[aid],
            provider_name=prov,
            model_id=mid,
            custom_instructions=instr,
            confirm_warn=c_warn,
            force_new=True,
            start_worker=start_worker,
        )

    def ensure_worker_running(self) -> None:
        with self._lock:
            if self._worker_thread and self._worker_thread.is_alive():
                return
            self._stop_event.clear()
            self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
            self._worker_thread.start()

    def run_all_pending_sync(self, on_task_complete: Callable[[dict[str, Any]], None] | None = None) -> list[dict[str, Any]]:
        """Execute all currently pending tasks synchronously in serial order (useful for CLI & deterministic tests)."""
        processed: list[dict[str, Any]] = []
        while True:
            task = self._claim_next_pending()
            if not task:
                break
            finished_task = self._execute_single_task(task)
            processed.append(finished_task)
            if on_task_complete:
                on_task_complete(finished_task)
        return processed

    def _claim_next_pending(self) -> dict[str, Any] | None:
        with self._lock:
            for t in self._state["tasks"]:
                if t.get("status") == "pending":
                    now_ts = _utc_now()
                    t["status"] = "running"
                    t["stage"] = "starting"
                    t["started_at"] = now_ts
                    t["updated_at"] = now_ts
                    t["detail"] = f"正在启动生成 ({t.get('model_id')})…"
                    self._save_to_disk()
                    return t
        return None

    def _execute_single_task(self, task: dict[str, Any]) -> dict[str, Any]:
        task_id = task["task_id"]
        aid = task["article_id"]
        provider_name = task.get("provider") or "magpie"
        model_id = task.get("model_id") or DEFAULT_EDITORIAL_MODEL_ID
        temperature = float(task.get("temperature") or 0.2)
        custom_instructions = task.get("custom_instructions") or ""

        def _progress(stage: str, detail: str) -> None:
            with self._lock:
                t_ref = next((x for x in self._state["tasks"] if x["task_id"] == task_id), None)
                if t_ref:
                    t_ref["stage"] = stage
                    t_ref["detail"] = detail
                    t_ref["updated_at"] = _utc_now()
                    self._save_to_disk()

        try:
            prov, cfg = create_provider_for_model(
                provider_name=provider_name,
                model_id=model_id,
                temperature=temperature,
            )
            active_provider = self.provider_override or prov
            rec = publish_article(
                issue_dir=self.issue_dir,
                article_id=aid,
                provider=active_provider,
                config=cfg,
                max_retries=1,
                custom_instructions=custom_instructions,
                notes=f"Queue task {task_id} ({model_id})",
                progress_callback=_progress,
            )
            si = rec["validation"]["compiler_audit"]["source_integrity"]
            with self._lock:
                t_ref = next((x for x in self._state["tasks"] if x["task_id"] == task_id), None)
                if t_ref:
                    if t_ref.get("cancel_requested"):
                        t_ref["status"] = "cancelled"
                        t_ref["stage"] = "cancelled"
                        t_ref["finished_at"] = _utc_now()
                        t_ref["detail"] = "任务在完成前被取消。"
                    else:
                        t_ref["status"] = "completed"
                        t_ref["stage"] = "completed"
                        t_ref["artifact_version"] = rec["artifact_version"]
                        t_ref["finished_at"] = _utc_now()
                        t_ref["detail"] = (
                            f"已完成 {rec['artifact_version']} — 原文逐字核验 CN {si['exact_match_cn']}, EN {si['exact_match_en']}"
                        )
                        t_ref["audit_summary"] = {
                            "exact_match_cn": si["exact_match_cn"],
                            "exact_match_en": si["exact_match_en"],
                            "content_digest": si["content_digest"],
                        }
                    self._save_to_disk()
                    return dict(t_ref)
        except Exception as e:
            with self._lock:
                t_ref = next((x for x in self._state["tasks"] if x["task_id"] == task_id), None)
                if t_ref:
                    t_ref["status"] = "failed"
                    t_ref["stage"] = "failed"
                    t_ref["error"] = str(e)
                    t_ref["finished_at"] = _utc_now()
                    t_ref["detail"] = f"生成失败 (已隔离，不影响其他任务与历史制品): {str(e)[:180]}"
                    self._save_to_disk()
                    return dict(t_ref)
        return dict(task)

    def _worker_loop(self) -> None:
        while not self._stop_event.is_set():
            task = self._claim_next_pending()
            if not task:
                break
            self._execute_single_task(task)
            # Also refresh the static reader snapshot on disk after each completed task
            try:
                from editorial_studio import build_editorial_reader_html
                build_editorial_reader_html(self.issue_dir)
            except Exception:
                pass

    def get_summary(self) -> dict[str, Any]:
        with self._lock:
            tasks = [dict(t) for t in self._state["tasks"]]
        counts = {"pending": 0, "running": 0, "completed": 0, "failed": 0, "cancelled": 0}
        for t in tasks:
            st = t.get("status", "pending")
            counts[st] = counts.get(st, 0) + 1
        return {
            "issue_date": self.issue_date,
            "total_tasks": len(tasks),
            "counts": counts,
            "tasks": list(reversed(tasks)),  # Newest first for UI display
        }

    def latest_task_by_article(self) -> dict[str, dict[str, Any]]:
        with self._lock:
            out: dict[str, dict[str, Any]] = {}
            for t in self._state["tasks"]:
                out[t["article_id"]] = dict(t)
            return out
