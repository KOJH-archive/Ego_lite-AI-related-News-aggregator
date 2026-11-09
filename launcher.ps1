param(
    [switch]$CheckOnly
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Write-Step([string]$Message) {
    Write-Host "`n==> $Message" -ForegroundColor Cyan
}

function Test-Url([string]$Url, [int]$TimeoutSec = 3) {
    try {
        $null = Invoke-RestMethod -Uri $Url -TimeoutSec $TimeoutSec
        return $true
    } catch {
        return $false
    }
}

try {
    Write-Host "AI Trend Hunter v0.2 one-click launcher" -ForegroundColor Green

    $python = Get-Command python -ErrorAction SilentlyContinue
    if (-not $python) {
        throw "Python was not found. Install Python 3.11 or newer and try again."
    }

    if (-not (Test-Path ".venv\Scripts\python.exe")) {
        Write-Step "Creating the Python environment"
        & python -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw "Failed to create the Python environment." }
    }

    $venvPython = (Resolve-Path ".venv\Scripts\python.exe").Path
    if (-not (Test-Path ".venv\Lib\site-packages\streamlit")) {
        Write-Step "Installing required packages"
        & $venvPython -m pip install -r requirements.txt
        if ($LASTEXITCODE -ne 0) { throw "Failed to install required packages." }
    }

    $ollama = Get-Command ollama -ErrorAction SilentlyContinue
    if (-not $ollama) {
        throw "Ollama was not found. Install Ollama and try again."
    }

    if (-not (Test-Url "http://127.0.0.1:11434/api/tags")) {
        Write-Step "Starting the Ollama server"
        Start-Process -FilePath $ollama.Source -ArgumentList "serve" -WindowStyle Hidden
        $ready = $false
        for ($i = 0; $i -lt 20; $i++) {
            Start-Sleep -Seconds 1
            if (Test-Url "http://127.0.0.1:11434/api/tags") {
                $ready = $true
                break
            }
        }
        if (-not $ready) { throw "Ollama did not start within 20 seconds." }
    }

    $models = (Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 10).models.name
    $qwenModel = $models | Where-Object { $_ -match "qwen" -and $_ -match "4b" } | Select-Object -First 1
    if (-not $qwenModel) {
        throw "No Qwen 4B model is installed. Run: ollama pull qwen3:4b"
    }
    Write-Host "Ollama is ready: $qwenModel" -ForegroundColor Green

    if ($CheckOnly) {
        Write-Host "One-click launcher check passed." -ForegroundColor Green
        exit 0
    }

    if (Test-Url "http://127.0.0.1:8501/_stcore/health") {
        Write-Step "Opening the running dashboard"
        Start-Process "http://127.0.0.1:8501"
        exit 0
    }

    Write-Step "Starting AI Trend Hunter"
    Write-Host "The browser will open automatically. Press Ctrl+C here to stop." -ForegroundColor Yellow
    & $venvPython -m streamlit run app.py `
        --server.address 127.0.0.1 `
        --server.port 8501 `
        --server.headless false `
        --browser.gatherUsageStats false
} catch {
    Write-Host "`nLaunch failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

