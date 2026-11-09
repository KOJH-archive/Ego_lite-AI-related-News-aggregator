$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
if (-not (Test-Path ".venv\Scripts\python.exe")) { throw "먼저 .\setup.ps1 을 실행하세요." }
& ".\.venv\Scripts\python.exe" -m streamlit run app.py

