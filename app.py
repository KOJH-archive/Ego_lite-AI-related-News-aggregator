from __future__ import annotations

import pandas as pd
import streamlit as st

from trend_hunter.config import Settings
from trend_hunter.db import Database
from trend_hunter.diagnostics import run_diagnostics
from trend_hunter.pipeline import Pipeline


st.set_page_config(page_title="AI Trend Hunter V2", page_icon="🧭", layout="wide")
st.title("🧭 AI Trend Hunter V2 — Efficient Pipeline")
st.caption("RSS/API → 메타데이터 사전평가 → 선택적 ego(lite)·캐시 → 분리형 Ollama 분석 → SQLite")

settings = Settings()
db = Database(settings.db_path)

with st.sidebar:
    st.header("실행 설정")
    use_browser = st.toggle("ego(lite) 탐색 사용", value=settings.ego_enabled)
    st.write(f"Ollama 우선 모델: `{settings.preferred_model}`")
    st.write(f"DB: `{settings.db_path}`")
    run_button = st.button("지금 전체 실행", type="primary", width="stretch")

if run_button:
    log_box = st.empty()
    logs: list[str] = []
    def log(message: str):
        logs.append(message)
        log_box.code("\n".join(logs[-20:]), language=None)
    with st.spinner("수집·탐색·분석 중입니다. 로컬 모델 속도에 따라 몇 분 걸릴 수 있습니다."):
        report = Pipeline(settings, log=log).run(use_browser=use_browser)
    if report.status == "completed":
        st.success(f"완료: {report.collected}개 수집 / {report.analyzed}개 분석 / "
                   f"브라우저 {report.browser_pages}개 / 캐시 {report.cache_hits}개")
    elif report.status == "partial":
        st.warning(f"부분 완료: {report.collected}개 수집 / {report.analyzed}개 분석")
    else:
        st.error("실행에 실패했습니다. 아래 오류와 진단 탭을 확인하세요.")
    if report.errors:
        st.code("\n".join(report.errors), language=None)

results_tab, runs_tab, diag_tab = st.tabs(["결과", "실행 기록", "진단"])
with results_tab:
    rows = db.results()
    if not rows:
        st.info("아직 분석 결과가 없습니다. 왼쪽의 ‘지금 전체 실행’을 눌러주세요.")
    else:
        frame = pd.DataFrame(rows)
        sources = st.multiselect("출처", sorted(frame.source.unique()), default=sorted(frame.source.unique()))
        categories = st.multiselect("카테고리", sorted(frame.category.unique()), default=sorted(frame.category.unique()))
        minimum = st.slider("최소 트렌드 점수", 0, 100, 0)
        confidence = st.slider("최소 신뢰도", 0, 100, 0)
        evidence = st.multiselect("근거 수준", sorted(frame.evidence_level.unique()),
                                  default=sorted(frame.evidence_level.unique()))
        shown = frame[frame.source.isin(sources) & frame.category.isin(categories) &
                      (frame.trend_score >= minimum) & (frame.confidence >= confidence) &
                      frame.evidence_level.isin(evidence)]
        st.dataframe(shown, width="stretch", hide_index=True,
                     column_config={"url": st.column_config.LinkColumn("원문")})
        st.download_button("CSV 다운로드", shown.to_csv(index=False).encode("utf-8-sig"), "trend_hunter.csv", "text/csv")
with runs_tab:
    run_rows = db.runs()
    st.dataframe(run_rows, width="stretch", hide_index=True)
    if run_rows:
        selected = st.selectbox("로그를 볼 실행", [row["id"] for row in run_rows])
        st.dataframe(db.events(selected), width="stretch", hide_index=True)
with diag_tab:
    live = st.checkbox("ego(lite) 실제 연결까지 시험 (새 전용 작업 공간에서 example.com만 열고 종료)")
    if st.button("환경 진단 실행"):
        checks = run_diagnostics(settings, live_browser=live)
        st.dataframe(checks, width="stretch", hide_index=True)

