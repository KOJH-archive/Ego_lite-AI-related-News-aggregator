from __future__ import annotations

import json
import re
from typing import Any

import requests


ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "category": {"type": "string", "enum": ["LLM", "에이전트", "RAG", "개발도구", "연구", "인프라", "기타"]},
        "summary": {"type": "string"},
        "why_it_matters": {"type": "string"},
        "trend_score": {"type": "integer", "minimum": 0, "maximum": 100},
        "needs_followup": {"type": "boolean"},
        "followup_url": {"type": "string"},
    },
    "required": ["category", "summary", "why_it_matters", "trend_score", "needs_followup", "followup_url"],
}


class OllamaClient:
    def __init__(self, base_url: str, preferred_model: str, timeout: int = 180):
        self.base_url = base_url.rstrip("/")
        self.preferred_model = preferred_model
        self.timeout = timeout
        self.model = preferred_model

    def models(self) -> list[str]:
        response = requests.get(f"{self.base_url}/api/tags", timeout=10)
        response.raise_for_status()
        return [row["name"] for row in response.json().get("models", [])]

    def choose_model(self) -> str:
        names = self.models()
        if self.preferred_model in names:
            self.model = self.preferred_model
        else:
            qwen_4b = next((name for name in names if "qwen" in name.lower() and ("4b" in name.lower() or "4." in name.lower())), None)
            qwen = next((name for name in names if "qwen" in name.lower()), None)
            if not (qwen_4b or qwen or (names[0] if names else None)):
                raise RuntimeError("Ollama에 설치된 모델이 없습니다.")
            self.model = qwen_4b or qwen or names[0]
        return self.model

    def analyze(self, item: dict[str, Any], exploration: dict[str, Any] | None = None,
                followup: dict[str, Any] | None = None) -> dict[str, Any]:
        links = (exploration or {}).get("links", [])[:12]
        prompt = f"""당신은 AI 기술 트렌드 분석가다. 아래 자료를 근거로만 한국어 JSON을 작성하라.
카테고리는 LLM/에이전트/RAG/개발도구/연구/인프라/기타 중 하나다.
trend_score는 신선도, 실용성, 기술적 영향도를 합쳐 0~100이다.
추가 탐색은 현재 정보가 부족하고 아래 허용 링크 중 유용한 것이 있을 때만 true다.
followup_url은 반드시 허용 링크 중 하나거나 빈 문자열이어야 한다.

출처: {item.get('source')}
제목: {item.get('title')}
설명: {item.get('description', '')}
초기 브라우저 본문: {(exploration or {}).get('content', '')[:9000]}
허용 링크: {json.dumps(links, ensure_ascii=False)}
추가 탐색 본문: {(followup or {}).get('content', '')[:9000]}
"""
        payload = {"model": self.model, "stream": False, "think": False, "format": ANALYSIS_SCHEMA,
                   "messages": [{"role": "user", "content": prompt}],
                   "options": {"temperature": 0.1, "num_ctx": 8192, "num_predict": 500},
                   "keep_alive": "10m"}
        response = requests.post(f"{self.base_url}/api/chat", json=payload, timeout=self.timeout)
        response.raise_for_status()
        content = response.json().get("message", {}).get("content", "")
        match = re.search(r"\{.*\}", content, re.S)
        if not match:
            raise ValueError(f"Ollama가 JSON을 반환하지 않았습니다: {content[:200]}")
        result = json.loads(match.group(0))
        result["trend_score"] = max(0, min(100, int(result.get("trend_score", 0))))
        allowed = {row.get("url") for row in links if isinstance(row, dict)}
        if result.get("followup_url") not in allowed:
            result["followup_url"] = ""
            result["needs_followup"] = False
        return result

