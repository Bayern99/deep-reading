"""Governance regressions at the existing source, queue, store and provider interfaces."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from canonical_builder import build_canonical_source
from generation_queue import PersistentGenerationQueue
from artifact_store import ArtifactStore
from editorial_publisher import import_raw_generation
from model_provider import create_provider_for_model


class GovernanceTests(unittest.TestCase):
    def test_canonical_dates_follow_the_selected_issue(self):
        entry = {
            "id": "GOV-1", "type": "brief", "title": "Sample", "title_cn": "示例",
            "body_en": "Complete text.", "body_cn": "完整正文。",
        }
        canonical = build_canonical_source(entry, issue_date="2026-10-14")
        self.assertEqual(canonical["metadata"]["date_cn"], "2026年10月14日")
        self.assertEqual(canonical["metadata"]["date_en"], "October 14, 2026")
        self.assertEqual(canonical["blocks"][0]["text_cn"], "完整正文。")

    def test_invalid_persistent_queue_is_preserved_and_rejected(self):
        for contents in ('{broken', '{"tasks": {}}', '{"schema_version": "editorial-queue-v1"}'):
            with self.subTest(contents=contents), tempfile.TemporaryDirectory() as tmpdir:
                queue_path = Path(tmpdir) / "editorial-artifacts" / "_queue.json"
                queue_path.parent.mkdir()
                queue_path.write_text(contents, encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "Invalid persistent queue"):
                    PersistentGenerationQueue(tmpdir, auto_start_worker=False)
                self.assertEqual(queue_path.read_text(encoding="utf-8"), contents)

    def test_artifact_identifiers_cannot_escape_the_store(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            entry = {
                "id": "GOV-1", "type": "brief", "title": "Sample", "title_cn": "示例",
                "body_en": "Complete text.", "body_cn": "完整正文。",
            }
            Path(tmpdir, "final.json").write_text(json.dumps([entry]), encoding="utf-8")
            import_raw_generation(
                issue_dir=tmpdir, article_id="GOV-1",
                raw_html='<html><body><p data-ref="p1"></p></body></html>',
                model_metadata={"provider": "test", "model_id": "test"},
            )
            store = ArtifactStore(tmpdir)
            for article_id in ("../escaped", str(Path(tmpdir) / "escaped"), "GOV-1/../../escaped"):
                with self.subTest(article_id=article_id), self.assertRaises(ValueError):
                    store.article_dir(article_id)
            outside = Path(tmpdir, "outside")
            outside.mkdir()
            outside.joinpath("artifact.json").write_text('{"artifact_version":"v999"}', encoding="utf-8")
            with self.assertRaises(KeyError):
                store.set_active_version("GOV-1", "../../outside")
            self.assertEqual(store.get_active_artifact("GOV-1")["artifact_version"], "v1")
            self.assertFalse(Path(tmpdir, "escaped").exists())

    def test_explicit_environment_selects_endpoint_and_credentials(self):
        import threading
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

        requests = []

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                requests.append((self.path, self.headers.get("Authorization"), body["model"]))
                response = b'{"choices":[{"message":{"content":"selected endpoint"}}]}'
                self.send_response(200)
                self.send_header("Content-Length", str(len(response)))
                self.end_headers()
                self.wfile.write(response)

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        endpoint = f"http://127.0.0.1:{server.server_port}/v1/chat/completions"
        try:
            with patch.dict(os.environ, {"WSJ_LLM_ENDPOINT": endpoint, "WSJ_LLM_API_KEY": "environment-test-key"}), patch(
                "model_provider.load_local_provider_registry",
                return_value={"magpie": {"baseUrl": "http://127.0.0.1:1/v1", "apiKey": "registry-test-key"}},
            ):
                provider, config = create_provider_for_model("openai-compatible", "local-test-model")
                result = provider.generate("endpoint selection probe", config)
            self.assertEqual(result.content, "selected endpoint")
            self.assertEqual(requests, [("/v1/chat/completions", "Bearer environment-test-key", "local-test-model")])
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=5)
