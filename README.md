# AI Trend Hunter V2 — Efficient Pipeline

Windows용 로컬 AI 트렌드 수집·분석 앱입니다. V2는 메타데이터를 먼저 평가해 가치가 높거나 불확실한 항목만 ego(lite)로 읽고, URL 캐시를 재사용합니다. Ollama의 분류·요약과 트렌드 점수 평가를 별도 호출로 분리하며, 근거 수준에 따른 신뢰도를 함께 저장합니다.

## V2 핵심 변경사항

1. 규칙 기반 메타데이터 점수와 불확실성으로 브라우저 후보를 먼저 선별
2. SQLite URL 캐시로 동일 원문 재방문 방지(기본 24시간)
3. 원문·캐시·메타데이터 전용 결과를 구분하고 신뢰도 상한 적용
4. 분류·요약과 트렌드 점수 평가를 별도 Ollama 요청으로 분리
5. novelty·usefulness·impact 가중치로 최종 점수 계산
6. 강한 AI 키워드가 있을 때만 4B 모델의 `기타` 오분류를 보수적으로 보정

## 가장 쉬운 실행 방법

`AI Trend Hunter.lnk`를 더블클릭하세요. 첫 실행이면 가상환경과 패키지를 자동 설치하고, Ollama 서버를 확인·시작한 뒤 Streamlit 대시보드를 엽니다.

GitHub에서 새로 받은 복사본에는 PC 절대경로가 포함되는 `.lnk` 파일이 없습니다. 처음에는 `powershell -ExecutionPolicy Bypass -File .\launcher.ps1`을 실행하고, 필요하면 해당 명령을 가리키는 Windows 바로가기를 만드세요.

## 빠른 시작

요구 사항: Windows 10/11, Python 3.11 이상, 실행 중인 Ollama, 설치·실행 중인 ego(lite). PowerShell에서 프로젝트 폴더로 이동한 뒤:

```powershell
.\setup.ps1
ollama pull qwen3:4b
.\start.ps1
```

PowerShell 실행 정책이 스크립트를 막으면 `powershell -ExecutionPolicy Bypass -File .\setup.ps1` 형태로 실행하세요.

브라우저에서 `http://localhost:8501`을 열고 **지금 전체 실행**을 누릅니다. 이 PC처럼 `qwen3:4b`가 없고 `qwen3.5:4b`가 있으면 설치된 Qwen 4B 모델을 자동 선택합니다.

## 먼저 진단하기

```powershell
.\diagnose.ps1
```

진단은 Python, SQLite, Ollama, 공식 `ego-browser skill` 가이드, 실제 ego(lite) 작업 공간 연결을 확인합니다. 실제 연결은 사용자 탭을 건드리지 않고 전용 TaskSpace에서 `example.com`만 열었다가 `finish({ keep: [] })`로 종료합니다.

격리된 에이전트 환경에서 `cannot connect to the ego_cli bootstrap`가 나오지만 일반 PowerShell에서는 성공한다면 설치 문제가 아니라 격리 제한입니다. 일반 PowerShell에서도 실패하면 ego(lite)를 직접 열고 다시 실행하세요.

## 명령줄 실행

```powershell
.\.venv\Scripts\python.exe run_pipeline.py
# 브라우저 없이 수집→Ollama→SQLite만 검증
.\.venv\Scripts\python.exe run_pipeline.py --no-browser
```

## 파이프라인

1. GeekNews·HN·GitHub 후보 수집 및 SQLite upsert
2. 제목·설명·날짜·인기도로 메타데이터 점수와 불확실성 계산
3. 상위 점수·불확실 후보만 캐시 확인 후 ego(lite) 원문 탐색
4. Ollama 분류·요약과 세부 점수 평가를 별도로 실행
5. 모델이 고른 **추출된 허용 링크**만 선택적으로 추가 탐색
6. 근거 수준과 신뢰도를 포함한 최종 결과를 SQLite에 저장

