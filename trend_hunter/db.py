from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  status TEXT NOT NULL,
  model TEXT,
  browser_status TEXT,
  collected_count INTEGER DEFAULT 0,
  analyzed_count INTEGER DEFAULT 0,
  error_count INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source TEXT NOT NULL,
  external_id TEXT NOT NULL,
  title TEXT NOT NULL,
  url TEXT NOT NULL,
  author TEXT,
  published_at TEXT,
  score REAL,
  description TEXT,
  raw_json TEXT,
  first_seen_at TEXT NOT NULL,
  last_seen_at TEXT NOT NULL,
  UNIQUE(source, external_id)
);
CREATE TABLE IF NOT EXISTS analyses (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
  run_id INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
  category TEXT NOT NULL,
  summary TEXT NOT NULL,
  why_it_matters TEXT,
  trend_score INTEGER,
  needs_followup INTEGER NOT NULL DEFAULT 0,
  model TEXT,
  created_at TEXT NOT NULL,
  UNIQUE(item_id, run_id)
);
CREATE TABLE IF NOT EXISTS explorations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
  run_id INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
  stage TEXT NOT NULL,
  url TEXT NOT NULL,
  title TEXT,
  content TEXT,
  links_json TEXT,
  browser_backend TEXT,
  error TEXT,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS run_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
  level TEXT NOT NULL,
  step TEXT NOT NULL,
  message TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_items_source_seen ON items(source, last_seen_at DESC);
CREATE INDEX IF NOT EXISTS idx_analyses_score ON analyses(trend_score DESC);
"""


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Database:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            conn.executescript(SCHEMA)

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.path, timeout=30)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def start_run(self) -> int:
        with self.connect() as conn:
            cur = conn.execute("INSERT INTO runs(started_at,status) VALUES(?,?)", (utcnow(), "running"))
            return int(cur.lastrowid)

    def event(self, run_id: int, step: str, message: str, level: str = "info") -> None:
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO run_events(run_id,level,step,message,created_at) VALUES(?,?,?,?,?)",
                (run_id, level, step, message, utcnow()),
            )

    def finish_run(self, run_id: int, **fields: Any) -> None:
        allowed = {"status", "model", "browser_status", "collected_count", "analyzed_count", "error_count"}
        values = {key: value for key, value in fields.items() if key in allowed}
        values["finished_at"] = utcnow()
        clause = ",".join(f"{key}=?" for key in values)
        with self.connect() as conn:
            conn.execute(f"UPDATE runs SET {clause} WHERE id=?", (*values.values(), run_id))

    def upsert_item(self, item: dict[str, Any]) -> int:
        now = utcnow()
        with self.connect() as conn:
            conn.execute(
                """INSERT INTO items(source,external_id,title,url,author,published_at,score,description,raw_json,first_seen_at,last_seen_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(source,external_id) DO UPDATE SET
                  title=excluded.title,url=excluded.url,author=excluded.author,published_at=excluded.published_at,
                  score=excluded.score,description=excluded.description,raw_json=excluded.raw_json,last_seen_at=excluded.last_seen_at""",
                (item["source"], item["external_id"], item["title"], item["url"], item.get("author"),
                 item.get("published_at"), item.get("score"), item.get("description", ""),
                 json.dumps(item.get("raw", {}), ensure_ascii=False), now, now),
            )
            row = conn.execute(
                "SELECT id FROM items WHERE source=? AND external_id=?", (item["source"], item["external_id"])
            ).fetchone()
            return int(row["id"])

    def save_exploration(self, item_id: int, run_id: int, stage: str, result: dict[str, Any], backend: str) -> None:
        with self.connect() as conn:
            conn.execute(
                """INSERT INTO explorations(item_id,run_id,stage,url,title,content,links_json,browser_backend,error,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (item_id, run_id, stage, result.get("url", ""), result.get("title"), result.get("content"),
                 json.dumps(result.get("links", []), ensure_ascii=False), backend, result.get("error"), utcnow()),
            )

    def save_analysis(self, item_id: int, run_id: int, analysis: dict[str, Any], model: str) -> None:
        with self.connect() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO analyses(item_id,run_id,category,summary,why_it_matters,trend_score,needs_followup,model,created_at)
                VALUES(?,?,?,?,?,?,?,?,?)""",
                (item_id, run_id, analysis.get("category", "기타"), analysis.get("summary", ""),
                 analysis.get("why_it_matters", ""), int(analysis.get("trend_score", 0)),
                 int(bool(analysis.get("needs_followup"))), model, utcnow()),
            )

    def results(self, limit: int = 200) -> list[dict[str, Any]]:
        query = """SELECT i.source,i.title,i.url,i.author,i.published_at,i.score,
          a.category,a.summary,a.why_it_matters,a.trend_score,a.needs_followup,a.model,a.created_at
          FROM analyses a JOIN items i ON i.id=a.item_id ORDER BY a.created_at DESC,a.trend_score DESC LIMIT ?"""
        with self.connect() as conn:
            return [dict(row) for row in conn.execute(query, (limit,)).fetchall()]

    def runs(self, limit: int = 50) -> list[dict[str, Any]]:
        with self.connect() as conn:
            return [dict(row) for row in conn.execute("SELECT * FROM runs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()]

    def events(self, run_id: int) -> list[dict[str, Any]]:
        with self.connect() as conn:
            return [dict(row) for row in conn.execute("SELECT * FROM run_events WHERE run_id=? ORDER BY id", (run_id,))]

