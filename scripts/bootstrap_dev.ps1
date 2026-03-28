# One-shot dev setup: .venv, runtime + dev dependencies, Git pre-commit hook (pytest on commit).
#
# Run from anywhere (script cd's to repo root):
#   .\scripts\bootstrap_dev.ps1

$ErrorActionPreference = "Stop"

$ScriptsDir = $PSScriptRoot
if (-not $ScriptsDir) {
    $ScriptsDir = Split-Path -Parent $MyInvocation.MyCommand.Path
}
$Root = Split-Path -Parent $ScriptsDir
Set-Location $Root

$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $VenvPython)) {
    Write-Host "Creating .venv ..." -ForegroundColor Cyan
    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3 -m venv "$Root\.venv"
    } elseif (Get-Command python -ErrorAction SilentlyContinue) {
        & python -m venv "$Root\.venv"
    } else {
        throw "Python 3 not found (tried 'py -3' and 'python'). Install Python 3 and retry."
    }
    if (-not (Test-Path -LiteralPath $VenvPython)) {
        throw "Expected $VenvPython after venv creation."
    }
}

Write-Host "Upgrading pip and installing requirements (runtime + dev) ..." -ForegroundColor Cyan
& $VenvPython -m pip install --upgrade pip
& $VenvPython -m pip install -r "$Root\requirements.txt" -r "$Root\requirements-dev.txt"

Write-Host "Installing Git pre-commit hook ..." -ForegroundColor Cyan
& $VenvPython "$Root\scripts\run_commit_tests.py" --install-hook

Write-Host "Done. Activate with: .\.venv\Scripts\Activate.ps1" -ForegroundColor Green
Write-Host "Commits will run: pytest tests -q --tb=short (via .git/hooks/pre-commit)" -ForegroundColor Green