LG Gram의 CPU/RAM 사용량을 줄이기 위해 Ollama 컨텍스트는 8K, 분석 출력은 500토큰으로 제한합니다.

## 데이터와 설정

- DB: `data/trend_hunter.db` (`page_cache` 테이블 포함)
- 환경 변수 예시: `.env.example` (앱이 `.env` 파일을 자동 로드하지 않으므로 PowerShell 환경 변수로 설정)
- 빠른 시험은 `TREND_HUNTER_PER_SOURCE_LIMIT=1`, `TREND_HUNTER_INITIAL_BROWSER_LIMIT=1`, `TREND_HUNTER_FOLLOWUP_LIMIT=1`로 축소할 수 있습니다.
- GitHub 토큰은 선택 사항입니다. 없으면 공개 API의 낮은 호출 한도를 사용합니다.
- 외부 유료 LLM API는 사용하지 않습니다.

## 검증 범위

- `python -m unittest discover -s tests -v`: DB 저장/조회와 공식 ego 작업 수명주기 스크립트 검증
- `python diagnose.py`: 로컬 서비스 상태 검증
- `python run_pipeline.py --no-browser`: 실제 네트워크 수집, 실제 Ollama 추론, 실제 SQLite 저장
- `python diagnose.py --live-browser`: 실제 ego(lite) 연결 검증

사이트 네트워크 정책, GitHub 호출 한도, 페이지 DOM 변경 때문에 일부 항목만 처리될 수 있으며 실행 기록과 오류가 UI에 그대로 남습니다.

이 PC에서 수행한 실제 검증과 미검증 범위는 `VALIDATION.md`에 분리해 기록했습니다.

## 상세 구조

```text
GeekNews RSS ─┐
Hacker News API ├─→ 후보 수집 → ego(lite) 원문 탐색
GitHub API ────┘                    ↓
                              Ollama Qwen 4B
                               분류·요약·평가
                                    ↓
                         필요한 경우 선택적 추가 탐색
                                    ↓
                              SQLite 영구 저장
                                    ↓
                         Streamlit 결과 조회 화면
```

외부 유료 LLM API는 사용하지 않습니다. 목록 수집에는 빠르고 안정적인 RSS/API를 사용하고, 원문 확인이 필요한 항목에만 ego(lite)를 사용합니다.

## 출처별 수집 방식

### GeekNews

GeekNews RSS 주소를 읽습니다. RSS 2.0과 현재 리다이렉트되는 Atom 피드를 모두 처리하며 제목, URL, 작성자, 게시 시각, 설명과 고유 ID를 저장합니다.

### Hacker News

공식 Firebase Top Stories API를 사용합니다. 제목, 외부 원문 또는 HN 토론 주소, 작성자, 점수, 게시 시각과 원본 API 응답을 저장합니다.

### GitHub

공식 Repository Search API에서 최근 90일 동안 생성된 LLM·Agent·RAG 관련 저장소를 검색합니다. 기본적으로 별 20개 이상인 저장소를 별 개수순으로 수집합니다. `GITHUB_TOKEN`은 선택 사항입니다.

## ego(lite)의 역할

ego(lite)는 목록 전체를 수집하는 도구가 아니라 선택된 게시물의 원문과 링크를 확인하는 도구입니다.

- 사용자 탭과 분리된 전용 TaskSpace 사용
- `article`, `main` 또는 본문 영역의 텍스트 추출
- 페이지 제목과 외부 링크 추출
- 한 실행에서 동일 TaskSpace 재사용
- 사이트 하나가 실패해도 나머지 항목 계속 처리
- 완료 시 `task.finish({ keep: [] })`로 작업 공간 정리

## Ollama 분석

기본 모델은 `qwen3:4b`이며, 해당 모델이 없으면 설치된 Qwen 4B 모델을 자동 선택합니다. 현재 검증 PC에서는 `qwen3.5:4b`가 선택됐습니다.

