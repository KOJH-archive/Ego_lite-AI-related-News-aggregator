from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Callable

from .collectors import Collectors
from .config import Settings
from .db import Database
from .ego_bridge import EgoBrowser
from .ollama_client import OllamaClient


@dataclass(slots=True)
class RunReport:
    run_id: int
    status: str
    model: str
    browser_status: str
    collected: int
    analyzed: int
    errors: list[str]

    def to_dict(self):
        return asdict(self)


class Pipeline:
    def __init__(self, settings: Settings, log: Callable[[str], None] | None = None):
        self.settings = settings
        self.db = Database(settings.db_path)
        self.collectors = Collectors(settings.request_timeout, settings.github_token)
        self.ollama = OllamaClient(settings.ollama_base_url, settings.preferred_model, settings.ollama_timeout)
        self.browser = EgoBrowser(settings.browser_timeout)
        self.log = log or (lambda message: None)

    def _event(self, run_id: int, step: str, message: str, level: str = "info"):
        self.db.event(run_id, step, message, level)
        self.log(f"[{step}] {message}")

    def run(self, use_browser: bool = True) -> RunReport:
        run_id = self.db.start_run()
        errors: list[str] = []
        analyzed = 0
        browser_status = "disabled"
        model = ""
        items: list[dict[str, Any]] = []
        browser_task = f"ai-trend-hunter-run-{run_id}"
        browser_open = False
        try:
            self._event(run_id, "collect", "GeekNews·Hacker News·GitHub 수집 시작")
            items, collect_errors = self.collectors.collect_all(self.settings.per_source_limit)
            errors.extend(collect_errors)
            ids = [self.db.upsert_item(item) for item in items]
            self._event(run_id, "collect", f"후보 {len(items)}개 저장")

            model = self.ollama.choose_model()
            self._event(run_id, "ollama", f"모델 선택: {model}")

            initial: dict[int, dict[str, Any]] = {}
            if use_browser and self.settings.ego_enabled and items:
                subset = items[: self.settings.initial_browser_limit]
                try:
                    browsed, backend = self.browser.browse([item["url"] for item in subset], browser_task, finish=False)
                    browser_open = True
                    browser_status = "connected"
                    for index, result in enumerate(browsed):
                        item_id = ids[index]
                        initial[item_id] = result
                        self.db.save_exploration(item_id, run_id, "initial", result, backend)
                    self._event(run_id, "browser", f"초기 페이지 {len(browsed)}개 탐색")
                except Exception as exc:
                    browser_status = "unavailable"
                    errors.append(f"ego-browser: {exc}")
                    self._event(run_id, "browser", str(exc), "warning")

            plans: list[tuple[int, dict[str, Any], dict[str, Any]]] = []
            for item_id, item in zip(ids, items):
                try:
                    analysis = self.ollama.analyze(item, initial.get(item_id))
                    plans.append((item_id, item, analysis))
                except Exception as exc:
                    errors.append(f"분석 {item.get('title')}: {exc}")
                    self._event(run_id, "ollama", f"분석 실패: {item.get('title')}: {exc}", "error")

            followups = [(item_id, item, plan) for item_id, item, plan in plans
                         if plan.get("needs_followup") and plan.get("followup_url")][: self.settings.followup_limit]
            followup_results: dict[int, dict[str, Any]] = {}
            if followups and browser_status == "connected":
                try:
                    browsed, backend = self.browser.browse([plan["followup_url"] for _, _, plan in followups], browser_task, finish=True)
                    browser_open = False
                    for (item_id, _, _), result in zip(followups, browsed):
                        followup_results[item_id] = result
                        self.db.save_exploration(item_id, run_id, "followup", result, backend)
                    self._event(run_id, "browser", f"선택적 추가 탐색 {len(browsed)}개 완료")
                except Exception as exc:
                    errors.append(f"추가 탐색: {exc}")
                    self._event(run_id, "browser", f"추가 탐색 실패: {exc}", "warning")

            if browser_open:
                self.browser.finish(browser_task)
                browser_open = False

            for item_id, item, plan in plans:
                final = plan
                if item_id in followup_results:
                    try:
                        final = self.ollama.analyze(item, initial.get(item_id), followup_results[item_id])
                    except Exception as exc:
                        errors.append(f"최종 분석 {item.get('title')}: {exc}")
                self.db.save_analysis(item_id, run_id, final, model)
                analyzed += 1

            status = "completed" if not errors else ("partial" if analyzed else "failed")
        except Exception as exc:
            errors.append(f"실행 중단: {type(exc).__name__}: {exc}")
            status = "failed"
            self._event(run_id, "pipeline", errors[-1], "error")
        if browser_open:
            try:
                self.browser.finish(browser_task)
            except Exception as exc:
                errors.append(f"브라우저 작업 공간 정리 실패: {exc}")
        self.db.finish_run(run_id, status=status, model=model, browser_status=browser_status,
                           collected_count=len(items), analyzed_count=analyzed, error_count=len(errors))
        return RunReport(run_id, status, model, browser_status, len(items), analyzed, errors)

