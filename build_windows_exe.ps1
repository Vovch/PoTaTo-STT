# Build a Windows one-folder executable bundle (dist/PipitClone/).
# Uses a dedicated .venv under the repo so PyInstaller does not bundle unrelated
# packages from your global Python install.
#
# Run from the repository root:
#   .\build_windows_exe.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    Write-Host "Creating .venv ..." -ForegroundColor Cyan
    python -m venv "$Root\.venv"
}

Write-Host "Installing dependencies into .venv ..." -ForegroundColor Cyan
& $VenvPython -m pip install --upgrade pip
& $VenvPython -m pip install -r "$Root\requirements.txt" -r "$Root\requirements-build.txt"

Write-Host "Running PyInstaller ..." -ForegroundColor Cyan
& $VenvPython -m PyInstaller "$Root\pipit_clone.spec" --clean --noconfirm

Write-Host ""
Write-Host "Done. Run: $($Root)\dist\PipitClone\PipitClone.exe" -ForegroundColor Green
Write-Host "Ship the entire dist\PipitClone folder (DLLs live next to the .exe)." -ForegroundColor Yellow