분석 결과는 다음 JSON 구조로 생성됩니다.

- `category`: LLM, 에이전트, RAG, 개발도구, 연구, 인프라, 기타
- `summary`: 한국어 요약
- `why_it_matters`: 기술적·실용적 중요성
- `trend_score`: 0~100점
- `needs_followup`: 추가 조사 필요 여부
- `followup_url`: 추가로 확인할 허용 링크

LG Gram의 자원 사용량을 줄이기 위해 컨텍스트 8K, 최대 출력 500토큰, temperature 0.1을 사용합니다.

## 선택적 추가 탐색

모델이 현재 정보만으로 판단하기 어렵다고 평가하면 ego(lite)가 원문에서 실제 추출한 링크 중 하나만 추가로 방문할 수 있습니다. 임의 URL은 허용하지 않습니다. 추가 본문을 확보하면 최초 자료와 함께 다시 분석해 최종 결과를 저장합니다.

## SQLite 구조

### `items`

수집된 원본 게시물을 저장합니다. 동일한 출처와 외부 ID는 중복 생성하지 않고 최신 정보로 갱신합니다.

### `analyses`

카테고리, 요약, 중요성, 트렌드 점수, 추가 탐색 여부, 모델과 분석 시각을 저장합니다.

### `explorations`

ego(lite)가 방문한 URL, 페이지 제목, 추출 본문, 발견한 링크, 탐색 단계와 오류를 저장합니다.

### `runs`와 `run_events`

각 실행의 시작·종료 시각, 상태, 수집·분석·오류 건수 및 단계별 로그를 저장합니다. 상태는 `completed`, `partial`, `failed`로 구분합니다.

## Streamlit 화면

- **결과:** 출처·카테고리·최소 점수·최소 신뢰도·근거 수준 필터, 원문 링크, 요약, CSV 다운로드
- **실행 기록:** 과거 실행 상태와 단계별 로그 조회
- **진단:** Python, SQLite, Ollama, 모델, ego-browser CLI 및 실제 ego(lite) 연결 검사

## 오류 처리

- 출처 하나가 실패해도 다른 출처는 계속 처리
- ego(lite)가 실패하면 제목·설명 기반 분석으로 폴백
- 게시물 하나가 실패해도 다음 게시물 계속 처리
- 추가 탐색이 실패하면 최초 분석 결과 보존
- 모든 오류는 실행 기록에 저장

## 실제 검증 결과

- `AI Trend Hunter.lnk` 원클릭 실행 성공
- 가상환경 및 패키지 자동 준비 성공
- Ollama 서버 자동 시작 및 `qwen3.5:4b` 탐지 성공
- Streamlit `127.0.0.1:8501` 기동 성공
- ego(lite) 실제 연결 및 UI 버튼 조작 성공
- GeekNews·Hacker News·GitHub 각 1건, 총 3건 실제 처리
- 수집 3건, 분석 3건, 오류 0건, 최종 상태 `completed`

V2 캐시 실전 검증에서는 동일한 GitHub AI 저장소를 연속 실행했습니다.

- 첫 실행: `browser_pages=1`, `cache_hits=0`, `browser_status=connected`
- 두 번째 실행: `browser_pages=0`, `cache_hits=1`, `browser_status=cache_only`
- 두 실행 모두 수집 1건, 분석 1건, 오류 0건
- 원문 결과 신뢰도 90, 캐시 원문 결과 신뢰도 80으로 저장

## 현재 한계와 개선 방향

현재 주요 한계는 브라우저 연결보다 4B 모델의 분석 정밀도입니다. 실제 검증에서 서로 다른 항목에 비슷한 카테고리와 점수를 주는 경향이 있었습니다.

다음 개선 우선순위는 메타데이터 1차 선별, 불확실 항목만 ego(lite) 방문, URL별 원문 캐시, 비AI 게시물 필터, 분류와 점수 평가 분리, 근거 문장과 신뢰도 표시입니다.
