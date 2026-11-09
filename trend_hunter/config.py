from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    return default if value is None else value.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    value = os.getenv(name)
    return default if value is None else max(1, int(value))


@dataclass(slots=True)
class Settings:
    db_path: Path = Path(os.getenv("TREND_HUNTER_DB", ROOT / "data" / "trend_hunter.db"))
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
    preferred_model: str = os.getenv("OLLAMA_MODEL", "qwen3:4b")
    github_token: str = os.getenv("GITHUB_TOKEN", "")
    ego_enabled: bool = _bool("EGO_BROWSER_ENABLED", True)
    request_timeout: int = 20
    ollama_timeout: int = 180
    browser_timeout: int = 120
    per_source_limit: int = _int("TREND_HUNTER_PER_SOURCE_LIMIT", 8)
    initial_browser_limit: int = _int("TREND_HUNTER_INITIAL_BROWSER_LIMIT", 6)
    followup_limit: int = _int("TREND_HUNTER_FOLLOWUP_LIMIT", 3)
    browser_min_metadata_score: int = _int("TREND_HUNTER_BROWSER_MIN_SCORE", 10)
    page_cache_hours: int = _int("TREND_HUNTER_PAGE_CACHE_HOURS", 24)

