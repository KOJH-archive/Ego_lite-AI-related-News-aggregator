# 검증 보고서 (2026-11-09, Windows 11)

## 실제 동작 검증 완료

- Python 3.14.4 문법 컴파일
- SQLite 3.50.4 스키마 생성, item upsert, 분석 저장, 실행 로그 조회
- Ollama 0.40.15 로컬 API 연결
- 설치된 `qwen3.5:4b` 자동 선택 및 JSON 스키마 분석 응답
- 공식 `ego-browser skill` 가이드 v2.2.0 완전 출력 확인
- 열린 ego(lite)에 실제 연결: 전용 TaskSpace 생성, `https://example.com` 읽기, `finish({ keep: [] })` 종료
- GeekNews Atom 피드, Hacker News API, GitHub Search API에서 각각 실제 항목 1개 이상 수집
- 실제 GeekNews 항목으로 수집 → ego(lite) 원문 읽기 → Ollama 분석 → SQLite 저장 통합 실행 완료
- Streamlit UI의 **지금 전체 실행**을 ego(lite)에서 직접 클릭해 GeekNews·HN·GitHub 각 1건, 총 3건을 실제 처리: `completed`, 브라우저 `connected`, 수집 3, 분석 3, 오류 0
- Streamlit 결과 화면에서 `완료: 3개 수집 / 3개 분석`과 실행 기록 ID 1을 확인
- Streamlit 1.67.0 서버 기동 및 `/_stcore/health` HTTP 200 / `ok`
- `python -m unittest discover -s tests -v`: 2개 테스트 통과

## 부분 검증

- 선택적 추가 탐색 분기는 코드·허용 URL 검증 로직까지 구현했지만, 실전 샘플에서 모델이 추가 탐색 불필요로 판단해 실제 follow-up 페이지 방문은 발생하지 않았습니다.
- HN과 GitHub를 포함한 3개 출처 모두 Streamlit 통합 실행에서 Ollama 분석과 SQLite 저장까지 확인했습니다. 초기 브라우저 원문 탐색은 축소 설정에 따라 상위 1건에 수행됐습니다.
- 기본 전체 실행은 출처당 8건이라 CPU 전용 4B 모델에서 수십 분이 걸릴 수 있습니다.

## 이 PC에서 확인된 차이

- 요청 모델 `qwen3:4b`는 설치되어 있지 않았고 `qwen3.5:4b`가 설치되어 있었습니다. 앱은 지정 모델이 없으면 설치된 Qwen 4B를 자동 선택합니다.
- 격리된 에이전트 권한에서는 로컬 소켓과 ego bootstrap이 차단됐지만, 일반 로컬 권한에서는 Ollama, ego(lite), Streamlit 모두 실제 연결에 성공했습니다. 사용자가 `start.ps1`과 `diagnose.ps1`을 일반 PowerShell에서 실행할 때는 이 제한이 없습니다.

## 재현 명령

```powershell
powershell -ExecutionPolicy Bypass -File .\setup.ps1
powershell -ExecutionPolicy Bypass -File .\diagnose.ps1
powershell -ExecutionPolicy Bypass -File .\start.ps1
```
