from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from trend_hunter.db import Database
from trend_hunter.ego_bridge import EgoBrowser, MARKER


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
            self.assertEqual(db.runs()[0]["status"], "completed")

    def test_ego_script_has_official_lifecycle(self):
        script = EgoBrowser._script(["https://example.com"], "test-space", finish=True)
        self.assertIn("taskSpace", script)
        self.assertIn("task.finish({ keep: [] })", script)
        self.assertIn(MARKER, script)


if __name__ == "__main__":
    unittest.main()

