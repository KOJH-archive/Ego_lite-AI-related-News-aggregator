$ErrorActionPreference = "Continue"
Set-Location $PSScriptRoot
$python = if (Test-Path ".venv\Scripts\python.exe") { ".\.venv\Scripts\python.exe" } else { "python" }
& $python diagnose.py --live-browser

