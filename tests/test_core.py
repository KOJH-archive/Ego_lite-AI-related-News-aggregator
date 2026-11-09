from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from trend_hunter.db import Database
from trend_hunter.ego_bridge import EgoBrowser, MARKER
from trend_hunter.ollama_client import OllamaClient
from trend_hunter.ranking import evaluate_metadata, select_browser_candidates


class CoreTests(unittest.TestCase):
    def test_database_roundtrip(self):
        temp_root = Path(__file__).resolve().parent / ".tmp"
        temp_root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=temp_root) as directory:
            db = Database(Path(directory) / "test.db")
            run_id = db.start_run()
            item_id = db.upsert_item({"source": "test", "external_id": "1", "title": "Demo", "url": "https://example.com"})
            db.save_analysis(item_id, run_id, {"category": "LLM", "summary": "요약", "trend_score": 77}, "fake")
            db.finish_run(run_id, status="completed", analyzed_count=1)
            self.assertEqual(db.results()[0]["trend_score"], 77)
            self.assertEqual(db.results()[0]["evidence_level"], "metadata_only")
            self.assertEqual(db.runs()[0]["status"], "completed")

    def test_page_cache_roundtrip_and_expiry(self):
        temp_root = Path(__file__).resolve().parent / ".tmp"
        temp_root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=temp_root) as directory:
            db = Database(Path(directory) / "test.db")
            page = {"url": "https://example.com/a", "title": "A", "content": "body",
                    "links": [{"text": "B", "url": "https://example.com/b"}]}
            db.cache_page(page, "ego-lite")
            self.assertEqual(db.cached_page(page["url"], 24)["content"], "body")
            with db.connect() as conn:
                conn.execute("UPDATE page_cache SET fetched_at='2000-01-01T00:00:00+00:00'")
            self.assertIsNone(db.cached_page(page["url"], 24))

    def test_metadata_ranking_selects_ai_candidate(self):
        items = [
            {"title": "C++ committee minutes", "description": "language governance", "score": None},
            {"title": "New local LLM agent", "description": "Ollama agent framework", "score": 128},
        ]
        self.assertGreater(evaluate_metadata(items[1])["metadata_score"], evaluate_metadata(items[0])["metadata_score"])
        self.assertEqual(evaluate_metadata(items[1])["suggested_category"], "에이전트")
        self.assertEqual(select_browser_candidates(items, 1, 10), [1])

    def test_metadata_only_confidence_is_capped(self):
        client = OllamaClient("http://unused", "fake")
        client.classify = lambda *args, **kwargs: {
            "category": "LLM", "summary": "s", "why_it_matters": "w",
            "classification_confidence": 99, "needs_followup": False, "followup_url": "",
        }
        client.score = lambda *args, **kwargs: {
            "novelty": 70, "usefulness": 80, "impact": 90, "trend_score": 81, "score_reason": "r",
        }
        result = client.analyze({"title": "AI", "description": "short"},
                                metadata={"metadata_score": 20}, evidence_level="metadata_only")
        self.assertEqual(result["confidence"], 45)

    def test_strong_metadata_corrects_other_category(self):
        client = OllamaClient("http://unused", "fake")
        client.classify = lambda *args, **kwargs: {
            "category": "기타", "summary": "s", "why_it_matters": "w",
            "classification_confidence": 80, "needs_followup": False, "followup_url": "",
        }
        client.score = lambda *args, **kwargs: {
            "novelty": 60, "usefulness": 70, "impact": 80, "trend_score": 71, "score_reason": "r",
        }
        result = client.analyze({"title": "Agent framework", "description": "AI agent tooling"},
                                metadata={"metadata_score": 40, "suggested_category": "에이전트"},
                                evidence_level="original")
        self.assertEqual(result["category"], "에이전트")

    def test_ego_script_has_official_lifecycle(self):
        script = EgoBrowser._script(["https://example.com"], "test-space", finish=True)
        self.assertIn("taskSpace", script)
        self.assertIn("task.finish({ keep: [] })", script)
        self.assertIn(MARKER, script)


if __name__ == "__main__":
    unittest.main()

