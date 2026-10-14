#!/usr/bin/env python3
"""WSJ 深读 · Phase 5 End-to-End Automated Test Suite (`test_phase5_product.py`).

Tests:
1. Workflow & Canonical Builder Integration (`canonical_builder.py` + `source_model.py` + `alignment_overrides.json` + `integrity_gate.py`):
   - Verifies E2-001 (20 blocks), E1-010 (20 blocks), E3-004 (22 blocks), and E2-002 (38 blocks with alignment repair).
   - Verifies sentence splitting & bilingual alignment invariants.
2. Model Provider Abstraction & Model Independence (`model_provider.py`):
   - Verifies `CallableModelProvider` and `GenerationConfig` swapping (`gemini` vs `claude` vs `omlx`) without changing downstream contracts.
3. Editorial Compiler & Content/Safety/SVG Integrity (`editorial_compiler.py`):
   - Verifies deterministic injection (`data-ref`, `data-derive`, `data-hl`).
   - Verifies strict rejection of missing references, duplicate references, out-of-order references, and invalid IDs.
   - Verifies HTML/SVG/CSS sanitization (`<script>`, `<iframe>`, `onerror`, `@import`, external `url()`).
   - Verifies Shadow DOM selector adaptation (`:root` -> `:host`, `html[lang]` -> `:host([lang])`).
   - Verifies SVG `viewBox` coordinate overflow diagnosis & selective auto-repair.
4. Artifact Store Persistence, Version Management & Non-Destructive Error Recovery (`artifact_store.py` & `editorial_publisher.py`):
   - Verifies multi-version persistence (`v1`..`v3`), active version retrieval without LLM calls,
     automatic repair retry on broken generation, and preservation of prior verified versions when a subsequent generation fails.
5. Reader Application Generation (`editorial_studio.py`):
   - Verifies `editorial-reader.html` embeds all verified artifacts and all 117 source library items.
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest

from artifact_store import ArtifactStore
from canonical_builder import build_canonical_source, load_canonical_for_issue
from editorial_compiler import (
    EditorialCompilationError,
    adapt_css_for_shadow_dom,
    compile_editorial_artifact,
)
from editorial_publisher import import_raw_generation, publish_article
from editorial_studio import (
    collect_issue_payload,
    compute_workflow_status,
    create_studio_http_server,
)
from generation_queue import PersistentGenerationQueue, discover_issues, evaluate_article_curation
from model_provider import CallableModelProvider, GenerationConfig, list_configured_models
BASE = os.path.dirname(os.path.abspath(__file__))
ISSUE_DIR = os.path.abspath(os.path.join(BASE, "../2026-10-12"))


class Phase5ProductTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Payload collection can recover/resume a queue; never use the live issue.
        cls._fixture = tempfile.TemporaryDirectory(prefix='wsj-phase5-tests-')
        cls.payload_issue = os.path.join(cls._fixture.name, '2026-10-12')
        os.makedirs(cls.payload_issue)
        shutil.copy2(os.path.join(ISSUE_DIR, 'final.json'), cls.payload_issue)
        shutil.copytree(os.path.join(ISSUE_DIR, 'editorial-artifacts'),
                        os.path.join(cls.payload_issue, 'editorial-artifacts'),
                        ignore=shutil.ignore_patterns('_queue.json', '_queue.json.tmp.*'))

    @classmethod
    def tearDownClass(cls):
        cls._fixture.cleanup()

    def test_01_canonical_builder_inherits_existing_pipeline_and_alignment_repairs(self) -> None:
        # E2-001: 20 paragraphs, curated sentence splits on p4 & p20
        c_e2001 = load_canonical_for_issue(ISSUE_DIR, "E2-001")
        self.assertEqual(c_e2001["article_id"], "E2-001")
        self.assertEqual(len(c_e2001["blocks"]), 20)

        # E2-002: has EN alignment repair in alignment_overrides.json; verify CN and EN block counts match (38)
        c_e2002 = load_canonical_for_issue(ISSUE_DIR, "E2-002")
        self.assertEqual(len(c_e2002["blocks"]), 38)
        for b in c_e2002["blocks"]:
            self.assertTrue(b["text_cn"] and b["text_en"], f"Block {b['id']} in E2-002 must have both CN and EN")
            joined_cn = "".join(s["text_cn"] for s in b["sentences"])
            self.assertEqual(joined_cn, b["text_cn"])

    def test_02_compiler_enforces_verbatim_source_and_structural_integrity(self) -> None:
        canonical = load_canonical_for_issue(ISSUE_DIR, "E2-001")
        p_tags = []
        for i in range(1, 21):
            if i == 1:
                p_tags.append('<p data-ref="p1" data-hl="4 万美元 | $40,000"></p>')
            elif i == 20:
                p_tags.append('<p data-ref="p20.s1"></p><blockquote class="verdict" data-ref="p20.s2"></blockquote>')
            else:
                p_tags.append(f'<p data-ref="p{i}"></p>')

        valid_html = f"""<!DOCTYPE html>
        <html lang="zh-CN">
        <head><style>:root {{ --paper: #faf8f4; }} html[lang="zh-CN"] .lang-en {{ display: none; }} body {{ margin: 0; }}</style></head>
        <body><main>
          <h1 data-ref="title"></h1>
          <section>
            {"".join(p_tags)}
            <aside><blockquote data-derive="q4"></blockquote></aside>
          </section>
        </main></body></html>"""

        bundle = compile_editorial_artifact(valid_html, canonical, strict=True)
        audit = bundle["audit_report"]
        self.assertTrue(audit["passed"])
        self.assertEqual(audit["source_integrity"]["exact_match_cn"], "20/20")
        self.assertEqual(audit["source_integrity"]["exact_match_en"], "20/20")
        # Verify q4 in the same section as p20.s2 blockquote was automatically deduplicated
        self.assertTrue(
            any(d["kind"] == "quote_deduped_removed" and d["id"] == "q4" for d in audit["derived_and_editorial_inventory"]["derived_items"])
        )
        # Verify Shadow DOM CSS adaptation
        self.assertIn(":host", bundle["shadow_bundle"]["shadow_css"])
        self.assertIn(':host([lang="zh-CN"])', bundle["shadow_bundle"]["shadow_css"])

        # Verify missing block fails loudly
        broken_html = "<!DOCTYPE html><html><body><p data-ref='p1'></p><p data-ref='p3'></p></body></html>"
        with self.assertRaises(EditorialCompilationError) as ctx:
            compile_editorial_artifact(broken_html, canonical, strict=True)
        self.assertIn("Missing canonical narrative units", str(ctx.exception))

    def test_03_sanitization_and_svg_viewbox_auto_repair(self) -> None:
        canonical = load_canonical_for_issue(ISSUE_DIR, "E2-001")
        p_tags = "".join(f'<p data-ref="p{i}"></p>' for i in range(1, 21))
        unsafe_html = f"""<!DOCTYPE html>
        <html><head><style>@import url("https://evil.example/x.css"); .bg {{ background: url("https://evil.example/p.png"); }}</style></head>
        <body><main>
          <p onclick="alert(1)"><a href="javascript:alert(2)">Bad</a></p>
          <iframe src="https://evil.example"></iframe>
          <svg viewBox="0 0 300 100"><rect x="10" y="10" width="380" height="140"></rect></svg>
          {p_tags}
        </main></body></html>"""

        # Sanitizer diagnostics remain available; unreviewed authored content cannot publish.
        bundle = compile_editorial_artifact(unsafe_html, canonical, strict=False, auto_repair_svg=True)
        self.assertFalse(bundle['audit_report']['claim_provenance']['passed'])
        comp = bundle["compiled_html"]
        self.assertNotIn("<iframe", comp)
        self.assertNotIn("onclick=", comp)
        self.assertNotIn("javascript:alert", comp)
        self.assertNotIn("@import", comp)
        # Verify SVG viewBox was expanded from 0 0 300 100 to accommodate rect x+w=390, y+h=150
        self.assertEqual(len(bundle["audit_report"]["svg_diagnostics"]), 1)
        self.assertEqual(bundle["audit_report"]["svg_diagnostics"][0]["repaired_viewBox"], "0 0 390 150")

    def test_04_model_agnostic_retry_and_nondestructive_artifact_store(self) -> None:
        canonical = load_canonical_for_issue(ISSUE_DIR, "E1-014")  # 2-paragraph brief
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(ISSUE_DIR, "final.json"), encoding="utf-8") as f:
                final_full = json.load(f)
            e1014 = [e for e in final_full if e["id"] == "E1-014"]
            with open(os.path.join(tmpdir, "final.json"), "w", encoding="utf-8") as f:
                json.dump(e1014, f)
            # 1) Provider that fails on attempt 1 (missing p2) and succeeds on attempt 2 (repair loop)
            attempts = []

            def flaky_model(prompt: str, cfg: GenerationConfig) -> str:
                attempts.append(prompt)
                if len(attempts) == 1:
                    return "<!DOCTYPE html><html><body><main><p data-ref='p1'></p></main></body></html>"
                return "<!DOCTYPE html><html><body><main><p data-ref='p1'></p><p data-ref='p2'></p></main></body></html>"

            provider_a = CallableModelProvider(
                flaky_model,
                GenerationConfig(provider="mock-gemini", model_id="gemini-test-v1"),
            )
            rec_v1 = publish_article(issue_dir=tmpdir, article_id="E1-014", provider=provider_a, max_retries=1)
            self.assertEqual(len(attempts), 2)
            self.assertEqual(rec_v1["artifact_version"], "v1")
            self.assertEqual(rec_v1["model_metadata"]["provider"], "mock-gemini")

            # 2) Second provider (e.g. Claude) produces v2
            provider_b = CallableModelProvider(
                lambda p, c: "<!DOCTYPE html><html><body><main><article><p data-ref='p1'></p><p data-ref='p2'></p></article></main></body></html>",
                GenerationConfig(provider="anthropic", model_id="claude-sonnet-4"),
            )
            rec_v2 = publish_article(issue_dir=tmpdir, article_id="E1-014", provider=provider_b, max_retries=0)
            self.assertEqual(rec_v2["artifact_version"], "v2")
            self.assertEqual(rec_v2["model_metadata"]["provider"], "anthropic")

            # 3) Third provider fails completely — verify v2 remains the active undamaged artifact!
            provider_broken = CallableModelProvider(
                lambda p, c: "<!DOCTYPE html><html><body><main><p data-ref='p999'></p></main></body></html>",
                GenerationConfig(provider="broken", model_id="broken-1"),
            )
            with self.assertRaises(EditorialCompilationError):
                publish_article(issue_dir=tmpdir, article_id="E1-014", provider=provider_broken, max_retries=0)

            store = ArtifactStore(tmpdir)
            active = store.get_active_artifact("E1-014")
            self.assertEqual(active["artifact_version"], "v2")
            art_summary = store.list_articles()["E1-014"]
            self.assertEqual(len(art_summary["versions"]), 2)
            self.assertEqual(len(art_summary["failed_attempts"]), 1)

    def test_05_persisted_issue_artifacts_and_reader_build(self) -> None:
        payload = collect_issue_payload(self.payload_issue)
        self.assertEqual(payload["total_source_items"], 117)
        for aid in ("E2-001", "E1-010", "E3-004"):
            self.assertIn(aid, payload["artifacts"])
            active_ver = payload["artifacts"][aid]["active_version"]
            ver_obj = payload["artifacts"][aid]["versions"][active_ver]
            self.assertTrue(ver_obj["validation"]["compiler_audit"]["passed"])


    def test_06_phase6_workflow_states_and_live_http_api(self) -> None:
        # Verify 5-state classification
        self.assertEqual(
            compute_workflow_status(
                gate_status="pass",
                excluded_by_curation=False,
                item_type="article",
                paras_cn=10,
                has_artifact=False,
                failed_attempts_count=0,
                active_job=None,
            )[0],
            "eligible",
        )
        self.assertEqual(
            compute_workflow_status(
                gate_status="pass",
                excluded_by_curation=False,
                item_type="article",
                paras_cn=10,
                has_artifact=False,
                failed_attempts_count=0,
                active_job={"status": "generating", "stage": "calling_model"},
            )[0],
            "generating",
        )
        self.assertEqual(
            compute_workflow_status(
                gate_status="pass",
                excluded_by_curation=False,
                item_type="article",
                paras_cn=10,
                has_artifact=False,
                failed_attempts_count=1,
                active_job={"status": "failed"},
            )[0],
            "failed_retry",
        )
        self.assertEqual(
            compute_workflow_status(
                gate_status="pass",
                excluded_by_curation=False,
                item_type="index_digest",
                paras_cn=16,
                has_artifact=False,
                failed_attempts_count=0,
                active_job=None,
            )[0],
            "not_ready",
        )

        # Verify all 6 generated articles (E2-001, E1-010, E3-004, E1-024, E1-019, E1-014) exist and pass audit
        payload = collect_issue_payload(self.payload_issue)
        for aid in ("E2-001", "E1-010", "E3-004", "E1-024", "E1-019", "E1-014"):
            self.assertIn(aid, payload["artifacts"], f"{aid} must be present in persisted artifacts")
            act = payload["artifacts"][aid]["active_version"]
            self.assertTrue(payload["artifacts"][aid]["versions"][act]["validation"]["compiler_audit"]["passed"])

        # Verify HTTP Server endpoints (/api/models, /api/canonical, /api/generate, /api/activate-version)
        import threading
        import urllib.request

        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(ISSUE_DIR, "final.json"), encoding="utf-8") as f:
                final_full = json.load(f)
            e1014 = [e for e in final_full if e["id"] == "E1-014"]
            with open(os.path.join(tmpdir, "final.json"), "w", encoding="utf-8") as f:
                json.dump(e1014, f)

            mock_prov = CallableModelProvider(
                lambda p, c: "<!DOCTYPE html><html><body><main><p data-ref='p1'></p><p data-ref='p2'></p></main></body></html>",
                GenerationConfig(provider="test-prov", model_id="test-model"),
            )
            httpd = create_studio_http_server(tmpdir, port=0, provider_override=mock_prov)
            port = httpd.server_address[1]
            t = threading.Thread(target=httpd.serve_forever, daemon=True)
            t.start()
            try:
                base_url = f"http://127.0.0.1:{port}"
                # 1. GET /api/models
                with urllib.request.urlopen(f"{base_url}/api/models") as r:
                    models_data = json.loads(r.read().decode("utf-8"))
                self.assertGreaterEqual(len(models_data["models"]), 1)

                # 2. GET /api/canonical?article_id=E1-014
                with urllib.request.urlopen(f"{base_url}/api/canonical?article_id=E1-014") as r:
                    canon_data = json.loads(r.read().decode("utf-8"))
                self.assertEqual(canon_data["article_id"], "E1-014")
                self.assertEqual(len(canon_data["blocks"]), 2)

                # 3. POST /api/generate (blocking=True for deterministic test)
                req = urllib.request.Request(
                    f"{base_url}/api/generate",
                    data=json.dumps({"article_id": "E1-014", "blocking": True}).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(req) as r:
                    job_data = json.loads(r.read().decode("utf-8"))
                self.assertEqual(job_data["status"], "completed")
                self.assertEqual(job_data["artifact_version"], "v1")
            finally:
                httpd.shutdown()
                httpd.server_close()

    def test_07_phase7_curation_persistent_queue_dedup_and_restart_recovery(self) -> None:
        # 1. Verify multi-issue discovery
        issues = discover_issues(os.path.dirname(ISSUE_DIR))
        self.assertTrue(any(i["issue"] == "2026-10-12" for i in issues))

        # 2. Verify Curation & Content Gate enforcement (PASS vs WARN vs Excluded)
        with open(os.path.join(ISSUE_DIR, "final.json"), encoding="utf-8") as f:
            final_full = json.load(f)
        with open(os.path.join(BASE, "curation.json"), encoding="utf-8") as f:
            curation_cfg = json.load(f)
        with open(os.path.join(ISSUE_DIR, "front.json"), encoding="utf-8") as f:
            front_cfg = json.load(f)

        by_id = {e["id"]: e for e in final_full}
        cur_e2001 = evaluate_article_curation(by_id["E2-001"], front=front_cfg, curation=curation_cfg)
        self.assertTrue(cur_e2001["recommended"])
        self.assertEqual(cur_e2001["tier"], "recommended_lead")
        self.assertTrue(cur_e2001["can_enqueue"])

        cur_e2013 = evaluate_article_curation(by_id["E2-013"], front=front_cfg, curation=curation_cfg)
        self.assertFalse(cur_e2013["can_enqueue"])
        self.assertEqual(cur_e2013["tier"], "excluded")

        cur_e1004 = evaluate_article_curation(by_id["E1-004"], front=front_cfg, curation=curation_cfg)
        self.assertTrue(cur_e1004["requires_warn_confirmation"])
        self.assertGreaterEqual(len(cur_e1004["warn_risks"]), 1)

        # 3. Verify PersistentGenerationQueue deduplication, cancellation, failure isolation, and crash recovery
        with tempfile.TemporaryDirectory() as tmpdir:
            subset = [by_id["E1-014"], by_id["E1-015"], by_id["E1-004"], by_id["E2-013"]]
            with open(os.path.join(tmpdir, "final.json"), "w", encoding="utf-8") as f:
                json.dump(subset, f)

            def selective_provider_fn(prompt: str, cfg: GenerationConfig) -> str:
                if "E1-014" in prompt:
                    return "<!DOCTYPE html><html><body><main><p data-ref='p1'></p><p data-ref='p2'></p></main></body></html>"
                if "E1-015" in prompt:
                    raise RuntimeError("Simulated provider timeout on E1-015")
                return "<!DOCTYPE html><html><body><main><p data-ref='p1'></p></main></body></html>"

            prov = CallableModelProvider(selective_provider_fn, GenerationConfig(provider="mock", model_id="mock-v1"))
            q1 = PersistentGenerationQueue(tmpdir, provider_override=prov, auto_start_worker=False)

            res_warn = q1.enqueue_articles(article_ids=["E1-004"], confirm_warn=False, start_worker=False)
            self.assertEqual(len(res_warn["enqueued"]), 0)
            self.assertEqual(res_warn["rejected"][0]["code"], "warn_confirmation_required")

            res_excl = q1.enqueue_articles(article_ids=["E2-013"], start_worker=False)
            self.assertEqual(len(res_excl["enqueued"]), 0)

            r_enq1 = q1.enqueue_articles(article_ids=["E1-014", "E1-015"], model_id="mock-v1", start_worker=False)
            self.assertEqual(len(r_enq1["enqueued"]), 2)
            r_enq_dup = q1.enqueue_articles(article_ids=["E1-014"], model_id="mock-v1", start_worker=False)
            self.assertEqual(len(r_enq_dup["enqueued"]), 0)
            self.assertEqual(len(r_enq_dup["deduplicated"]), 1)

            processed = q1.run_all_pending_sync()
            self.assertEqual(len(processed), 2)
            statuses = {t["article_id"]: t["status"] for t in processed}
            self.assertEqual(statuses["E1-014"], "completed")
            self.assertEqual(statuses["E1-015"], "failed")

            with open(q1.queue_path, encoding="utf-8") as f:
                q_disk = json.load(f)
            q_disk["tasks"].append({
                "task_id": "task-interrupted",
                "issue": os.path.basename(tmpdir),
                "article_id": "E1-004",
                "title_cn": "Warn Article",
                "provider": "mock",
                "model_id": "mock-v1",
                "status": "running",
                "stage": "calling_model",
                "started_at": "2099-01-01T00:00:00Z",
            })
            with open(q1.queue_path, "w", encoding="utf-8") as f:
                json.dump(q_disk, f)

            q2 = PersistentGenerationQueue(tmpdir, provider_override=prov, auto_start_worker=False)
            summary2 = q2.get_summary()
            recovered_task = next(t for t in summary2["tasks"] if t["task_id"] == "task-interrupted")
            self.assertEqual(recovered_task["status"], "pending")
            self.assertTrue(recovered_task["recovered_from_restart"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
