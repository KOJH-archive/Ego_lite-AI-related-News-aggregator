from __future__ import annotations

import math
import re
from datetime import datetime, timezone
from typing import Any


KEYWORD_WEIGHTS = {
    "large language model": 28,
    "language model": 24,
    "llm": 25,
    "agentic": 23,
    "agent": 18,
    "rag": 22,
    "retrieval augmented": 24,
    "inference": 15,
    "transformer": 16,
    "embedding": 14,
    "vector database": 14,
    "ollama": 20,
    "prompt": 10,
    "ai": 8,
    "인공지능": 12,
    "언어 모델": 24,
    "에이전트": 18,
}


def _freshness_score(value: str | None) -> int:
    if not value:
        return 2
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        days = max(0, (datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).days)
        return max(0, 15 - min(days, 90) // 6)
    except (TypeError, ValueError):
        return 2


def evaluate_metadata(item: dict[str, Any]) -> dict[str, Any]:
    title = str(item.get("title") or "")
    description = str(item.get("description") or "")
    haystack = f"{title} {description}".lower()
    matched: list[str] = []
    relevance = 0
    for keyword, weight in KEYWORD_WEIGHTS.items():
        if re.search(rf"(?<!\w){re.escape(keyword)}(?!\w)", haystack):
            relevance += weight
            matched.append(keyword)
    relevance = min(70, relevance)
    freshness = _freshness_score(item.get("published_at"))
    popularity = 0
    if item.get("score") is not None:
        try:
            popularity = min(15, int(math.log2(max(1.0, float(item["score"])))) * 2)
        except (TypeError, ValueError):
            popularity = 0
    metadata_score = min(100, relevance + freshness + popularity)
    suggested_category = None
    if any(keyword in matched for keyword in ("rag", "retrieval augmented")):
        suggested_category = "RAG"
    elif any(keyword in matched for keyword in ("agent", "agentic", "에이전트")):
        suggested_category = "에이전트"
    elif any(keyword in matched for keyword in
             ("llm", "large language model", "language model", "언어 모델", "ollama")):
        suggested_category = "LLM"
    uncertainty_reasons = []
    if len(description.strip()) < 80:
        uncertainty_reasons.append("short_description")
    if item.get("score") is None:
        uncertainty_reasons.append("missing_popularity")
    if not item.get("published_at"):
        uncertainty_reasons.append("missing_date")
    uncertain = bool(uncertainty_reasons) and relevance >= 8
    browser_priority = min(100, metadata_score + (15 if uncertain else 0))
    return {
        "metadata_score": metadata_score,
        "browser_priority": browser_priority,
        "uncertain": uncertain,
        "matched_keywords": matched,
        "uncertainty_reasons": uncertainty_reasons,
        "suggested_category": suggested_category,
    }


def select_browser_candidates(items: list[dict[str, Any]], limit: int, minimum_score: int = 10) -> list[int]:
    ranked = []
    for index, item in enumerate(items):
        evaluation = evaluate_metadata(item)
        if evaluation["metadata_score"] >= minimum_score or evaluation["uncertain"]:
            ranked.append((evaluation["browser_priority"], evaluation["metadata_score"], index))
    ranked.sort(reverse=True)
    return [index for _, _, index in ranked[:limit]]

