from __future__ import annotations

import platform
import sqlite3
import sys
from typing import Any

from .config import Settings
from .db import Database
from .ego_bridge import EgoBrowser
from .ollama_client import OllamaClient


def run_diagnostics(settings: Settings, live_browser: bool = False) -> list[dict[str, Any]]:
    checks = [{"name": "Python", "ok": sys.version_info >= (3, 11), "detail": sys.version.split()[0]},
              {"name": "Windows", "ok": platform.system() == "Windows", "detail": platform.platform()}]
    try:
        db = Database(settings.db_path)
        with db.connect() as conn:
            conn.execute("SELECT 1").fetchone()
        checks.append({"name": "SQLite", "ok": True, "detail": f"{sqlite3.sqlite_version} / {settings.db_path}"})
    except Exception as exc:
        checks.append({"name": "SQLite", "ok": False, "detail": str(exc)})
    try:
        client = OllamaClient(settings.ollama_base_url, settings.preferred_model)
        model = client.choose_model()
        checks.append({"name": "Ollama", "ok": True, "detail": f"연결됨 / 선택 모델 {model}"})
    except Exception as exc:
        checks.append({"name": "Ollama", "ok": False, "detail": str(exc)})
    ego = EgoBrowser(settings.browser_timeout)
    result = ego.diagnostic()
    checks.append({"name": "ego-browser CLI", "ok": result["ok"], "detail": result["message"]})
    if live_browser:
        try:
            rows, _ = ego.browse(["https://example.com"], "ai-trend-hunter-diagnostic")
            checks.append({"name": "ego(lite) 실제 연결", "ok": bool(rows and rows[0].get("content")), "detail": rows[0].get("title", "")})
        except Exception as exc:
            checks.append({"name": "ego(lite) 실제 연결", "ok": False, "detail": str(exc)})
    return checks

