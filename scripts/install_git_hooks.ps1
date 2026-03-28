# Installs the Git pre-commit hook (runs pytest via .venv). Safe to run after each clone.
# Requires: git on PATH; Python on PATH if .venv is missing (installer only uses stdlib).
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent $here
Set-Location $root

$runner = Join-Path $here "run_commit_tests.py"
$venvPy = Join-Path $root ".venv\Scripts\python.exe"

if (Test-Path -LiteralPath $venvPy) {
    & $venvPy $runner --install-hook
} else {
    python $runner --install-hook
}
