from __future__ import annotations

import json
import re
from typing import Any

import requests


CATEGORIES = ["LLM", "에이전트", "RAG", "개발도구", "연구", "인프라", "기타"]

CLASSIFICATION_SCHEMA = {
    "type": "object",
    "properties": {
        "category": {"type": "string", "enum": CATEGORIES},
        "summary": {"type": "string"},
        "why_it_matters": {"type": "string"},
        "classification_confidence": {"type": "integer", "minimum": 0, "maximum": 100},
        "needs_followup": {"type": "boolean"},
        "followup_url": {"type": "string"},
    },
    "required": ["category", "summary", "why_it_matters", "classification_confidence",
                 "needs_followup", "followup_url"],
}

SCORE_SCHEMA = {
    "type": "object",
    "properties": {
        "novelty": {"type": "integer", "minimum": 0, "maximum": 100},
        "usefulness": {"type": "integer", "minimum": 0, "maximum": 100},
        "impact": {"type": "integer", "minimum": 0, "maximum": 100},
        "score_reason": {"type": "string"},
    },
    "required": ["novelty", "usefulness", "impact", "score_reason"],
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
            qwen_4b = next((name for name in names if "qwen" in name.lower() and
                            ("4b" in name.lower() or "4." in name.lower())), None)
            qwen = next((name for name in names if "qwen" in name.lower()), None)
            if not (qwen_4b or qwen or (names[0] if names else None)):
                raise RuntimeError("Ollama에 설치된 모델이 없습니다.")
            self.model = qwen_4b or qwen or names[0]
        return self.model

    def _chat_json(self, prompt: str, schema: dict[str, Any], num_predict: int = 500) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "stream": False,
            "think": False,
            "format": schema,
            "messages": [{"role": "user", "content": prompt}],
            "options": {"temperature": 0.1, "num_ctx": 8192, "num_predict": num_predict},
            "keep_alive": "10m",
        }
        response = requests.post(f"{self.base_url}/api/chat", json=payload, timeout=self.timeout)
        response.raise_for_status()
        content = response.json().get("message", {}).get("content", "")
        match = re.search(r"\{.*\}", content, re.S)
        if not match:
            raise ValueError(f"Ollama가 JSON을 반환하지 않았습니다: {content[:200]}")
        return json.loads(match.group(0))

    @staticmethod
    def _evidence_text(item: dict[str, Any], exploration: dict[str, Any] | None,
                       followup: dict[str, Any] | None) -> str:
        return f"""출처: {item.get('source')}
제목: {item.get('title')}
설명: {item.get('description', '')}
원문 본문: {(exploration or {}).get('content', '')[:7000]}
추가 탐색 본문: {(followup or {}).get('content', '')[:5000]}"""

    def classify(self, item: dict[str, Any], exploration: dict[str, Any] | None = None,
                 followup: dict[str, Any] | None = None) -> dict[str, Any]:
        links = (exploration or {}).get("links", [])[:12]
        prompt = f"""당신은 AI 기술 뉴스 편집자다. 아래 근거만 이용해 한국어 JSON을 작성하라.
분류와 요약만 수행하고 트렌드 점수는 계산하지 마라.
AI와 직접 관련이 없으면 반드시 category를 '기타'로 지정하라.
원문이 없고 제목·짧은 설명만 있으면 classification_confidence를 45 이하로 지정하라.
추가 탐색 URL은 반드시 허용 링크 중 하나거나 빈 문자열이어야 한다.

{self._evidence_text(item, exploration, followup)}
허용 링크: {json.dumps(links, ensure_ascii=False)}
"""
        result = self._chat_json(prompt, CLASSIFICATION_SCHEMA, 420)
        result["classification_confidence"] = max(0, min(100, int(result.get("classification_confidence", 0))))
        allowed = {row.get("url") for row in links if isinstance(row, dict)}
        if result.get("followup_url") not in allowed:
            result["followup_url"] = ""
            result["needs_followup"] = False
        return result

    def score(self, item: dict[str, Any], exploration: dict[str, Any] | None = None,
              followup: dict[str, Any] | None = None) -> dict[str, Any]:
        prompt = f"""당신은 독립적인 기술 트렌드 평가자다. 분류나 요약은 하지 말고 세 축만 평가하라.
novelty는 새로움, usefulness는 실제 활용성, impact는 기술 생태계 영향력이다.
서로 다른 축에 같은 점수를 반복하지 말고 구체적 근거가 없으면 50점 이하로 제한하라.
원문이 없으면 과도한 점수를 주지 마라. 한국어 score_reason을 한 문장으로 작성하라.

{self._evidence_text(item, exploration, followup)}
"""
        result = self._chat_json(prompt, SCORE_SCHEMA, 260)
        for key in ("novelty", "usefulness", "impact"):
            result[key] = max(0, min(100, int(result.get(key, 0))))
        result["trend_score"] = round(
            result["novelty"] * 0.30 + result["usefulness"] * 0.35 + result["impact"] * 0.35
        )
        return result

    def analyze(self, item: dict[str, Any], exploration: dict[str, Any] | None = None,
                followup: dict[str, Any] | None = None, metadata: dict[str, Any] | None = None,
                evidence_level: str = "metadata_only") -> dict[str, Any]:
        classification = self.classify(item, exploration, followup)
        scoring = self.score(item, exploration, followup)
        metadata = metadata or {}
        confidence_caps = {"metadata_only": 45, "cached_original": 80, "original": 90, "followup": 95}
        confidence = min(classification["classification_confidence"], confidence_caps.get(evidence_level, 45))
        result = {**classification, **scoring, "confidence": confidence, "evidence_level": evidence_level,
                  "metadata_score": int(metadata.get("metadata_score", 0)),
                  "uncertain": bool(metadata.get("uncertain", False))}
        if result["category"] == "기타" and metadata.get("suggested_category"):
            result["category"] = metadata["suggested_category"]
        if result["metadata_score"] < 10 and evidence_level == "metadata_only":
            result["category"] = "기타"
            result["trend_score"] = min(result["trend_score"], 30)
            result["score_reason"] = "AI 관련 메타데이터와 원문 근거가 부족해 보수적으로 평가했습니다."
        return result

